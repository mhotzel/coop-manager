from pathlib import Path

from coop_manager.config import find_env_file, load_settings


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


def test_env_file_is_read(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# Kommentar\nCM_LOG_LEVEL=warning\nCM_DATA_DIR=/srv/aus-datei\n")
    monkeypatch.setattr("coop_manager.config.find_env_file", lambda: str(env_file))
    monkeypatch.delenv("CM_LOG_LEVEL", raising=False)
    monkeypatch.setenv("CM_DATA_DIR", "/srv/aus-umgebung")

    settings = load_settings()

    assert settings.log_level == "WARNING"  # aus der Datei
    assert settings.data_dir == Path("/srv/aus-umgebung")  # Umgebung geht vor


def test_env_file_is_searched_upwards(monkeypatch, tmp_path):
    # find_env_file ist hier die Originalfunktion: Die Fixture no_env_file ersetzt nur den Eintrag im
    # Modul coop_manager.config, nicht diesen Namen, der schon beim Import geholt wurde.
    (tmp_path / ".env").write_text("CM_LOG_LEVEL=error\n")
    (tmp_path / "backend").mkdir()
    monkeypatch.chdir(tmp_path / "backend")

    assert find_env_file() == str(tmp_path / ".env")


def test_frontend_dir_and_api_docs_have_defaults(monkeypatch):
    monkeypatch.delenv("CM_FRONTEND_DIR", raising=False)
    monkeypatch.delenv("CM_API_DOCS", raising=False)

    settings = load_settings()
    assert settings.frontend_dir is None
    assert settings.api_docs is False


def test_frontend_dir_and_api_docs_come_from_environment(monkeypatch):
    monkeypatch.setenv("CM_FRONTEND_DIR", "/app/frontend")
    monkeypatch.setenv("CM_API_DOCS", "true")

    settings = load_settings()
    assert settings.frontend_dir == Path("/app/frontend")
    assert settings.api_docs is True
