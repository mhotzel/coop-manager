from typing import Annotated

import pytest
from fastapi import Depends

from coop_manager.core import DomainError, NotFoundError
from coop_manager.users import services
from coop_manager.users.access import CSRF_HEADER, require_role
from coop_manager.users.domain import ACCOUNTING, ADMIN
from coop_manager.users.projections import UserView


def test_login_returns_user_and_csrf_token(client, register, login):
    user_id = register()

    response = login()

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": user_id,
        "username": "erika",
        "full_name": "Erika Muster",
        "role": ACCOUNTING,
        "active": True,
    }
    assert body["csrf_token"]
    assert "password_hash" not in response.text


def test_session_cookie_is_httponly_secure_and_expires(register, login):
    register()

    cookie = login().headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=1800" in cookie


def test_login_with_wrong_password(register, login):
    register()

    response = login(password="Falsch-123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Benutzername oder Kennwort falsch."}


def test_login_is_locked_after_too_many_failures(register, login):
    register()
    for _ in range(3):
        login(password="Falsch-123")

    assert login().status_code == 429


def test_me_without_login(client):
    assert client.get("/api/me").status_code == 401


def test_me_after_login(client, register, login):
    register()
    csrf_token = login().json()["csrf_token"]

    response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "erika"
    assert response.json()["csrf_token"] == csrf_token


def test_deactivated_user_loses_access_immediately(client, db, register, login):
    user_id = register()
    login()

    services.deactivate(db, user_id, actor="test")

    assert client.get("/api/me").status_code == 401


def test_logout_ends_session(client, register, login):
    register()
    login()

    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


@pytest.mark.parametrize("csrf_token", [None, "falsch"])
def test_unsafe_request_needs_csrf_token(client, register, login, csrf_token):
    register()
    login()
    if csrf_token is None:
        del client.headers[CSRF_HEADER]
    else:
        client.headers[CSRF_HEADER] = csrf_token

    assert client.post("/api/logout").status_code == 403
    assert client.get("/api/me").status_code == 200  # noch angemeldet


def test_role_is_checked(app, client, register, login):
    # Nur für diesen Test: ein Endpunkt, den allein Admins aufrufen dürfen.
    @app.get("/api/admin-only")
    def admin_only(user: Annotated[UserView, Depends(require_role(ADMIN))]) -> dict[str, str]:
        return {"user": user.username}

    register("erika", ACCOUNTING)
    register("chefin", ADMIN)

    login("erika")
    assert client.get("/api/admin-only").status_code == 403

    login("chefin")
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


def test_change_own_password(client, register, login):
    register()
    login()

    response = client.post(
        "/api/me/change-password", json={"current_password": "Geheim-123", "new_password": "Neu-Geheim-456"}
    )

    assert response.status_code == 204
    assert client.get("/api/me").status_code == 200  # weiter angemeldet
    assert login(password="Neu-Geheim-456").status_code == 200


def test_change_own_password_with_wrong_current_password(client, register, login):
    register()
    login()

    response = client.post(
        "/api/me/change-password", json={"current_password": "Falsch-123", "new_password": "Neu-Geheim-456"}
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Das bisherige Kennwort ist falsch."}


def test_change_own_password_needs_login(client):
    response = client.post("/api/me/change-password", json={"current_password": "x", "new_password": "y"})

    assert response.status_code == 401
