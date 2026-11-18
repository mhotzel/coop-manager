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
    claim: int  # offener Auseinandersetzungsanspruch in Cent: Saldo minus Anteile × Preis
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
            claim=ledger.claim(number, share_price),
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


# Plausible Jahre; ohne Grenze ergäbe z. B. Jahr 0 kein gültiges Datum und einen Serverfehler.
YEAR_MIN, YEAR_MAX = 1900, 2200


class ClaimBooking(BaseModel):
    """Befehl: Auszahlung oder Kürzung um Verlustvortrag; Betrag frei, höchstens der Anspruch."""

    account_number: int
    amount: int  # in Cent
    value_date: date
    text: str | None = Field(default=None, max_length=200)  # leer = „Auszahlung“ bzw. „Kürzung …“


class WriteOff(BaseModel):
    """Befehl: Ausbuchung wegen Verjährung; der Betrag ist immer der ganze Rest."""

    account_number: int
    value_date: date
    text: str | None = Field(default=None, max_length=200)


class PostExits(BaseModel):
    """Befehl: alle offenen Ausscheiden zum 31.12. dieses Jahres buchen."""

    year: int = Field(ge=YEAR_MIN, le=YEAR_MAX)


class ReverseBooking(BaseModel):
    """Befehl: Storno einer Buchung. Der Grund ist Pflicht und kommt in den Buchungstext."""

    booking_id: str
    reason: str = Field(max_length=200)
