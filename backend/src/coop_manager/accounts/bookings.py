"""Fachliche Buchungsvorgänge: Eintritt und Rückzahlung, später Storno, Umbuchung usw.

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
from ..db import Database
from ..eventsource import ConcurrencyError
from ..members.domain import Member
from ..members.services import MAX_ATTEMPTS, get_member
from ..system_settings.services import get_system_settings
from .domain import COOPERATIVE_ACCOUNT_NUMBER, MEMBER_ACCOUNT, REFUND, REVERSAL, SUBSCRIPTION, Booking, Ledger
from .services import get_ledger

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookingResult:
    """Die gespeicherte Buchung und ggf. eine Warnung; die Buchung gilt auch mit Warnung."""

    booking: Booking
    warning: str | None = None


# Bucht auf dem geladenen Hauptbuch: (Mitglied, Hauptbuch, Kontonummer, Anteilspreis) → Buchung
BookAction = Callable[[Member, Ledger, int, int], Booking]


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
        if member.payment_date is not None or ledger.shares(account) >= member.shares_subscribed:
            raise DomainError("Die gezeichneten Anteile sind bereits eingezahlt.")
        assert member.application_date is not None  # gesetzt durch member.applied
        if value_date < member.application_date:
            raise DomainError("Die Wertstellung darf nicht vor dem Antrag liegen.")
        amount = shares * share_price
        return ledger.post_booking(
            SUBSCRIPTION, COOPERATIVE_ACCOUNT_NUMBER, account, amount, shares, text or "Eintritt", value_date, today
        )

    return _book(db, account_number, today, actor, book)


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
    account_number = member_account_of(original)

    def book(member: Member, ledger: Ledger, account: int, share_price: int) -> Booking:
        return ledger.reverse(booking_id, f"Storno zu „{original.text}“: {reason.strip()}", today)

    # Der Abgleich mit den gezeichneten Anteilen gehört nur zum Eintritt. Nach einem gebuchten
    # Ausscheiden passen gezeichnete und gehaltene Anteile nicht mehr zusammen; ein Abgleich würde
    # dann fälschlich den Geldeingang zurücknehmen.
    return _book(db, account_number, today, actor, book, reconcile=original.kind in (SUBSCRIPTION, REFUND))


def member_account_of(booking: Booking) -> int:
    """Das Mitgliedskonto einer Buchung: die Seite, die nicht das Genossenschaftskonto ist.

    Eintritt, Rückzahlung und ihr Storno berühren genau ein Mitgliedskonto, die Gegenseite ist das
    Genossenschaftskonto. Die Umbuchung zwischen zwei Mitgliedskonten kommt erst in 5h.
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


def _reconcile(member: Member, ledger: Ledger, account: int, booking: Booking, today: date) -> str | None:
    """Gleicht eingezahlte und gezeichnete Anteile ab (siehe Plan: Variante A).

    Stimmen sie nach der Buchung genau überein, wird der Geldeingang am Mitglied erfasst, mit der
    Wertstellung dieser Buchung. Sonst kommt eine Warnung zurück, der Vorgang ist zu klären.

    Nach einem Storno kann ein erfasster Geldeingang seine Grundlage verlieren; dann wird er
    zurückgenommen. Beides geschieht beim Storno nie still, sondern immer mit Warnung.
    """
    paid, subscribed = ledger.shares(account), member.shares_subscribed
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
