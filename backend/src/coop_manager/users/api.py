import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core import NotFoundError
from ..db import Database, get_db
from . import projections, services
from .access import current_user, require_role
from .domain import ADMIN, ROLES
from .login_attempts import LoginAttempts
from .projections import UserView
from .schemas import (
    ChangeFullName,
    ChangeOwnPassword,
    ChangePassword,
    ChangeRole,
    LoginRequest,
    Me,
    RegisterUser,
    RoleOut,
    UserCommand,
    UserOut,
)
from .services import LoginLockedError

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Kurzformen für die Parameter: die Datenbank und der angemeldete Admin.
Db = Annotated[Database, Depends(get_db)]
Admin = Annotated[UserView, Depends(require_role(ADMIN))]


# --- Anmeldung ---


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Db) -> Me:
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


@router.post("/me/change-password", status_code=204)
def change_own_password(body: ChangeOwnPassword, db: Db, user: Annotated[UserView, Depends(current_user)]) -> None:
    """Jeder Angemeldete darf sein eigenes Kennwort ändern; die Session bleibt bestehen."""
    services.change_own_password(db, user.id, body.current_password, body.new_password)


# --- Benutzerverwaltung (nur Admin): Abfragen ---


@router.get("/users")
def list_users(db: Db, admin: Admin) -> list[UserOut]:
    return [UserOut.from_view(user) for user in projections.list_users(db.projections.conn)]


# Muss vor /users/{user_id} stehen, sonst hielte FastAPI „roles“ für eine Benutzer-ID.
@router.get("/users/roles")
def list_roles(admin: Admin) -> list[RoleOut]:
    return [RoleOut(value=value, label=label) for value, label in ROLES.items()]


@router.get("/users/{user_id}")
def get_user(user_id: str, db: Db, admin: Admin) -> UserOut:
    return _user_out(db, user_id)


# --- Benutzerverwaltung (nur Admin): Befehle ---


@router.post("/users/register")
def register(body: RegisterUser, db: Db, admin: Admin) -> UserOut:
    user = services.register_user(db, body.username, body.full_name, body.password, body.role, actor=admin.id)
    return _user_out(db, user.subject)


@router.post("/users/change-full-name")
def change_full_name(body: ChangeFullName, db: Db, admin: Admin) -> UserOut:
    services.change_full_name(db, body.user_id, body.full_name, actor=admin.id)
    return _user_out(db, body.user_id)


@router.post("/users/change-role")
def change_role(body: ChangeRole, db: Db, admin: Admin) -> UserOut:
    services.change_role(db, body.user_id, body.role, actor=admin.id)
    return _user_out(db, body.user_id)


@router.post("/users/change-password")
def change_password(body: ChangePassword, db: Db, admin: Admin) -> UserOut:
    services.change_password(db, body.user_id, body.password, actor=admin.id)
    return _user_out(db, body.user_id)


@router.post("/users/deactivate")
def deactivate(body: UserCommand, db: Db, admin: Admin) -> UserOut:
    services.deactivate(db, body.user_id, actor=admin.id)
    return _user_out(db, body.user_id)


@router.post("/users/reactivate")
def reactivate(body: UserCommand, db: Db, admin: Admin) -> UserOut:
    services.reactivate(db, body.user_id, actor=admin.id)
    return _user_out(db, body.user_id)


@router.post("/users/terminate", status_code=204)
def terminate(body: UserCommand, db: Db, admin: Admin) -> None:
    """Löscht endgültig; danach gibt es den Benutzer nicht mehr, darum keine Antwort."""
    services.terminate(db, body.user_id, actor=admin.id)


def _me(request: Request, user: UserView) -> Me:
    return Me(user=UserOut.from_view(user), csrf_token=request.session["csrf_token"])


def _user_out(db: Database, user_id: str) -> UserOut:
    """Den Benutzer frisch aus der Projektion; die ist nach dem Speichern schon aktuell."""
    user = projections.get_user(db.projections.conn, user_id)
    if user is None:
        raise NotFoundError("Der Benutzer wurde nicht gefunden.")
    return UserOut.from_view(user)
