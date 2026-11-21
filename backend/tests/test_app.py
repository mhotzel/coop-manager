import pytest
from fastapi.testclient import TestClient

from coop_manager.app import app, create_app
from coop_manager.config import Settings


def test_healthz():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture
def frontend(tmp_path) -> TestClient:
    """App mit einer erfundenen, gebauten Oberfläche: index.html und eine Datei unter assets/."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>App</html>")
    (dist / "assets" / "app.js").write_text("console.log('app')")
    (tmp_path / "geheim.txt").write_text("nicht ausliefern")
    return TestClient(create_app(Settings(data_dir=tmp_path, frontend_dir=dist)))


def test_root_delivers_index(frontend):
    response = frontend.get("/")
    assert response.status_code == 200
    assert response.text == "<html>App</html>"


def test_existing_file_is_delivered(frontend):
    response = frontend.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_unknown_path_falls_back_to_index(frontend):
    """Neuladen von /members/5: Die Adresse kennt nur der Vue Router, der Server liefert die App."""
    response = frontend.get("/members/5")
    assert response.status_code == 200
    assert response.text == "<html>App</html>"


def test_unknown_api_path_stays_json_404(frontend):
    response = frontend.get("/api/gibtsnicht")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_healthz_wins_over_frontend(frontend):
    assert frontend.get("/healthz").json() == {"status": "ok"}


# Die erste Form glättet schon der Client, die zweite (kodierte Punkte) kommt so beim Server an.
@pytest.mark.parametrize("path", ["/../geheim.txt", "/%2e%2e/geheim.txt"])
def test_files_outside_frontend_dir_are_not_delivered(frontend, path):
    response = frontend.get(path)
    assert "nicht ausliefern" not in response.text


def test_without_frontend_dir_root_is_404(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert client.get("/").status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_are_off_by_default(tmp_path, path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_can_be_switched_on(tmp_path, path):
    client = TestClient(create_app(Settings(data_dir=tmp_path, api_docs=True)))
    assert client.get(path).status_code == 200
