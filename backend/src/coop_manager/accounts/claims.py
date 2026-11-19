"""Liste der offenen Auseinandersetzungsansprüche (siehe Plan: Auseinandersetzung, Schritt 5h-2).

Die App überwacht die Verjährung nicht (Satzung 2.7). Die Liste zeigt dafür alle offenen
Ansprüche mit dem Ausscheidensdatum, das älteste zuerst; ausgebucht wird von Hand.

Eigene Datei wie `exits.py`, weil sie Name und Status der Mitglieder braucht.
"""

from dataclasses import dataclass
from datetime import date

from ..db import Database
from ..members.addressing import list_name
from ..members.services import all_members
from ..system_settings.services import get_system_settings
from .services import get_ledger


@dataclass(frozen=True)
class ClaimEntry:
    """Ein Konto mit offenem Anspruch."""

    member_id: str
    member_number: int
    account_number: int
    name: str  # wie in Listen: „Nachname, Vornamen“ bzw. Firma
    status: str | None  # zum Tag der Abfrage
    exit_date: date  # letztes gebuchtes Ausscheiden
    claim: int  # offener Anspruch in Cent


def open_claims(db: Database, today: date) -> list[ClaimEntry]:
    """Alle Konten mit gebuchtem Ausscheiden und offenem Anspruch, das älteste Ausscheiden zuerst.

    Nur mit gebuchtem Ausscheiden: Ein echter Anspruch entsteht erst damit. Sänke der Anteilspreis,
    hätte sonst jedes Mitglied rechnerisch einen „Anspruch“ (siehe Plan).
    """
    ledger = get_ledger(db)
    share_price = get_system_settings(db).share_price
    entries: list[ClaimEntry] = []
    for member in all_members(db):
        account = ledger.account_of(member.subject)
        if account is None:
            continue
        exit_date = ledger.last_exit_date(account.number)
        claim = ledger.claim(account.number, share_price)
        if exit_date is None or claim == 0:
            continue
        entries.append(
            ClaimEntry(
                member_id=member.subject,
                member_number=member.member_number,
                account_number=account.number,
                name=list_name(member.person_type, member.name),
                status=member.status(today),
                exit_date=exit_date,
                claim=claim,
            )
        )
    # sorted ist stabil: Bei gleichem Datum bleibt die Reihenfolge nach Mitgliedsnummer.
    return sorted(entries, key=lambda e: e.exit_date)
