import pytest

from coop_manager.core import DomainError
from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY, ADMIN, User

PASSWORD = "Geheim-123"


def register(**overrides) -> User:
    data = {"username": "erika", "full_name": "Erika Muster", "password": PASSWORD, "role": ACCOUNTING}
    return User.register(**(data | overrides))


def reloaded(user: User) -> User:
    """Baut den Benutzer aus seinen Events neu auf, wie nach dem Laden aus dem Event Store."""
    return User.from_events(user.subject, user.uncommitted_events)


def test_register_creates_active_user():
    user = register()

    assert user.subject.startswith("user-")
    assert (user.username, user.full_name, user.role, user.active) == ("erika", "Erika Muster", ACCOUNTING, True)
    assert [e.type for e in user.uncommitted_events] == ["user.registered"]


def test_register_normalizes_username_and_full_name():
    user = register(username="  Erika.M ", full_name=" Erika   Muster ")

    assert user.username == "erika.m"
    assert user.full_name == "Erika Muster"


def test_password_is_stored_only_as_hash():
    user = register()

    assert PASSWORD not in str(user.uncommitted_events[0].data)
    assert user.check_password(PASSWORD)
    assert not user.check_password("Falsch-123")


@pytest.mark.parametrize("username", ["ab", "erika muster", "erika@example", "x" * 51])
def test_invalid_username_is_rejected(username):
    with pytest.raises(DomainError, match="Benutzername"):
        register(username=username)


@pytest.mark.parametrize("full_name", ["", "123", "Erika <script>", "x" * 101])
def test_invalid_full_name_is_rejected(full_name):
    with pytest.raises(DomainError, match="Name"):
        register(full_name=full_name)


@pytest.mark.parametrize("password", ["Kurz-1", "geheim-123", "GEHEIM-123", "Geheim-abc", "Geheim1234"])
def test_weak_password_is_rejected(password):
    with pytest.raises(DomainError, match="Kennwort"):
        register(password=password)


def test_unknown_role_is_rejected():
    with pytest.raises(DomainError, match="Rolle"):
        register(role="chef")


def test_change_full_name_without_change_records_nothing():
    user = register()

    user.change_full_name(" Erika  Muster")

    assert len(user.uncommitted_events) == 1


def test_change_full_name():
    user = register()

    user.change_full_name("Erika Beispiel")

    assert reloaded(user).full_name == "Erika Beispiel"


def test_change_password():
    user = register()

    user.change_password("Neu-Geheim-456")

    assert reloaded(user).check_password("Neu-Geheim-456")
    assert not reloaded(user).check_password(PASSWORD)


def test_change_role():
    user = register()

    user.change_role(ACCOUNTING_READONLY)

    assert reloaded(user).role == ACCOUNTING_READONLY


def test_change_to_same_role_is_rejected():
    user = register(role=ADMIN)

    with pytest.raises(DomainError, match="bereits"):
        user.change_role(ADMIN)


def test_deactivate_and_reactivate():
    user = register()

    user.deactivate()
    assert not reloaded(user).active

    user.reactivate()
    assert reloaded(user).active


def test_deactivate_twice_is_rejected():
    user = register()
    user.deactivate()

    with pytest.raises(DomainError, match="bereits deaktiviert"):
        user.deactivate()


def test_only_deactivated_user_can_be_terminated():
    user = register()

    with pytest.raises(DomainError, match="Nur deaktivierte"):
        user.terminate()

    user.deactivate()
    user.terminate()

    assert reloaded(user).terminated


def test_terminated_user_cannot_be_changed():
    user = register()
    user.deactivate()
    user.terminate()

    with pytest.raises(DomainError, match="gelöscht"):
        user.reactivate()
