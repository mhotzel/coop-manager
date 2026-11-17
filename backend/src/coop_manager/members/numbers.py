from collections.abc import Collection

from ..accounts.domain import COOPERATIVE_ACCOUNT_NUMBER
from ..core import DomainError
from ..eventsource import Aggregate, Event, on

SUBJECT = "member-numbers"
# 9999 gehört dem Konto der Genossenschaft und wird nie an ein Mitglied vergeben (siehe Plan).
RESERVED = {COOPERATIVE_ACCOUNT_NUMBER}


class MemberNumbers(Aggregate):
    """Register aller vergebenen Mitgliedsnummern, als ein einziger Stream.

    Weil alle Vergaben im selben Stream landen, scheitert von zwei gleichzeitigen Vergaben die
    zweite an der Versionsprüfung des Event Stores (`ConcurrencyError`). So kann keine Nummer
    doppelt vergeben werden, auch wenn zwei Anträge im selben Moment erfasst werden.
    """

    def __init__(self, subject: str = SUBJECT) -> None:
        """Leeres Register; die vergebenen Nummern setzen erst die Events."""
        super().__init__(subject)
        self.assigned: dict[int, str] = {}  # Nummer → Mitglieds-ID

    def next_number(self, account_numbers: Collection[int] = ()) -> int:
        """Höchste vergebene Mitglieds- oder Kontonummer + 1 (siehe Plan: Nummernvergabe).

        `account_numbers` sind die Nummern der Mitgliedskonten aus dem Hauptbuch. Reservierte und
        belegte Nummern werden übersprungen. So sind Mitglieds- und Kontonummer gleich, solange
        keine abweichenden Nummern manuell vergeben wurden.
        """
        taken = set(self.assigned) | set(account_numbers)
        number = max(taken, default=0) + 1
        while number in RESERVED or number in taken:
            number += 1
        return number

    def assign(self, number: int, member_id: str) -> None:
        """Vergibt die Nummer an ein Mitglied; auch für manuell gewählte Nummern (Migration)."""
        if number < 1:
            raise DomainError("Die Mitgliedsnummer muss positiv sein.")
        if number in RESERVED:
            raise DomainError(f"Die Nummer {number} ist reserviert.")
        if number in self.assigned:
            raise DomainError(f"Die Mitgliedsnummer {number} ist bereits vergeben.")
        self._record("member-number.assigned", number=number, member_id=member_id)

    @on("member-number.assigned")
    def _assigned(self, event: Event) -> None:
        self.assigned[event.data["number"]] = event.data["member_id"]
