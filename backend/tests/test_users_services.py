from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError, NotFoundError
from coop_manager.db import Database, prepare
from coop_manager.users import projections, services
from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY, ADMIN
from coop_manager.users.login_attempts import LoginAttempts
from coop_manager.users.services import LoginLockedError

PASSWORD = "Geheim-123"


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    yield db
    db.close()


@pytest.fixture
def attempts(db) -> LoginAttempts:
    return LoginAttempts(db.projections.conn, max_attempts=3, lockout_seconds=900)


def register(db: Database, username: str = "erika", role: str = ACCOUNTING) -> str:
    """Legt einen erfundenen Benutzer an und liefert seine ID."""
    return services.register_user(db, username, "Erika Muster", PASSWORD, role, actor="test").subject


def view(db: Database, user_id: str) -> projections.UserView | None:
    return projections.get_user(db.projections.conn, user_id)


# --- Projektion ---


def test_registered_user_appears_in_projection(db):
    user_id = register(db)

    user = view(db, user_id)
    assert user is not None
    assert (user.username, user.full_name, user.role, user.active) == ("erika", "Erika Muster", ACCOUNTING, True)


def test_changes_appear_in_projection(db):
    user_id = register(db)

    services.change_full_name(db, user_id, "Erika Beispiel", actor="test")
    services.change_role(db, user_id, ACCOUNTING_READONLY, actor="test")
    services.deactivate(db, user_id, actor="test")

    user = view(db, user_id)
    assert user is not None
    assert (user.full_name, user.role, user.active) == ("Erika Beispiel", ACCOUNTING_READONLY, False)


def test_terminated_user_disappears_from_projection(db):
    user_id = register(db)
    services.deactivate(db, user_id, actor="test")

    services.terminate(db, user_id, actor="test")

    assert view(db, user_id) is None
    assert projections.list_users(db.projections.conn) == []


def test_list_users_is_sorted_by_username(db):
    register(db, "max")
    register(db, "anna")

    assert [u.username for u in projections.list_users(db.projections.conn)] == ["anna", "max"]


def test_rebuild_restores_projection(db):
    user_id = register(db)
    services.change_role(db, user_id, ADMIN, actor="test")
    before = view(db, user_id)

    db.projections.rebuild(db.store)

    assert view(db, user_id) == before


# --- Services ---


def test_username_must_be_unique_regardless_of_case(db):
    register(db, "erika")

    with pytest.raises(DomainError, match="bereits vergeben"):
        register(db, " Erika ")


def test_events_record_the_actor(db):
    user_id = register(db)

    assert [event.actor for event in db.store.read_stream(user_id)] == ["test"]


def test_change_unknown_user_raises_not_found(db):
    with pytest.raises(NotFoundError):
        services.reactivate(db, "user-unbekannt", actor="test")


def test_admin_cannot_remove_own_admin_role(db):
    admin_id = register(db, role=ADMIN)

    with pytest.raises(DomainError, match="Admin-Rolle"):
        services.change_role(db, admin_id, ACCOUNTING, actor=admin_id)


def test_cannot_deactivate_or_terminate_oneself(db):
    user_id = register(db, role=ADMIN)

    with pytest.raises(DomainError, match="nicht selbst deaktivieren"):
        services.deactivate(db, user_id, actor=user_id)
    with pytest.raises(DomainError, match="nicht selbst löschen"):
        services.terminate(db, user_id, actor=user_id)


def test_change_own_password(db, attempts):
    user_id = register(db)

    services.change_own_password(db, user_id, PASSWORD, "Neu-Geheim-456")

    assert services.authenticate(db, attempts, "erika", "Neu-Geheim-456") is not None
    assert [event.actor for event in db.store.read_stream(user_id)] == ["test", user_id]


def test_change_own_password_needs_current_password(db):
    user_id = register(db)

    with pytest.raises(DomainError, match="bisherige Kennwort ist falsch"):
        services.change_own_password(db, user_id, "Falsch-123", "Neu-Geheim-456")
    assert len(db.store.read_stream(user_id)) == 1  # nichts gespeichert


# --- Login ---


def test_authenticate_with_correct_password(db, attempts):
    user_id = register(db)

    user = services.authenticate(db, attempts, " Erika", PASSWORD)

    assert user is not None and user.id == user_id


@pytest.mark.parametrize("username, password", [("erika", "Falsch-123"), ("niemand", PASSWORD)])
def test_authenticate_fails_for_wrong_password_or_unknown_user(db, attempts, username, password):
    register(db)

    assert services.authenticate(db, attempts, username, password) is None


def test_deactivated_user_cannot_log_in(db, attempts):
    user_id = register(db)
    services.deactivate(db, user_id, actor="test")

    assert services.authenticate(db, attempts, "erika", PASSWORD) is None


def test_login_is_locked_after_too_many_failures(db, attempts):
    register(db)
    for _ in range(3):
        services.authenticate(db, attempts, "erika", "Falsch-123")

    # Auch das richtige Kennwort hilft jetzt nicht mehr.
    with pytest.raises(LoginLockedError):
        services.authenticate(db, attempts, "erika", PASSWORD)


def test_unknown_usernames_are_locked_too(db, attempts):
    for _ in range(3):
        services.authenticate(db, attempts, "niemand", PASSWORD)

    with pytest.raises(LoginLockedError):
        services.authenticate(db, attempts, "niemand", PASSWORD)


def test_successful_login_resets_failures(db, attempts):
    register(db)
    for _ in range(2):
        services.authenticate(db, attempts, "erika", "Falsch-123")

    services.authenticate(db, attempts, "erika", PASSWORD)
    services.authenticate(db, attempts, "erika", "Falsch-123")

    assert not attempts.is_locked("erika")


def test_lock_expires_after_lockout(db, attempts):
    for _ in range(3):
        attempts.record_failure("erika")
    # Den letzten Versuch in die Vergangenheit legen, statt 15 Minuten zu warten.
    past = (datetime.now(UTC) - timedelta(seconds=900)).isoformat()
    db.projections.conn.execute("UPDATE login_attempts SET last_attempt = ?", (past,))

    assert not attempts.is_locked("erika")
