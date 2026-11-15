"""Gemeinsame Fixtures für die API-Tests; pytest findet diese Datei von selbst."""

from collections.abc import Callable, Iterator

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coop_manager.app import create_app
from coop_manager.config import Settings
from coop_manager.db import Database
from coop_manager.users import services
from coop_manager.users.access import CSRF_HEADER
from coop_manager.users.domain import ACCOUNTING

PASSWORD = "Geheim-123"


@pytest.fixture(autouse=True)
def no_env_file(monkeypatch):
    """Die Tests sollen nicht von einer lokalen .env abhängen; autouse = gilt für jeden Test."""
    monkeypatch.setattr("coop_manager.config.find_env_file", lambda: "")


@pytest.fixture
def app(tmp_path) -> FastAPI:
    return create_app(Settings(data_dir=tmp_path, secret_key="test-key"))


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


@pytest.fixture
def register(db) -> Callable[..., str]:
    """Legt einen erfundenen Benutzer an und liefert seine ID: `register("erika", ACCOUNTING)`."""

    def register(username: str = "erika", role: str = ACCOUNTING, full_name: str = "Erika Muster") -> str:
        return services.register_user(db, username, full_name, PASSWORD, role, actor="test").subject

    return register


@pytest.fixture
def login(client) -> Callable[..., httpx2.Response]:
    """Meldet an; bei Erfolg schickt der Client danach das CSRF-Token bei jeder Anfrage mit."""

    def login(username: str = "erika", password: str = PASSWORD) -> httpx2.Response:
        response = client.post("/api/login", json={"username": username, "password": password})
        if response.status_code == 200:
            client.headers[CSRF_HEADER] = response.json()["csrf_token"]
        return response

    return login
