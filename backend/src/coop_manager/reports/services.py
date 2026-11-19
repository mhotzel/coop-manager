"""Abfragen für die Reports: wer zum Stichtag in einer Liste steht, mit welchen Anteilen.

Wie `accounts/claims.py` geht das über alle Mitglieder und das Hauptbuch. Bei einigen hundert
Mitgliedern ist das schnell genug; eine eigene Projektion wäre mehr Aufwand.
"""

from dataclasses import dataclass
from datetime import date

from ..accounts.domain import EXIT, Ledger
from ..accounts.services import get_ledger
from ..db import Database
from ..members.addressing import list_name
from ..members.domain import Member
from ..members.services import all_members
from ..members.status import DECEASED, EXPELLED, MEMBER, NOTICE_GIVEN
from ..system_settings.services import get_system_settings

# Wer eingetreten und zum Stichtag noch nicht ausgeschieden ist (siehe Plan: Reports).
LISTED_STATUSES = {MEMBER, NOTICE_GIVEN, DECEASED, EXPELLED}


@dataclass(frozen=True)
class GengRow:
    """Eine Zeile der Mitgliederliste nach GenG."""

    member_number: int
    name: str  # „Nachname, Vornamen“ bzw. Firma
    address: str  # einzeilig: „Straße Hausnummer, PLZ Ort“
    entry_date: date
    amount: int  # Anteile × Anteilspreis in Cent
    shares: int


def shares_on(ledger: Ledger, number: int, day: date) -> int:
    """Die Anteile des Kontos am Ende des Tages `day` (siehe Plan: Reports).

    Es zählen die Buchungen mit Wertstellung bis zum Stichtag. Stornierte Buchungen und ihre
    Stornos fallen ganz heraus; zusammen ergäben sie ohnehin 0. Ausnahme: Die Ausscheidensbuchung
    zum 31.12. wirkt erst ab dem 01.01., denn bis einschließlich 31.12. zählt die Person noch mit
    ihren Anteilen.
    """
    total = 0
    for booking in ledger.bookings_of(number):
        if booking.reverses is not None or ledger.reversal_of(booking.id) is not None:
            continue
        if booking.value_date > day or (booking.kind == EXIT and booking.value_date == day):
            continue
        total += booking.shares if booking.credit == number else -booking.shares
    return total


def members_geng(db: Database, day: date) -> list[GengRow]:
    """Mitgliederliste nach GenG zum Stichtag, nach Mitgliedsnummer.

    Ohne Anteile steht niemand in der Liste, etwa am Tag einer Spende des Anteils (siehe Plan).
    """
    ledger = get_ledger(db)
    share_price = get_system_settings(db).share_price or 0
    rows: list[GengRow] = []
    for member in all_members(db):
        entry_date = member.entry_date()
        account = ledger.account_of(member.subject)
        if member.status(day) not in LISTED_STATUSES or entry_date is None or account is None:
            continue
        shares = shares_on(ledger, account.number, day)
        if shares <= 0:
            continue
        rows.append(
            GengRow(
                member_number=member.member_number,
                name=list_name(member.person_type, member.name),
                address=one_line_address(member),
                entry_date=entry_date,
                amount=shares * share_price,
                shares=shares,
            )
        )
    return rows


def one_line_address(member: Member) -> str:
    """Anschrift in einer Zeile: „Straße Hausnummer, PLZ Ort“."""
    address = member.address
    return f"{address.street} {address.house_number}, {address.postal_code} {address.city}"
