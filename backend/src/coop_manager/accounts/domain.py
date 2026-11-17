import uuid
from dataclasses import dataclass
from datetime import date

from ..core import DomainError
from ..eventsource import Aggregate, Event, on

SUBJECT = "ledger"
MEMBER_ACCOUNT = "member_account"
COOPERATIVE_ACCOUNT = "cooperative_account"
# Das Konto der Genossenschaft hat immer diese Nummer, wie im Altsystem (siehe Plan).
COOPERATIVE_ACCOUNT_NUMBER = 9999

# Buchungsarten (siehe Plan: Buchungsarten). Was für die einzelne Art gilt, z. B. „Betrag =
# Anteile × Preis“ oder welche Konten erlaubt sind, prüfen die Vorgänge ab Schritt 5c.
SUBSCRIPTION = "subscription"  # Eintritt
REFUND = "refund"  # Rückzahlung
TRANSFER = "transfer"  # Umbuchung
EXIT = "exit"  # Ausscheiden
LOSS_DEDUCTION = "loss_deduction"  # Kürzung Verlustvortrag
PAYOUT = "payout"  # Auszahlung
LIMITATION_WRITEOFF = "limitation_writeoff"  # Ausbuchung Verjährung
REVERSAL = "reversal"  # Storno
BOOKING_KINDS = {SUBSCRIPTION, REFUND, TRANSFER, EXIT, LOSS_DEDUCTION, PAYOUT, LIMITATION_WRITEOFF, REVERSAL}


@dataclass(frozen=True)
class Account:
    """Ein Konto im Hauptbuch."""

    number: int
    kind: str  # MEMBER_ACCOUNT oder COOPERATIVE_ACCOUNT
    member_id: str | None = None  # nur bei Mitgliedskonten
    name: str | None = None  # nur beim Genossenschaftskonto


@dataclass(frozen=True)
class Booking:
    """Ein Buchungssatz: Betrag und Anteile gehen vom Soll- auf das Habenkonto.

    Auf dem Habenkonto zählen Betrag und Anteile positiv, auf dem Sollkonto negativ. Ein Eintritt
    bucht also Soll Genossenschaftskonto an Haben Mitgliedskonto.
    """

    id: str  # UUIDv7, z. B. als Referenz für ein Storno
    kind: str  # eine der BOOKING_KINDS
    debit: int  # Kontonummer Soll
    credit: int  # Kontonummer Haben
    amount: int  # Betrag in Cent
    shares: int  # Zahl der Anteile
    text: str
    booking_date: date  # Tag, an dem in der App gebucht wurde
    value_date: date  # Tag, an dem die Buchung fachlich gilt


class Ledger(Aggregate):
    """Das Hauptbuch mit allen Konten und Buchungen, als ein einziger Stream.

    Weil alles im selben Stream liegt, kann jede Änderung gegen den ganzen Bestand geprüft werden,
    und von zwei gleichzeitigen Änderungen scheitert die zweite an der Versionsprüfung
    (`ConcurrencyError`), wie bei `MemberNumbers`.
    """

    def __init__(self, subject: str = SUBJECT) -> None:
        """Leeres Hauptbuch; Konten und Buchungen setzen erst die Events."""
        super().__init__(subject)
        self.accounts: dict[int, Account] = {}  # Kontonummer → Konto
        self.bookings: list[Booking] = []  # in der Reihenfolge, in der gebucht wurde

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

    def post_booking(
        self,
        kind: str,
        debit: int,
        credit: int,
        amount: int,
        shares: int,
        text: str,
        value_date: date,
        booking_date: date,
    ) -> Booking:
        """Bucht Betrag (in Cent) und Anteile vom Soll- auf das Habenkonto.

        Prüft nur, was für jede Buchung gilt. `booking_date` ist der heutige Tag, er kommt als
        Parameter, damit Tests nicht vom Datum abhängen (wie `today` beim Mitglied).
        """
        if kind not in BOOKING_KINDS:
            raise DomainError(f"Unbekannte Buchungsart: {kind}")
        for number in (debit, credit):
            if number not in self.accounts:
                raise DomainError(f"Das Konto {number} gibt es nicht.")
        if debit == credit:
            raise DomainError("Soll- und Habenkonto müssen verschieden sein.")
        if amount < 0 or shares < 0:
            raise DomainError("Betrag und Anteile dürfen nicht negativ sein.")
        if amount == 0 and shares == 0:
            raise DomainError("Betrag oder Anteile müssen größer als 0 sein.")
        if not text.strip():
            raise DomainError("Der Buchungstext fehlt.")
        if value_date > booking_date:
            raise DomainError("Die Wertstellung darf nicht nach dem Buchungstag liegen.")
        if self.accounts[debit].kind == MEMBER_ACCOUNT:  # nur das Genossenschaftskonto darf negativ werden
            if self.balance(debit) < amount:
                raise DomainError(f"Der Saldo von Konto {debit} reicht nicht aus.")
            if self.shares(debit) < shares:
                raise DomainError(f"Konto {debit} hat nicht so viele Anteile.")
        booking_id = str(uuid.uuid7())
        self._record(
            "booking.posted",
            id=booking_id,
            kind=kind,
            debit=debit,
            credit=credit,
            amount=amount,
            shares=shares,
            text=text.strip(),
            booking_date=booking_date.isoformat(),
            value_date=value_date.isoformat(),
        )
        return self.bookings[-1]

    def balance(self, number: int) -> int:
        """Saldo des Kontos in Cent: Haben zählt positiv, Soll negativ."""
        total = 0
        for booking in self.bookings_of(number):
            total += booking.amount if booking.credit == number else -booking.amount
        return total

    def shares(self, number: int) -> int:
        """Anteile auf dem Konto: Haben zählt positiv, Soll negativ."""
        total = 0
        for booking in self.bookings_of(number):
            total += booking.shares if booking.credit == number else -booking.shares
        return total

    def bookings_of(self, number: int) -> list[Booking]:
        """Alle Buchungen, an denen das Konto im Soll oder Haben beteiligt ist."""
        return [b for b in self.bookings if number in (b.debit, b.credit)]

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

    @on("booking.posted")
    def _posted(self, event: Event) -> None:
        data = event.data
        booking = Booking(
            id=data["id"],
            kind=data["kind"],
            debit=data["debit"],
            credit=data["credit"],
            amount=data["amount"],
            shares=data["shares"],
            text=data["text"],
            booking_date=date.fromisoformat(data["booking_date"]),
            value_date=date.fromisoformat(data["value_date"]),
        )
        self.bookings.append(booking)
