import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from ..db import Database, get_db
from . import services
from .access import current_user
from .login_attempts import LoginAttempts
from .projections import UserView
from .schemas import LoginRequest, Me, UserOut
from .services import LoginLockedError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Annotated[Database, Depends(get_db)]) -> Me:
    """Meldet an; die Session bekommt die Benutzer-ID und ein neues CSRF-Token."""
    settings = request.app.state.settings
    attempts = LoginAttempts(db.projections.conn, settings.login_max_attempts, settings.login_lockout_seconds)
    try:
        user = services.authenticate(db, attempts, body.username, body.password)
    except LoginLockedError as exc:
        raise HTTPException(429, str(exc)) from exc
    if user is None:
        raise HTTPException(401, "Benutzername oder Kennwort falsch.")
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return _me(request, user)


@router.post("/logout", status_code=204)
def logout(request: Request, user: Annotated[UserView, Depends(current_user)]) -> None:
    request.session.clear()
    log.info("logout", extra={"user": user.id})


@router.get("/me")
def me(request: Request, user: Annotated[UserView, Depends(current_user)]) -> Me:
    """Wer ist angemeldet? Die Vue-App fragt das beim Start und nach dem Neuladen."""
    return _me(request, user)


def _me(request: Request, user: UserView) -> Me:
    return Me(user=UserOut.from_view(user), csrf_token=request.session["csrf_token"])
