from fastapi.testclient import TestClient

from coop_manager.app import create_app
from coop_manager.config import Settings


def make_client(tmp_path, client_ip="10.0.0.1", base_url="http://testserver"):
    settings = Settings(data_dir=tmp_path, trusted_proxies=("10.0.0.1",))
    return TestClient(create_app(settings), base_url=base_url, client=(client_ip, 50000))


def test_security_headers_are_set(tmp_path):
    response = make_client(tmp_path).get("/healthz")

    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_is_sent_over_https(tmp_path):
    response = make_client(tmp_path, base_url="https://testserver").get("/healthz")

    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]


def test_forwarded_headers_count_only_from_trusted_proxy(tmp_path):
    headers = {"X-Forwarded-Proto": "https"}

    trusted = make_client(tmp_path, client_ip="10.0.0.1").get("/healthz", headers=headers)
    untrusted = make_client(tmp_path, client_ip="10.0.0.2").get("/healthz", headers=headers)

    assert "Strict-Transport-Security" in trusted.headers
    assert "Strict-Transport-Security" not in untrusted.headers
