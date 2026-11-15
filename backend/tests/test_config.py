from pathlib import Path

from coop_manager.config import load_settings


def test_data_dir_has_default(monkeypatch):
    monkeypatch.delenv("CM_DATA_DIR", raising=False)

    assert load_settings().data_dir == Path("data")


def test_data_dir_comes_from_environment(monkeypatch):
    monkeypatch.setenv("CM_DATA_DIR", "/srv/coop")

    assert load_settings().data_dir == Path("/srv/coop")


def test_log_level_has_default(monkeypatch):
    monkeypatch.delenv("CM_LOG_LEVEL", raising=False)

    assert load_settings().log_level == "INFO"


def test_log_level_comes_from_environment_in_any_case(monkeypatch):
    monkeypatch.setenv("CM_LOG_LEVEL", "debug")

    assert load_settings().log_level == "DEBUG"


def test_trusted_proxies_default_to_none(monkeypatch):
    monkeypatch.delenv("CM_TRUSTED_PROXIES", raising=False)

    assert load_settings().trusted_proxies == ()


def test_trusted_proxies_are_split_at_commas(monkeypatch):
    monkeypatch.setenv("CM_TRUSTED_PROXIES", "10.0.0.1, 172.18.0.1,")

    assert load_settings().trusted_proxies == ("10.0.0.1", "172.18.0.1")


def test_session_settings_have_defaults(monkeypatch):
    for name in ("CM_SECRET_KEY", "CM_SESSION_TIMEOUT", "CM_SESSION_COOKIE_SECURE"):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert (settings.secret_key, settings.session_timeout, settings.session_cookie_secure) == ("", 1800, True)


def test_session_cookie_secure_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("CM_SESSION_COOKIE_SECURE", "false")

    assert load_settings().session_cookie_secure is False
