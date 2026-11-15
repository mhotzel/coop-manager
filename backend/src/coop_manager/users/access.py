"""Zugriffsprüfung: Wer ist angemeldet, und darf er das?

Jeder Endpunkt außer den öffentlichen (siehe `PUBLIC_PATHS`) muss `current_user` oder
`require_role(...)` als Dependency verwenden. Ein Test prüft das für alle Routen.
"""

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from ..db import Database, get_db
from . import projections
from .projections import UserView

PUBLIC_PATHS = {"/healthz", "/api/login"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "X-CSRF-Token"


def current_user(request: Request, db: Annotated[Database, Depends(get_db)]) -> UserView:
    """Der angemeldete Benutzer, bei jeder Anfrage frisch aus der Projektion gelesen.

    So wirken Deaktivieren und Rollenwechsel sofort. Bei schreibenden Anfragen muss außerdem
    das CSRF-Token im Header stimmen.
    """
    user_id = request.session.get("user_id")
    user = projections.get_user(db.projections.conn, user_id) if user_id else None
    if user is None or not user.active:
        request.session.clear()
        raise HTTPException(401, "Bitte melde dich an.")
    if request.method in UNSAFE_METHODS and not _csrf_token_valid(request):
        raise HTTPException(403, "Die Anfrage ist ungültig. Bitte lade die Seite neu.")
    return user


def require_role(*roles: str) -> Callable[..., UserView]:
    """Dependency, die nur Benutzer mit einer der genannten Rollen durchlässt."""

    def check(user: Annotated[UserView, Depends(current_user)]) -> UserView:
        if user.role not in roles:
            raise HTTPException(403, "Dafür fehlt dir die Berechtigung.")
        return user

    return check


def _csrf_token_valid(request: Request) -> bool:
    expected = request.session.get("csrf_token", "")
    given = request.headers.get(CSRF_HEADER, "")
    # compare_digest braucht für jeden Vergleich gleich lange,
    # so lässt sich das Token nicht Zeichen für Zeichen erraten.
    return bool(expected) and secrets.compare_digest(expected, given)
