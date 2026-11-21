"""Abgleich nach dem Aufbau im Speicher und Bericht für die Ausgabe (siehe Plan: Ablauf)."""

from collections import Counter
from datetime import date

from ..accounts.domain import COOPERATIVE_ACCOUNT_NUMBER, Ledger
from ..core.money import format_euro
from ..members.status import STATUSES
from ..reports.services import BOOKING_LABELS
from .plan import MigrationPlan
from .run import Built
from .source import LegacyData


def compare(legacy: LegacyData, ledger: Ledger) -> list[str]:
    """Saldo und Anteile je Konto: alle alten Buchungen gegen das neue Hauptbuch.

    Gerechnet wird mit allen alten Buchungen, auch den übersprungenen. Die heben sich je Konto zu
    null auf (Notizen, Testbuchung, Widerruf); stimmt es trotzdem nicht, ist beim Überspringen
    etwas verloren gegangen. Konten übersprungener Personen gibt es neu nicht, sie zählen als 0.
    """
    balance: Counter[int] = Counter()
    shares: Counter[int] = Counter()
    for b in legacy.bookings:
        balance[b.credit] += b.amount
        balance[b.debit] -= b.amount
        shares[b.credit] += b.shares
        shares[b.debit] -= b.shares
    differences = []
    for number in sorted(balance.keys() | shares.keys() | ledger.accounts.keys()):
        old = (balance[number], shares[number])
        new = (ledger.balance(number), ledger.shares(number)) if number in ledger.accounts else (0, 0)
        if old != new:
            differences.append(
                f"Konto {number}: alt {format_euro(old[0])} / {old[1]} Anteile, "
                f"neu {format_euro(new[0])} / {new[1]} Anteile"
            )
    return differences


def summary(plan: MigrationPlan, built: Built, today: date) -> list[str]:
    """Kurzer Bericht in Zahlen; Nummern nur bei den übersprungenen Personen und Buchungen."""
    statuses = Counter(STATUSES.get(member.status(today) or "", "ohne Status") for member in built.members.values())
    kinds = Counter(b.kind for b in plan.bookings)
    coop = COOPERATIVE_ACCOUNT_NUMBER
    lines = [
        f"Personen: {len(plan.persons)} übernommen, {len(plan.skipped_persons)} übersprungen",
        "Status heute: " + ", ".join(f"{label} {n}" for label, n in sorted(statuses.items())),
        f"Buchungen: {len(plan.bookings)} übernommen, {len(plan.skipped_bookings)} übersprungen",
        "Buchungsarten: " + ", ".join(f"{BOOKING_LABELS[k]} {n}" for k, n in sorted(kinds.items())),
        f"Bestand: {-built.ledger.shares(coop)} Anteile, {format_euro(-built.ledger.balance(coop))}",
        f"Versionen der Historie: {sum(len(p.versions) for p in plan.persons)}",
        "Übersprungene Personen: " + (", ".join(map(str, plan.skipped_persons)) or "keine"),
        "Übersprungene Buchungen:" + ("" if plan.skipped_bookings else " keine"),
        *(f"  {booking_id}: {reason}" for booking_id, reason in plan.skipped_bookings),
    ]
    return lines
