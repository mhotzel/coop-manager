"""Reports-API: liefert die Listen als Excel-Datei zum Herunterladen."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from ..accounts import balances
from ..accounts.schemas import YEAR_MAX, YEAR_MIN
from ..db import Database, get_db
from ..users.access import require_role
from ..users.domain import ACCOUNTING, ACCOUNTING_READONLY
from ..users.projections import UserView
from . import excel, services

router = APIRouter(prefix="/api/reports")

Db = Annotated[Database, Depends(get_db)]
Reader = Annotated[UserView, Depends(require_role(ACCOUNTING, ACCOUNTING_READONLY))]

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/warnings")
def warnings(reference_date: date, db: Db, user: Reader) -> list[str]:
    """Hinweise zum Stichtag für die Seite „Reports“, z. B. ein noch nicht gebuchtes Ausscheiden."""
    return services.warnings(db, reference_date)


@router.get("/members-geng")
def members_geng(reference_date: date, db: Db, user: Reader) -> Response:
    """Mitgliederliste nach GenG zum Stichtag, z. B. `?reference_date=2026-12-31`."""
    content = excel.members_geng(
        services.members_geng(db, reference_date), reference_date, services.warnings(db, reference_date)
    )
    return _xlsx(content, f"Mitgliederliste-GenG-{reference_date.isoformat()}.xlsx")


@router.get("/members-assembly")
def members_assembly(reference_date: date, db: Db, user: Reader) -> Response:
    """Liste zur Generalversammlung zum Stichtag (Tag der Versammlung)."""
    content = excel.members_assembly(
        services.members_assembly(db, reference_date), reference_date, services.warnings(db, reference_date)
    )
    return _xlsx(content, f"Generalversammlung-{reference_date.isoformat()}.xlsx")


@router.get("/members-mailing")
def members_mailing(reference_date: date, db: Db, user: Reader) -> Response:
    """Seriendruck-Liste zum Stichtag, z. B. für die Einladung zur Generalversammlung."""
    content = excel.members_mailing(services.members_mailing(db, reference_date), reference_date)
    return _xlsx(content, f"Seriendruck-{reference_date.isoformat()}.xlsx")


@router.get("/account-balances")
def account_balances(reference_date: date, db: Db, user: Reader, include_zero: bool = False) -> Response:
    """Saldenliste zum Stichtag; ohne `include_zero` nur Konten mit Saldo ≠ 0."""
    content = excel.account_balances(balances.account_balances(db, reference_date, include_zero))
    return _xlsx(content, f"Saldenliste-{reference_date.isoformat()}.xlsx")


@router.get("/fiscal-year-events")
def fiscal_year_events(fiscal_year: Annotated[int, Query(ge=YEAR_MIN, le=YEAR_MAX)], db: Db, user: Reader) -> Response:
    """Auswertung der Vorgänge eines Geschäftsjahres, z. B. `?fiscal_year=2025`."""
    content = excel.fiscal_year_events(services.fiscal_year_events(db, fiscal_year), fiscal_year)
    return _xlsx(content, f"Vorgaenge-{fiscal_year}.xlsx")


def _xlsx(content: bytes, filename: str) -> Response:
    # attachment: Der Browser speichert die Datei, statt sie anzuzeigen.
    return Response(content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
