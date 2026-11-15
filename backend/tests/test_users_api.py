from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from coop_manager.app import create_app
from coop_manager.config import Settings
from coop_manager.core import DomainError, NotFoundError
from coop_manager.db import Database
from coop_manager.users import services
from coop_manager.users.access import CSRF_HEADER, require_role
from coop_manager.users.domain import ACCOUNTING, ADMIN
from coop_manager.users.projections import UserView

PASSWORD = "Geheim-123"


@pytest.fixture
def app(tmp_path) -> FastAPI:
    app = create_app(Settings(data_dir=tmp_path, secret_key="test-key"))

    # Nur für die Tests: ein Endpunkt, den allein Admins aufrufen dürfen.
    @app.get("/api/admin-only")
    def admin_only(user: Annotated[UserView, Depends(require_role(ADMIN))]) -> dict[str, str]:
        return {"user": user.username}

    return app


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    # https, weil das Session-Cookie nur über HTTPS geschickt wird (Secure).
    with TestClient(app, base_url="https://testserver") as client:
        yield client


@pytest.fixture
def db(app, client) -> Iterator[Database]:
    """Direkter Zugriff auf die Datenbank, z. B. um Benutzer anzulegen; erst nach dem Start der App."""
    db = Database(app.state.settings.data_dir, app.state.projectors)
    yield db
    db.close()


def register(db: Database, username: str = "erika", role: str = ACCOUNTING) -> str:
    return services.register_user(db, username, "Erika Muster", PASSWORD, role, actor="test").subject


def login(client: TestClient, username: str = "erika", password: str = PASSWORD):
    return client.post("/api/login", json={"username": username, "password": password})


def test_login_returns_user_and_csrf_token(client, db):
    user_id = register(db)

    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {"id": user_id, "username": "erika", "full_name": "Erika Muster", "role": ACCOUNTING}
    assert body["csrf_token"]
    assert "password_hash" not in response.text


def test_session_cookie_is_httponly_secure_and_expires(client, db):
    register(db)

    cookie = login(client).headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=1800" in cookie


def test_login_with_wrong_password(client, db):
    register(db)

    response = login(client, password="Falsch-123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Benutzername oder Kennwort falsch."}


def test_login_is_locked_after_too_many_failures(client, db):
    register(db)
    for _ in range(3):
        login(client, password="Falsch-123")

    assert login(client).status_code == 429


def test_me_without_login(client):
    assert client.get("/api/me").status_code == 401


def test_me_after_login(client, db):
    register(db)
    csrf_token = login(client).json()["csrf_token"]

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "erika"
    assert response.json()["csrf_token"] == csrf_token


def test_deactivated_user_loses_access_immediately(client, db):
    user_id = register(db)
    login(client)

    services.deactivate(db, user_id, actor="test")

    assert client.get("/api/me").status_code == 401


def test_logout_ends_session(client, db):
    register(db)
    csrf_token = login(client).json()["csrf_token"]

    assert client.post("/api/logout", headers={CSRF_HEADER: csrf_token}).status_code == 204
    assert client.get("/api/me").status_code == 401


@pytest.mark.parametrize("headers", [{}, {CSRF_HEADER: "falsch"}])
def test_unsafe_request_needs_csrf_token(client, db, headers):
    register(db)
    login(client)

    assert client.post("/api/logout", headers=headers).status_code == 403
    assert client.get("/api/me").status_code == 200  # noch angemeldet


def test_role_is_checked(client, db):
    register(db, "erika", ACCOUNTING)
    register(db, "chefin", ADMIN)

    login(client, "erika")
    assert client.get("/api/admin-only").status_code == 403

    login(client, "chefin")
    assert client.get("/api/admin-only").json() == {"user": "chefin"}


def test_domain_error_becomes_400_with_detail(app, client):
    @app.get("/healthz-domain-error")
    def fail() -> None:
        raise DomainError("Das geht so nicht.")

    @app.get("/healthz-not-found")
    def missing() -> None:
        raise NotFoundError("Gibt es nicht.")

    assert client.get("/healthz-domain-error").json() == {"detail": "Das geht so nicht."}
    assert client.get("/healthz-domain-error").status_code == 400
    assert client.get("/healthz-not-found").status_code == 404
