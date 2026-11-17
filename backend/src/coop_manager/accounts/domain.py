from dataclasses import dataclass

from ..core import DomainError
from ..eventsource import Aggregate, Event, on

SUBJECT = "ledger"
MEMBER_ACCOUNT = "member_account"
COOPERATIVE_ACCOUNT = "cooperative_account"
# Das Konto der Genossenschaft hat immer diese Nummer, wie im Altsystem (siehe Plan).
COOPERATIVE_ACCOUNT_NUMBER = 9999


@dataclass(frozen=True)
class Account:
    """Ein Konto im Hauptbuch."""

    number: int
    kind: str  # MEMBER_ACCOUNT oder COOPERATIVE_ACCOUNT
    member_id: str | None = None  # nur bei Mitgliedskonten
    name: str | None = None  # nur beim Genossenschaftskonto


class Ledger(Aggregate):
    """Das Hauptbuch mit allen Konten (und ab Teil 2 allen Buchungen), als ein einziger Stream.

    Weil alles im selben Stream liegt, kann jede Änderung gegen den ganzen Bestand geprüft werden,
    und von zwei gleichzeitigen Änderungen scheitert die zweite an der Versionsprüfung
    (`ConcurrencyError`), wie bei `MemberNumbers`.
    """

    def __init__(self, subject: str = SUBJECT) -> None:
        """Leeres Hauptbuch; die Konten setzen erst die Events."""
        super().__init__(subject)
        self.accounts: dict[int, Account] = {}  # Kontonummer → Konto

    def open_member_account(self, number: int, member_id: str) -> None:
        """Eröffnet das Konto eines Mitglieds; das geschieht schon mit dem Antrag (siehe Plan)."""
        if number < 1:
            raise DomainError("Die Kontonummer muss positiv sein.")
        if number == COOPERATIVE_ACCOUNT_NUMBER:
            raise DomainError(f"Die Kontonummer {number} gehört der Genossenschaft.")
        if number in self.accounts:
            raise DomainError(f"Die Kontonummer {number} ist bereits vergeben.")
        if self.account_of(member_id) is not None:
            raise DomainError("Das Mitglied hat bereits ein Konto.")
        self._record("account.opened", number=number, kind=MEMBER_ACCOUNT, member_id=member_id, name=None)

    def open_cooperative_account(self, name: str) -> None:
        """Eröffnet das Konto der Genossenschaft; das gibt es genau einmal."""
        if not name.strip():
            raise DomainError("Das Genossenschaftskonto braucht eine Bezeichnung.")
        if self.cooperative_account() is not None:
            raise DomainError("Das Genossenschaftskonto gibt es bereits.")
        self._record(
            "account.opened",
            number=COOPERATIVE_ACCOUNT_NUMBER,
            kind=COOPERATIVE_ACCOUNT,
            member_id=None,
            name=name.strip(),
        )

    def cooperative_account(self) -> Account | None:
        """Das Konto der Genossenschaft, erkannt an der Kontoart; None, solange es fehlt."""
        return next((a for a in self.accounts.values() if a.kind == COOPERATIVE_ACCOUNT), None)

    def account_of(self, member_id: str) -> Account | None:
        """Das Konto des Mitglieds; None, wenn es keines hat."""
        return next((a for a in self.accounts.values() if a.member_id == member_id), None)

    def member_account_numbers(self) -> set[int]:
        """Die Nummern aller Mitgliedskonten, für die Nummernvergabe."""
        return {a.number for a in self.accounts.values() if a.kind == MEMBER_ACCOUNT}

    @on("account.opened")
    def _opened(self, event: Event) -> None:
        account = Account(
            number=event.data["number"],
            kind=event.data["kind"],
            member_id=event.data["member_id"],
            name=event.data["name"],
        )
        self.accounts[account.number] = account
