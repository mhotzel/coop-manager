import logging
from collections.abc import Callable
from functools import cache

from ..core import DomainError, NotFoundError
from ..db import Database
from . import projections
from .domain import ADMIN, User, hash_password, normalize_username, verify_password
from .login_attempts import LoginAttempts
from .projections import UserView

log = logging.getLogger(__name__)


class LoginLockedError(DomainError):
    """Zu viele Fehlversuche für diesen Benutzernamen."""


def register_user(db: Database, username: str, full_name: str, password: str, role: str, actor: str) -> User:
    """Legt einen Benutzer an; der Benutzername muss noch frei sein."""
    if projections.find_by_username(db.projections.conn, normalize_username(username)):
        raise DomainError(f"Der Benutzername '{normalize_username(username)}' ist bereits vergeben.")
    user = User.register(username, full_name, password, role)
    db.save(user, actor)
    log.info("user registered", extra={"user": user.subject, "username": user.username, "actor": actor})
    return user


def change_full_name(db: Database, user_id: str, full_name: str, actor: str) -> User:
    return _change(db, user_id, actor, lambda user: user.change_full_name(full_name))


def change_password(db: Database, user_id: str, password: str, actor: str) -> User:
    return _change(db, user_id, actor, lambda user: user.change_password(password))


def change_own_password(db: Database, user_id: str, current_password: str, new_password: str) -> User:
    """Der angemeldete Benutzer ändert sein Kennwort; dafür muss er das bisherige kennen.

    So kann niemand an einem kurz verlassenen, angemeldeten Rechner das Kennwort ändern.
    Fehlversuche zählen nicht für die Login-Sperre, werden aber geloggt.
    """

    def change(user: User) -> None:
        if not user.check_password(current_password):
            log.warning("wrong current password", extra={"user": user_id})
            raise DomainError("Das bisherige Kennwort ist falsch.")
        user.change_password(new_password)

    return _change(db, user_id, user_id, change)


def change_role(db: Database, user_id: str, role: str, actor: str) -> User:
    if user_id == actor and role != ADMIN:
        raise DomainError("Du kannst dir die Admin-Rolle nicht selbst entziehen.")
    return _change(db, user_id, actor, lambda user: user.change_role(role))


def deactivate(db: Database, user_id: str, actor: str) -> User:
    if user_id == actor:
        raise DomainError("Du kannst dich nicht selbst deaktivieren.")
    return _change(db, user_id, actor, User.deactivate)


def reactivate(db: Database, user_id: str, actor: str) -> User:
    return _change(db, user_id, actor, User.reactivate)


def terminate(db: Database, user_id: str, actor: str) -> User:
    if user_id == actor:
        raise DomainError("Du kannst dich nicht selbst löschen.")
    return _change(db, user_id, actor, User.terminate)


def authenticate(db: Database, attempts: LoginAttempts, username: str, password: str) -> UserView | None:
    """Liefert den Benutzer bei richtigen Zugangsdaten, sonst None.

    Solange der Benutzername nach zu vielen Fehlversuchen gesperrt ist, kommt `LoginLockedError`.
    Unbekannte und deaktivierte Benutzer werden behandelt wie ein falsches Kennwort.
    """
    username = normalize_username(username)
    if attempts.is_locked(username):
        log.warning("login while locked", extra={"username": username})
        raise LoginLockedError("Zu viele fehlgeschlagene Anmeldeversuche. Bitte versuche es später noch einmal.")

    user = projections.find_by_username(db.projections.conn, username)
    if user is None or not user.active:
        verify_password(password, _dummy_hash())  # gleich lange Antwortzeit wie bei vorhandenen Benutzern
        valid = False
    else:
        valid = verify_password(password, user.password_hash)

    if user is None or not valid:
        attempts.record_failure(username)
        log.warning("login failed", extra={"username": username})
        return None
    attempts.reset(username)
    log.info("login", extra={"user": user.id, "username": username})
    return user


def _change(db: Database, user_id: str, actor: str, action: Callable[[User], None]) -> User:
    """Lädt den Benutzer, führt die Änderung aus und speichert die neuen Events."""
    user = db.store.load(User, user_id)
    if user is None or user.terminated:
        raise NotFoundError("Der Benutzer wurde nicht gefunden.")
    action(user)
    db.save(user, actor)
    log.info("user changed", extra={"user": user_id, "actor": actor, "version": user.version})
    return user


@cache
def _dummy_hash() -> str:
    """Einmal berechneter Hash, gegen den bei unbekannten Benutzern geprüft wird."""
    return hash_password("Dummy-Kennwort-1")
