import pytest

from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY, ADMIN

NEW_USER = {"username": "max", "full_name": "Max Beispiel", "password": "Anfang-123", "role": ACCOUNTING}


@pytest.fixture
def admin_id(register, login) -> str:
    """Ein angemeldeter Admin; die Tests sprechen danach als dieser Admin mit der API."""
    admin_id = register("chefin", ADMIN, full_name="Clara Chefin")
    login("chefin")
    return admin_id


@pytest.fixture
def user_id(client, admin_id) -> str:
    """Ein vom Admin angelegter Benutzer."""
    return client.post("/api/users/register", json=NEW_USER).json()["id"]


def test_register_user(client, login, admin_id):
    response = client.post("/api/users/register", json=NEW_USER)

    assert response.status_code == 200
    assert response.json() | {"id": "…"} == {
        "id": "…",
        "username": "max",
        "full_name": "Max Beispiel",
        "role": ACCOUNTING,
        "active": True,
    }
    assert login("max", "Anfang-123").status_code == 200


def test_register_reports_domain_error(client, admin_id, user_id):
    response = client.post("/api/users/register", json=NEW_USER)

    assert response.status_code == 400
    assert response.json() == {"detail": "Der Benutzername 'max' ist bereits vergeben."}


def test_list_and_get_users(client, admin_id, user_id):
    users = client.get("/api/users").json()

    assert [user["username"] for user in users] == ["chefin", "max"]
    assert client.get(f"/api/users/{user_id}").json()["full_name"] == "Max Beispiel"


def test_get_unknown_user(client, admin_id):
    assert client.get("/api/users/user-unbekannt").status_code == 404


def test_list_roles(client, admin_id):
    roles = client.get("/api/users/roles").json()

    assert {"value": ACCOUNTING_READONLY, "label": "Buchhaltung lesend"} in roles


def test_change_full_name_and_role(client, admin_id, user_id):
    client.post("/api/users/change-full-name", json={"user_id": user_id, "full_name": "Max Muster"})
    response = client.post("/api/users/change-role", json={"user_id": user_id, "role": ACCOUNTING_READONLY})

    assert response.json()["full_name"] == "Max Muster"
    assert response.json()["role"] == ACCOUNTING_READONLY


def test_change_password(client, login, admin_id, user_id):
    client.post("/api/users/change-password", json={"user_id": user_id, "password": "Neu-Geheim-456"})

    assert login("max", "Anfang-123").status_code == 401
    assert login("max", "Neu-Geheim-456").status_code == 200


def test_deactivate_reactivate_and_terminate(client, admin_id, user_id):
    assert client.post("/api/users/deactivate", json={"user_id": user_id}).json()["active"] is False
    assert client.post("/api/users/reactivate", json={"user_id": user_id}).json()["active"] is True

    client.post("/api/users/deactivate", json={"user_id": user_id})
    assert client.post("/api/users/terminate", json={"user_id": user_id}).status_code == 204
    assert client.get(f"/api/users/{user_id}").status_code == 404


def test_admin_cannot_deactivate_self(client, admin_id):
    response = client.post("/api/users/deactivate", json={"user_id": admin_id})

    assert response.status_code == 400
    assert response.json() == {"detail": "Du kannst dich nicht selbst deaktivieren."}


def test_events_record_admin_as_actor(client, db, admin_id, user_id):
    assert [event.actor for event in db.store.read_stream(user_id)] == [admin_id]


def test_only_admin_may_manage_users(client, register, login):
    register("erika", ACCOUNTING)
    login("erika")

    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users/register", json=NEW_USER).status_code == 403
