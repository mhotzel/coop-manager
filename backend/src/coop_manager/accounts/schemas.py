"""Pydantic-Modelle der Konten-API: was hereinkommt und was hinausgeht. Beträge in Cent."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .domain import Booking, Ledger


class AccountView(BaseModel):
    """Die Kontoansicht: Konto, berechneter Saldo und Anteile, alle Buchungen."""

    number: int
    kind: str  # MEMBER_ACCOUNT oder COOPERATIVE_ACCOUNT
    member_id: str | None  # Inhaber; beim Genossenschaftskonto None
    # Berechnet, nicht gespeichert:
    balance: int  # Saldo in Cent, Haben positiv
    shares: int
    share_price: int | None  # aktueller Anteilspreis in Cent, für die Buchungsmaske
    bookings: list[Booking]  # in der Reihenfolge, in der gebucht wurde

    @classmethod
    def from_ledger(cls, ledger: Ledger, number: int, share_price: int | None) -> AccountView:
        """Baut die Ansicht eines Kontos aus dem Hauptbuch; das Konto muss existieren."""
        account = ledger.accounts[number]
        return cls(
            number=account.number,
            kind=account.kind,
            member_id=account.member_id,
            balance=ledger.balance(number),
            shares=ledger.shares(number),
            share_price=share_price,
            bookings=ledger.bookings_of(number),
        )


class BookingResponse(BaseModel):
    """Antwort auf einen Buchungsbefehl: das Konto danach und ggf. eine Warnung."""

    account: AccountView
    warning: str | None


# --- Befehle: je einer pro fachlichem Vorgang, alle Daten im Body ---


class ShareBooking(BaseModel):
    """Befehl: Eintritt oder Rückzahlung. Den Betrag berechnet der Service (Anteile × Preis)."""

    account_number: int
    shares: int
    value_date: date
    text: str | None = Field(default=None, max_length=200)  # leer = „Eintritt“ bzw. „Rückzahlung“


class ReverseBooking(BaseModel):
    """Befehl: Storno einer Buchung. Der Grund ist Pflicht und kommt in den Buchungstext."""

    booking_id: str
    reason: str = Field(max_length=200)
