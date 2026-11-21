"""Saldenliste: das Guthaben jedes Mitgliedskontos gegenüber der Genossenschaft zu einem Stichtag.

Die Summe aller Salden ist das Gegenstück zum Genossenschaftskonto; die Liste stimmt beides ab
(siehe Plan: Saldenliste). Eigene Datei wie `claims.py`, weil sie Name und Status der Mitglieder
braucht.
"""

from dataclasses import dataclass
from datetime import date

from ..db import Database
from ..members.addressing import list_name
from ..members.services import all_members
from ..members.status import EXITED
from ..system_settings.services import get_system_settings
from .domain import COOPERATIVE_ACCOUNT_NUMBER, EXIT, Booking, Ledger
from .services import get_ledger


@dataclass(frozen=True)
class BalanceEntry:
    """Ein Mitgliedskonto zum Stichtag; Beträge in Cent."""

    member_id: str
    member_number: int
    account_number: int
    name: str  # wie in Listen: „Nachname, Vornamen“ bzw. Firma
    status: str | None  # zum Stichtag
    shares: int
    balance: int  # Saldo: das ganze Guthaben gegenüber der Genossenschaft
    share_capital: int  # davon Geschäftsguthaben: Anteile × Anteilspreis
    claim: int  # davon Auseinandersetzungsanspruch: Saldo − Geschäftsguthaben
    exit_not_booked: bool  # zum Stichtag ausgeschieden, aber noch Anteile: Seite „Jahresende“


@dataclass(frozen=True)
class BalanceList:
    """Die Saldenliste mit Summen und Abstimmung gegen das Genossenschaftskonto."""

    day: date
    entries: list[BalanceEntry]
    total_shares: int
    total_balance: int
    total_share_capital: int
    total_claim: int
    cooperative_balance: int  # Saldo des Genossenschaftskontos, normalerweise −total_balance
    balanced: bool  # Summe der Mitgliedskonten + Genossenschaftskonto = 0


def account_balances(db: Database, day: date, include_zero: bool = False) -> BalanceList:
    """Alle Mitgliedskonten zum Stichtag, nach Mitgliedsnummer; ohne `include_zero` nur Saldo ≠ 0.

    Es zählen alle Personen mit Konto, auch Antragsteller und Ausgeschiedene: Wer Geld auf dem
    Konto hat, hat einen Anspruch gegen die Genossenschaft. Die Summen gehen immer über alle Konten.
    """
    ledger = get_ledger(db)
    share_price = get_system_settings(db).share_price or 0
    entries: list[BalanceEntry] = []
    for member in all_members(db):
        account = ledger.account_of(member.subject)
        if account is None:
            continue
        shares = shares_on(ledger, account.number, day)
        balance = balance_on(ledger, account.number, day)
        status = member.status(day)
        entries.append(
            BalanceEntry(
                member_id=member.subject,
                member_number=member.member_number,
                account_number=account.number,
                name=list_name(member.person_type, member.name),
                status=status,
                shares=shares,
                balance=balance,
                share_capital=shares * share_price,
                claim=balance - shares * share_price,
                exit_not_booked=status == EXITED and shares > 0,
            )
        )
    total_balance = sum(e.balance for e in entries)
    cooperative_balance = balance_on(ledger, COOPERATIVE_ACCOUNT_NUMBER, day)
    return BalanceList(
        day=day,
        entries=[e for e in entries if include_zero or e.balance != 0],
        total_shares=sum(e.shares for e in entries),
        total_balance=total_balance,
        total_share_capital=sum(e.share_capital for e in entries),
        total_claim=sum(e.claim for e in entries),
        cooperative_balance=cooperative_balance,
        balanced=total_balance + cooperative_balance == 0,
    )


def shares_on(ledger: Ledger, number: int, day: date) -> int:
    """Die Anteile des Kontos am Ende des Tages `day` (siehe Plan: Reports).

    Es zählen die Buchungen mit Wertstellung bis zum Stichtag. Stornierte Buchungen und ihre
    Stornos fallen ganz heraus; zusammen ergäben sie ohnehin 0. Ausnahme: Die Ausscheidensbuchung
    zum 31.12. wirkt erst ab dem 01.01., denn bis einschließlich 31.12. zählt die Person noch mit
    ihren Anteilen.
    """
    total = 0
    for booking in _counted(ledger, number, day):
        if booking.kind == EXIT and booking.value_date == day:
            continue
        total += booking.shares if booking.credit == number else -booking.shares
    return total


def balance_on(ledger: Ledger, number: int, day: date) -> int:
    """Der Saldo des Kontos in Cent am Ende des Tages `day`: Haben positiv, Soll negativ.

    Dieselben Buchungen wie bei `shares_on`. Die Ausscheidensbuchung bewegt nur Anteile, kein Geld,
    deshalb braucht es ihre Ausnahme hier nicht.
    """
    total = 0
    for booking in _counted(ledger, number, day):
        total += booking.amount if booking.credit == number else -booking.amount
    return total


def _counted(ledger: Ledger, number: int, day: date) -> list[Booking]:
    """Buchungen des Kontos mit Wertstellung bis `day`, ohne stornierte Buchungen und ihre Stornos."""
    return [
        b
        for b in ledger.bookings_of(number)
        if b.value_date <= day and b.reverses is None and ledger.reversal_of(b.id) is None
    ]
