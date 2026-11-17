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
from .domain import COOPERATIVE_ACCOUNT_NUMBER, MEMBER_ACCOUNT, REFUND, SUBSCRIPTION, Booking, Ledger
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

    return _book(db, account_number, shares, today, actor, book)


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

    return _book(db, account_number, shares, today, actor, book)


def _book(db: Database, account_number: int, shares: int, today: date, actor: str, book: BookAction) -> BookingResult:
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
        if shares < 1:
            raise DomainError("Es muss mindestens ein Anteil gebucht werden.")
        booking = book(member, ledger, account.number, share_price)
        warning = _reconcile(member, ledger, account.number, booking.value_date, today)
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


def _reconcile(member: Member, ledger: Ledger, account: int, value_date: date, today: date) -> str | None:
    """Gleicht eingezahlte und gezeichnete Anteile ab (siehe Plan: Variante A).

    Stimmen sie nach der Buchung genau überein, wird der Geldeingang am Mitglied erfasst, mit der
    Wertstellung dieser Buchung. Sonst kommt eine Warnung zurück, der Vorgang ist zu klären.
    """
    paid, subscribed = ledger.shares(account), member.shares_subscribed
    if member.rejection_date is not None:
        if paid > 0:
            return "Der Antrag ist abgelehnt oder zurückgenommen; das Geld muss zurückgezahlt werden."
        return None
    if member.payment_date is not None:
        return None
    if paid == subscribed:
        member.record_payment(value_date, today)
        return None
    if paid < subscribed:
        return f"{paid} von {subscribed} gezeichneten Anteilen eingezahlt."
    return f"Mehr Anteile eingezahlt als gezeichnet ({paid} von {subscribed}); bitte klären."
