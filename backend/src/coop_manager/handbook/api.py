"""Handbuch-API: liefert das Benutzerhandbuch an jeden angemeldeten Benutzer, gleich welche Rolle.

Das HTML erzeugt `Dokumentation/handbuch/handbuch.js` (siehe Plan). Es liegt im Paket statt unter
`frontend/public`, denn dort wäre es ohne Anmeldung abrufbar.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..users.access import current_user
from ..users.projections import UserView

HANDBOOK = Path(__file__).with_name("handbuch.html")

router = APIRouter(prefix="/api/help")


class Handbook(BaseModel):
    """Das Handbuch als HTML-Ausschnitt mit Inhaltsverzeichnis, ohne Seitenrahmen."""

    html: str


@router.get("")
def get_handbook(user: Annotated[UserView, Depends(current_user)]) -> Handbook:
    """Das Benutzerhandbuch; ohne Anmeldung 401."""
    return Handbook(html=HANDBOOK.read_text(encoding="utf-8"))
