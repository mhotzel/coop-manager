"""Ausscheiden zum Jahresende buchen (siehe Plan: Buchungsarten, Schritt 5g).

Nach dem 31.12. zeigt die Buchhaltung alle, die zu diesem Termin ausscheiden, und bucht nach
Bestätigung je Konto eine Ausscheidensbuchung: Betrag 0, die Anteile gehen vom Mitgliedskonto an
das Genossenschaftskonto. Der Saldo bleibt stehen, er ist der Auseinandersetzungsanspruch, der
später ausgezahlt wird (5h). Kein automatischer Lauf.

Ob schon gebucht ist, steht im Hauptbuch: eine nicht stornierte Ausscheidensbuchung des Kontos
mit Wertstellung zu diesem 31.12. Ein Storno macht das Ausscheiden also wieder offen.

Eigene Datei wie `bookings.py`, weil der Vorgang Mitglieder braucht (sonst Importzyklus).
"""

import logging
from dataclasses import dataclass
from datetime import date

from ..core import DomainError
from ..db import Database
from ..eventsource import ConcurrencyError
from ..members.addressing import list_name
from ..members.services import MAX_ATTEMPTS, all_members
from .domain import COOPERATIVE_ACCOUNT_NUMBER, EXIT, Ledger
from .services import get_ledger

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExitEntry:
    """Eine Zeile der Liste: ein Konto, das zum 31.12. Anteile abgibt."""

    member_id: str
    member_number: int
    account_number: int
    name: str  # wie in Listen: „Nachname, Vornamen“ bzw. Firma
    reasons: tuple[str, ...]  # siehe ExitDue; die Texte macht das Frontend
    full: bool  # alle Anteile, die Mitgliedschaft endet
    shares: int  # gebuchte bzw. zu buchende Anteile
    balance: int  # Saldo in Cent: der Auseinandersetzungsanspruch
    booked: bool


def exits_due(db: Database, year: int) -> list[ExitEntry]:
    """Alle, die zum 31.12. `year` ausscheiden, gebucht oder noch offen, nach Mitgliedsnummer."""
    return _entries(db, get_ledger(db), date(year, 12, 31))


def post_exits(db: Database, year: int, today: date, actor: str) -> list[ExitEntry]:
    """Bucht alle offenen Ausscheiden zum 31.12. `year`, alle zusammen oder keines.

    Nur für abgeschlossene Jahre: Erst danach steht fest, wer ausscheidet. Bis einschließlich
    31.12. lässt sich z. B. eine Kündigung noch zurücknehmen.
    """
    if year >= today.year:
        raise DomainError(f"Das Ausscheiden zum 31.12.{year} kann erst nach dem Jahresende gebucht werden.")
    day = date(year, 12, 31)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        ledger = get_ledger(db)
        if ledger.cooperative_account() is None:
            raise DomainError("Das Genossenschaftskonto fehlt.")
        open_entries = [e for e in _entries(db, ledger, day) if not e.booked]
        for entry in open_entries:
            ledger.post_booking(
                EXIT,
                debit=entry.account_number,
                credit=COOPERATIVE_ACCOUNT_NUMBER,
                amount=0,
                shares=entry.shares,
                text=f"Ausscheiden zum 31.12.{year}",
                value_date=day,
                booking_date=today,
            )
        try:
            db.save(ledger, actor)
        except ConcurrencyError:
            log.warning("exit posting conflict", extra={"year": year, "attempt": attempt})
            if attempt == MAX_ATTEMPTS:
                raise
            continue
        log.info("exits posted", extra={"year": year, "count": len(open_entries), "actor": actor})
        return _entries(db, ledger, day)
    raise AssertionError("unreachable")  # die Schleife endet immer mit return oder raise


def _entries(db: Database, ledger: Ledger, day: date) -> list[ExitEntry]:
    """Die Liste zum 31.12. `day`, berechnet aus Mitgliedern und Hauptbuch.

    Ein Konto ohne Anteile, z. B. nach einer Umbuchung auf Erben, hat nichts abzugeben und fehlt.
    """
    entries: list[ExitEntry] = []
    for member in all_members(db):
        due = member.exit_due(day)
        account = ledger.account_of(member.subject)
        if due is None or account is None:
            continue
        booking = ledger.exit_booking(account.number, day)
        if booking is not None:
            shares = booking.shares
        else:
            shares = ledger.shares(account.number) if due.full else due.partial_shares
        if shares == 0:
            continue
        entries.append(
            ExitEntry(
                member_id=member.subject,
                member_number=member.member_number,
                account_number=account.number,
                name=list_name(member.person_type, member.name),
                reasons=due.reasons,
                full=due.full,
                shares=shares,
                balance=ledger.balance(account.number),
                booked=booking is not None,
            )
        )
    return entries
