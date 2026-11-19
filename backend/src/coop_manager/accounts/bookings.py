"""Fachliche Buchungsvorgänge: Eintritt, Rückzahlung, Storno, Auszahlung usw.

Die API bucht nur über diese Vorgänge, nie direkt mit `Ledger.post_booking` (siehe Plan). Jeder
Vorgang prüft seine eigenen Regeln; `post_booking` prüft darunter, was für jede Buchung gilt.

Eigene Datei statt `accounts/services.py`, weil die Vorgänge das Mitglied brauchen und
`members/services.py` schon `accounts/services.py` importiert (sonst Importzyklus).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from ..core import DomainError, NotFoundError
from ..core.money import format_euro
from ..db import Database
from ..eventsource import ConcurrencyError
from ..members.domain import Member
from ..members.services import MAX_ATTEMPTS, get_member
from ..members.status import MEMBER, NOTICE_GIVEN
from ..system_settings.services import get_system_settings
from .domain import (
    ADDITIONAL_SHARES,
    COOPERATIVE_ACCOUNT_NUMBER,
    LIMITATION_WRITEOFF,
    LOSS_DEDUCTION,
    MEMBER_ACCOUNT,
    PAYOUT,
    REFUND,
    REVERSAL,
    SHARE_DONATION,
    SUBSCRIPTION,
    TRANSFER,
    Booking,
    Ledger,
)
from .services import get_ledger

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookingResult:
    """Die gespeicherte Buchung und ggf. eine Warnung; die Buchung gilt auch mit Warnung."""

    booking: Booking
    warning: str | None = None


# Bucht auf dem geladenen Hauptbuch: (Mitglied, Hauptbuch, Kontonummer, Anteilspreis) → Buchung
BookAction = Callable[[Member, Ledger, int, int], Booking]
# Wie BookAction, aber zwischen zwei Mitgliedskonten: (Mitglied Soll, Mitglied Haben, Hauptbuch,
# Anteilspreis) → Buchung und ggf. Warnung
TransferAction = Callable[[Member, Member, Ledger, int], tuple[Booking, str | None]]


def subscribe(
    db: Database,
    account_number: int,
    shares: int,
    value_date: date,
    today: date,
    actor: str,
    text: str | None = None,
) -> BookingResult:
    """Eintritt: Geldeingang für gezeichnete Anteile, Soll Genossenschaftskonto an Haben Mitgliedskonto."""

    _ensure_shares(shares)

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        entry_shares = ledger.shares(account) - ledger.paid_additional_shares(account)
        if member.payment_date is not None or entry_shares >= member.shares_subscribed:
            raise DomainError("Die gezeichneten Anteile sind bereits eingezahlt.")
        assert member.application_date is not None  # gesetzt durch member.applied
        if value_date < member.application_date:
            raise DomainError("Die Wertstellung darf nicht vor dem Antrag liegen.")
        amount = shares * share_price
        return ledger.post_booking(
            SUBSCRIPTION, COOPERATIVE_ACCOUNT_NUMBER, account, amount, shares, text or "Eintritt", value_date, today
        )

    return _book(db, account_number, today, actor, book)


def pay_additional_shares(
    db: Database,
    account_number: int,
    shares: int,
    value_date: date,
    today: date,
    actor: str,
    text: str | None = None,
) -> BookingResult:
    """Weitere Anteile: Einzahlung später gezeichneter Anteile (siehe Plan: Weitere Anteile).

    Soll Genossenschaftskonto an Haben Mitgliedskonto, Betrag = Anteile × Preis. Höchstens die
    offenen Anteile (gezeichnet, aber noch nicht eingezahlt); weniger geht mit Warnung. Kein
    Abgleich am Mitglied: Die Mitgliedschaft hängt nur an der Einzahlung des Antrags.
    """
    _ensure_shares(shares)
    remaining: list[str] = []  # Warnung aus `book`; eine Liste, weil `book` sie nicht neu zuweisen kann

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        remaining.clear()  # bei einem zweiten Versuch (Versionskonflikt) neu rechnen
        subscribed = member.additional_shares_subscribed()
        open_shares = subscribed - ledger.paid_additional_shares(account)
        if open_shares <= 0:
            raise DomainError("Es sind keine weiteren Anteile gezeichnet, die noch offen sind.")
        if shares > open_shares:
            raise DomainError(f"Offen sind nur {open_shares} weitere Anteile.")
        if value_date < min(s.decision_date for s in member.additional_subscriptions):
            raise DomainError("Die Wertstellung darf nicht vor der Zulassung liegen.")
        if member.status(value_date) not in (MEMBER, NOTICE_GIVEN):
            raise DomainError("Weitere Anteile einzahlen kann nur, wer an diesem Tag Mitglied ist.")
        if shares < open_shares:
            paid = subscribed - open_shares + shares
            remaining.append(f"{paid} von {subscribed} weiteren Anteilen eingezahlt.")
        return ledger.post_booking(
            ADDITIONAL_SHARES,
            COOPERATIVE_ACCOUNT_NUMBER,
            account,
            shares * share_price,
            shares,
            text or "Weitere Anteile",
            value_date,
            today,
        )

    result = _book(db, account_number, today, actor, book, reconcile=False)
    return BookingResult(result.booking, remaining[0] if remaining else None)


def refund(
    db: Database,
    account_number: int,
    shares: int,
    value_date: date,
    today: date,
    actor: str,
    text: str | None = None,
) -> BookingResult:
    """Rückzahlung: Soll Mitgliedskonto an Haben Genossenschaftskonto.

    Nur bei abgelehntem oder zurückgenommenem Antrag oder solange die Zahlung ungeklärt ist (noch
    kein Geldeingang erfasst). Mitglieder bekommen ihr Geld über die Kündigung zurück (Schritt 5f).
    """

    _ensure_shares(shares)

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        if member.rejection_date is None and member.payment_date is not None:
            raise DomainError(
                "Zurückgezahlt wird nur bei abgelehntem oder zurückgenommenem Antrag "
                "oder solange die Zahlung ungeklärt ist."
            )
        amount = shares * share_price
        return ledger.post_booking(
            REFUND, account, COOPERATIVE_ACCOUNT_NUMBER, amount, shares, text or "Rückzahlung", value_date, today
        )

    return _book(db, account_number, today, actor, book)


def reverse(db: Database, booking_id: str, reason: str, today: date, actor: str) -> BookingResult:
    """Storno: Gegenbuchung zu einer Buchung, mit Pflichtgrund (siehe Plan: Buchungen und Storno).

    Der Grund steht im Buchungstext, z. B. „Storno zu „Eintritt“: Zahlung falsch zugeordnet“.
    Danach wird wie bei jeder Buchung der Geldeingang am Mitglied abgeglichen.
    """
    if not reason.strip():
        raise DomainError("Der Stornogrund fehlt.")
    original = get_ledger(db).booking(booking_id)
    if original is None:
        raise NotFoundError("Die Buchung gibt es nicht.")
    if original.kind == TRANSFER:
        return _reverse_transfer(db, original, reason, today, actor)
    account_number = member_account_of(original)

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        if original.kind == SHARE_DONATION:  # mit der Buchung entfällt auch das Ausscheiden
            member.revoke_donation()
        return ledger.reverse(booking_id, f"Storno zu „{original.text}“: {reason.strip()}", today)

    # Der Abgleich mit den gezeichneten Anteilen gehört nur zum Eintritt. Nach einem gebuchten
    # Ausscheiden passen gezeichnete und gehaltene Anteile nicht mehr zusammen; ein Abgleich würde
    # dann fälschlich den Geldeingang zurücknehmen.
    return _book(db, account_number, today, actor, book, reconcile=original.kind in (SUBSCRIPTION, REFUND))


def transfer(
    db: Database,
    account_number: int,
    target_account_number: int,
    shares: int,
    value_date: date,
    today: date,
    actor: str,
    text: str | None = None,
) -> BookingResult:
    """Umbuchung von Anteilen auf ein anderes Mitgliedskonto, z. B. auf Erben (siehe Plan: Umbuchung).

    Soll abgebendes Konto an Haben empfangendes Konto, Betrag = Anteile × Preis. Ist der Empfänger
    ein zugelassener Antragsteller, zählt die Umbuchung wie seine Einzahlung und wird abgeglichen;
    passt sie, ist er Mitglied. Gibt der Abgebende alle Anteile ab, scheidet er am Folgetag aus.
    Ein offener Anspruch aus einer früheren Teilkündigung bleibt beim Abgebenden.
    """
    _ensure_shares(shares)

    def book(source: Member, target: Member, ledger: Ledger, share_price: int) -> tuple[Booking, str | None]:
        if target.subject == source.subject:
            raise DomainError("Abgebendes und empfangendes Konto müssen verschieden sein.")
        source.ensure_can_give_shares(value_date)
        target.ensure_can_receive_shares(value_date)
        last_exit = ledger.last_exit_date(account_number)
        held = ledger.shares(account_number)
        if held == 0 and last_exit is not None:
            raise DomainError(
                f"Das Ausscheiden zum {last_exit:%d.%m.%Y} ist bereits gebucht. Für eine Umbuchung "
                "zuerst die Ausscheidensbuchung stornieren."
            )
        if last_exit is not None and value_date <= last_exit:
            raise DomainError(f"Das Datum muss nach dem gebuchten Ausscheiden zum {last_exit:%d.%m.%Y} liegen.")
        if shares > held:
            raise DomainError(f"Auf dem Konto sind nur {held} Anteile.")
        # Anteile aus laufenden Teilkündigungen müssen zum 31.12. noch da sein; wer alles abgibt,
        # scheidet ohnehin vorher aus.
        free = held - source.partially_noticed_shares(ledger.booked_exit_dates(account_number))
        if shares != held and shares > free:
            raise DomainError(f"Höchstens {free} Anteile sind nicht teilgekündigt und können umgebucht werden.")
        booking = ledger.post_booking(
            TRANSFER,
            account_number,
            target_account_number,
            shares * share_price,
            shares,
            text or "Umbuchung",
            value_date,
            today,
        )
        if shares == held:
            source.transfer_all_shares(value_date, today)
        warning = None
        if target.payment_date is None:  # Antragsteller: die Umbuchung ist seine Einzahlung
            warning = _reconcile(target, ledger, target_account_number, booking, today)
        return booking, warning

    return _book_between(db, account_number, target_account_number, actor, book)


def _reverse_transfer(db: Database, original: Booking, reason: str, today: date, actor: str) -> BookingResult:
    """Storno einer Umbuchung: Gegenbuchung zwischen denselben zwei Mitgliedskonten.

    Bekommt der Abgebende so wieder Anteile, entfällt sein Ausscheiden durch Übertragung. Ist der
    Empfänger durch diese Umbuchung Mitglied geworden (Geldeingang = ihre Wertstellung), wird bei
    ihm abgeglichen; dann ist er wieder Antragsteller, mit Warnung.
    """

    def book(source: Member, target: Member, ledger: Ledger, share_price: int) -> tuple[Booking, str | None]:
        booking = ledger.reverse(original.id, f"Storno zu „{original.text}“: {reason.strip()}", today)
        if source.transfer_date is not None and ledger.shares(original.debit) > 0:
            source.revoke_transfer()
        warning = None
        if target.payment_date == original.value_date:
            warning = _reconcile(target, ledger, original.credit, booking, today)
        return booking, warning

    return _book_between(db, original.debit, original.credit, actor, book)


def donate(
    db: Database, account_number: int, value_date: date, today: date, actor: str, text: str | None = None
) -> BookingResult:
    """Ausscheiden mit Spende des Anteils (siehe Plan): ohne Kündigungsfrist, am Tag der Spende.

    Bucht das ganze Guthaben, Saldo und Anteile, vom Mitgliedskonto an das Genossenschaftskonto;
    danach steht das Konto auf 0, es bleibt kein Auseinandersetzungsanspruch. Am Mitglied wird die
    Spende festgehalten, beides wird zusammen gespeichert. Ein Storno der Buchung nimmt das
    Ausscheiden zurück.
    """

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        last_exit = ledger.last_exit_date(account)
        if last_exit is not None and value_date <= last_exit:
            raise DomainError(f"Das Datum muss nach dem gebuchten Ausscheiden zum {last_exit:%d.%m.%Y} liegen.")
        balance, shares = ledger.balance(account), ledger.shares(account)
        if balance == 0 and shares == 0:
            raise DomainError("Auf dem Konto ist nichts, was gespendet werden könnte.")
        member.donate_shares(value_date, today)
        return ledger.post_booking(
            SHARE_DONATION,
            account,
            COOPERATIVE_ACCOUNT_NUMBER,
            balance,
            shares,
            text or "Spende Anteil",
            value_date,
            today,
        )

    return _book(db, account_number, today, actor, book, reconcile=False)


def payout(
    db: Database,
    account_number: int,
    amount: int,
    value_date: date,
    today: date,
    actor: str,
    text: str | None = None,
) -> BookingResult:
    """Auszahlung des Auseinandersetzungsanspruchs, auch in Teilbeträgen.

    Ob ausgezahlt werden darf (Mindestkapital, Satzung 6.6), prüft die App nicht (siehe Plan).
    """
    return _reduce_claim(db, account_number, PAYOUT, amount, value_date, today, actor, text or "Auszahlung")


def deduct_loss(
    db: Database,
    account_number: int,
    amount: int,
    value_date: date,
    today: date,
    actor: str,
    text: str | None = None,
) -> BookingResult:
    """Kürzung des Anspruchs um einen anteiligen Verlustvortrag (Satzung 6.5)."""
    return _reduce_claim(
        db, account_number, LOSS_DEDUCTION, amount, value_date, today, actor, text or "Kürzung Verlustvortrag"
    )


def write_off(
    db: Database, account_number: int, value_date: date, today: date, actor: str, text: str | None = None
) -> BookingResult:
    """Ausbuchung des ganzen Restanspruchs wegen Verjährung (Satzung 2.7), Zuführung zur Rücklage.

    Die Verjährungsfrist überwacht die App nicht; das entscheidet die Buchhaltung.
    """
    return _reduce_claim(
        db, account_number, LIMITATION_WRITEOFF, None, value_date, today, actor, text or "Ausbuchung Verjährung"
    )


def _reduce_claim(
    db: Database,
    account_number: int,
    kind: str,
    amount: int | None,
    value_date: date,
    today: date,
    actor: str,
    text: str,
) -> BookingResult:
    """Gemeinsamer Ablauf für Buchungen, die den Anspruch mindern: Soll Mitgliedskonto an Haben
    Genossenschaftskonto, Betrag ohne Anteile. `amount` None heißt: der ganze Rest.

    Die Wertstellung muss nach dem gebuchten Ausscheiden liegen; so zeigt ein Report zu keinem
    Stichtag einen negativen Anspruch. Mit dem Geldeingang hat das nichts zu tun, daher kein Abgleich.
    """

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        claim = ledger.claim(account, share_price)
        if claim == 0:
            raise DomainError("Es gibt keinen offenen Auseinandersetzungsanspruch.")
        last_exit = ledger.last_exit_date(account)
        if last_exit is None:
            raise DomainError("Es ist noch kein Ausscheiden gebucht.")
        if value_date <= last_exit:
            raise DomainError(f"Die Wertstellung muss nach dem Ausscheiden zum {last_exit:%d.%m.%Y} liegen.")
        value = claim if amount is None else amount
        if value < 1:
            raise DomainError("Der Betrag muss größer als 0 sein.")
        if value > claim:
            raise DomainError(f"Der Betrag ist höher als der offene Anspruch von {format_euro(claim)}.")
        return ledger.post_booking(kind, account, COOPERATIVE_ACCOUNT_NUMBER, value, 0, text, value_date, today)

    return _book(db, account_number, today, actor, book, reconcile=False)


def member_account_of(booking: Booking) -> int:
    """Das Mitgliedskonto einer Buchung: die Seite, die nicht das Genossenschaftskonto ist.

    Die meisten Buchungen berühren genau ein Mitgliedskonto, die Gegenseite ist das
    Genossenschaftskonto. Bei der Umbuchung und ihrem Storno ist es das Sollkonto.
    """
    return booking.credit if booking.debit == COOPERATIVE_ACCOUNT_NUMBER else booking.debit


def _ensure_shares(shares: int) -> None:
    if shares < 1:
        raise DomainError("Es muss mindestens ein Anteil gebucht werden.")


def _book(
    db: Database, account_number: int, today: date, actor: str, book: BookAction, reconcile: bool = True
) -> BookingResult:
    """Gemeinsamer Ablauf: laden, prüfen, buchen, abgleichen, zusammen speichern.

    Das Konto wird über seine Nummer angesprochen; das Mitglied dazu steht im Hauptbuch.

    Hauptbuch und Mitglied werden mit `save_all` gespeichert, beides oder nichts. Hat jemand
    anderes in der Zwischenzeit gebucht, scheitert das Speichern an der Versionsprüfung, und es
    geht mit dem neuen Stand von vorn los, damit der Abgleich nie mit altem Kontostand rechnet.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        ledger = get_ledger(db)
        account = ledger.accounts.get(account_number)
        if account is None:
            raise NotFoundError(f"Das Konto {account_number} gibt es nicht.")
        if account.kind != MEMBER_ACCOUNT or account.member_id is None:
            raise DomainError(f"Konto {account_number} ist kein Mitgliedskonto.")
        member = get_member(db, account.member_id)
        share_price = get_system_settings(db).share_price
        if share_price is None:
            raise DomainError("Es ist noch kein Anteilspreis festgelegt.")
        if ledger.cooperative_account() is None:
            raise DomainError("Das Genossenschaftskonto fehlt.")
        booking = book(member, ledger, account.number, share_price)
        warning = _reconcile(member, ledger, account.number, booking, today) if reconcile else None
        try:
            db.save_all([ledger, member], actor)
        except ConcurrencyError:
            log.warning("booking conflict", extra={"account": account.number, "attempt": attempt})
            if attempt == MAX_ATTEMPTS:
                raise
            continue
        log.info(
            "booking posted",
            extra={
                "kind": booking.kind,
                "account": account.number,
                "shares": booking.shares,
                "warning": warning is not None,
                "actor": actor,
            },
        )
        return BookingResult(booking, warning)
    raise AssertionError("unreachable")  # die Schleife endet immer mit return oder raise


