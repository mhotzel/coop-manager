"""Konten-API: Kontoansicht zum Lesen, je ein Endpunkt pro fachlichem Buchungsvorgang.

Einen Endpunkt für freie Buchungen gibt es bewusst nicht (siehe Plan): Jeder Vorgang prüft im
Service seine eigenen Regeln. Jeder Befehl antwortet mit der Kontoansicht und ggf. einer Warnung.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from ..core import NotFoundError
from ..db import Database, get_db
from ..system_settings.services import get_system_settings
from ..users.access import require_role
from ..users.domain import ACCOUNTING, ACCOUNTING_READONLY
from ..users.projections import UserView
from . import bookings
from .bookings import BookingResult
from .schemas import AccountView, BookingResponse, ShareBooking
from .services import get_ledger

router = APIRouter(prefix="/api/accounts")

# Kurzformen für die Parameter: Lesen dürfen beide Buchhaltungsrollen, buchen nur die Buchhaltung.
Db = Annotated[Database, Depends(get_db)]
Reader = Annotated[UserView, Depends(require_role(ACCOUNTING, ACCOUNTING_READONLY))]
Writer = Annotated[UserView, Depends(require_role(ACCOUNTING))]


# --- Abfragen ---


@router.get("/{number}")
def get_account(number: int, db: Db, user: Reader) -> AccountView:
    """Ein Konto mit Saldo, Anteilen und Buchungen; 404, wenn es die Nummer nicht gibt."""
    return _view(db, number)


# --- Befehle ---


@router.post("/subscribe")
def subscribe(body: ShareBooking, db: Db, user: Writer) -> BookingResponse:
    """Eintritt: Geldeingang für gezeichnete Anteile."""
    result = bookings.subscribe(
        db, body.account_number, body.shares, body.value_date, date.today(), actor=user.id, text=body.text
    )
    return _response(db, body.account_number, result)


@router.post("/refund")
def refund(body: ShareBooking, db: Db, user: Writer) -> BookingResponse:
    """Rückzahlung bei abgelehntem Antrag oder ungeklärter Zahlung."""
    result = bookings.refund(
        db, body.account_number, body.shares, body.value_date, date.today(), actor=user.id, text=body.text
    )
    return _response(db, body.account_number, result)


def _view(db: Database, number: int) -> AccountView:
    """Die Kontoansicht mit dem aktuellen Anteilspreis."""
    ledger = get_ledger(db)
    if number not in ledger.accounts:
        raise NotFoundError(f"Das Konto {number} gibt es nicht.")
    return AccountView.from_ledger(ledger, number, get_system_settings(db).share_price)


def _response(db: Database, number: int, result: BookingResult) -> BookingResponse:
    """Das Konto nach der Buchung und die Warnung des Vorgangs."""
    return BookingResponse(account=_view(db, number), warning=result.warning)