def _book_between(
    db: Database, debit_account: int, credit_account: int, actor: str, book: TransferAction
) -> BookingResult:
    """Wie `_book`, aber für eine Buchung zwischen zwei Mitgliedskonten (Umbuchung und ihr Storno).

    Hauptbuch und beide Mitglieder werden zusammen gespeichert, alles oder nichts.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        ledger = get_ledger(db)
        members: list[Member] = []
        for number in (debit_account, credit_account):
            account = ledger.accounts.get(number)
            if account is None:
                raise NotFoundError(f"Das Konto {number} gibt es nicht.")
            if account.kind != MEMBER_ACCOUNT or account.member_id is None:
                raise DomainError(f"Konto {number} ist kein Mitgliedskonto.")
            members.append(get_member(db, account.member_id))
        share_price = get_system_settings(db).share_price
        if share_price is None:
            raise DomainError("Es ist noch kein Anteilspreis festgelegt.")
        source, target = members
        booking, warning = book(source, target, ledger, share_price)
        try:
            db.save_all([ledger, source, target], actor)
        except ConcurrencyError:
            log.warning("booking conflict", extra={"account": debit_account, "attempt": attempt})
            if attempt == MAX_ATTEMPTS:
                raise
            continue
        log.info(
            "booking posted",
            extra={
                "kind": booking.kind,
                "account": debit_account,
                "target": credit_account,
                "shares": booking.shares,
                "warning": warning is not None,
                "actor": actor,
            },
        )
        return BookingResult(booking, warning)
    raise AssertionError("unreachable")


def _reconcile(member: Member, ledger: Ledger, account: int, booking: Booking, today: date) -> str | None:
    """Gleicht eingezahlte und gezeichnete Anteile ab (siehe Plan: Variante A).

    Stimmen sie nach der Buchung genau überein, wird der Geldeingang am Mitglied erfasst, mit der
    Wertstellung dieser Buchung. Sonst kommt eine Warnung zurück, der Vorgang ist zu klären.

    Nach einem Storno kann ein erfasster Geldeingang seine Grundlage verlieren; dann wird er
    zurückgenommen. Beides geschieht beim Storno nie still, sondern immer mit Warnung.
    """
    # Nur die Anteile aus dem Antrag zählen; eingezahlte weitere Anteile haben eigene Buchungen.
    paid = ledger.shares(account) - ledger.paid_additional_shares(account)
    subscribed = member.shares_subscribed
    if member.rejection_date is not None:
        if paid > 0:
            return "Der Antrag ist abgelehnt oder zurückgenommen; das Geld muss zurückgezahlt werden."
        return None
    if member.payment_date is not None:
        if paid == subscribed:
            return None
        was_member = member.entry_date() is not None
        member.revoke_payment()
        warning = f"Der Geldeingang ist zurückgenommen, {paid} von {subscribed} gezeichneten Anteilen eingezahlt."
        if was_member:
            warning += " Die Person ist nicht mehr Mitglied."
        return warning + " Bitte klären."
    if paid == subscribed:
        member.record_payment(booking.value_date, today)
        if booking.kind == REVERSAL:
            return f"Der Geldeingang ist jetzt mit Wertstellung {booking.value_date:%d.%m.%Y} erfasst. Bitte prüfen."
        return None
    if paid < subscribed:
        return f"{paid} von {subscribed} gezeichneten Anteilen eingezahlt."
    return f"Mehr Anteile eingezahlt als gezeichnet ({paid} von {subscribed}); bitte klären."
