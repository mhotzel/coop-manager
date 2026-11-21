import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, find_dotenv


@dataclass(frozen=True)
class Settings:
    """Die Konfiguration der App, nach dem Start unveränderlich."""

    data_dir: Path
    log_level: str = "INFO"
    trusted_proxies: tuple[str, ...] = ()
    login_max_attempts: int = 3
    login_lockout_seconds: int = 900
    secret_key: str = ""  # leer: Die App erzeugt beim Start einen zufälligen Schlüssel.
    session_timeout: int = 1800
    session_cookie_secure: bool = True
    cooperative_account_name: str = "Unser Dorfladen Schlichten eG"
    frontend_dir: Path | None = None  # None: keine Oberfläche ausliefern (Entwicklung mit Vite)
    api_docs: bool = False  # /docs, /redoc und /openapi.json; im Betrieb aus


def find_env_file() -> str:
    """Sucht `.env` im aktuellen Ordner und darüber; aus backend/ heraus also auch ../.env.

    Liefert einen leeren Text, wenn es keine gibt, z. B. im Container.
    """
    return find_dotenv(usecwd=True)


def load_settings() -> Settings:
    """Liest die Konfiguration aus den CM_*-Umgebungsvariablen (siehe .env.example).

    Gibt es eine `.env`, gelten ihre Werte ebenfalls. Echte Umgebungsvariablen gehen vor, damit man
    einzelne Werte beim Start überschreiben kann. `os.environ` selbst bleibt unverändert.
    """
    env = _read_env_file(find_env_file()) | dict(os.environ)
    return Settings(
        data_dir=Path(env.get("CM_DATA_DIR", "data")),
        log_level=env.get("CM_LOG_LEVEL", "INFO").upper(),
        trusted_proxies=_list(env.get("CM_TRUSTED_PROXIES", "")),
        login_max_attempts=int(env.get("CM_LOGIN_MAX_ATTEMPTS", "3")),
        login_lockout_seconds=int(env.get("CM_LOGIN_LOCKOUT_SECONDS", "900")),
        secret_key=env.get("CM_SECRET_KEY", ""),
        session_timeout=int(env.get("CM_SESSION_TIMEOUT", "1800")),
        session_cookie_secure=_bool(env.get("CM_SESSION_COOKIE_SECURE", "true")),
        cooperative_account_name=env.get("CM_COOPERATIVE_ACCOUNT_NAME", "Unser Dorfladen Schlichten eG"),
        frontend_dir=_path_or_none(env.get("CM_FRONTEND_DIR", "")),
        api_docs=_bool(env.get("CM_API_DOCS", "false")),
    )


def _read_env_file(path: str) -> dict[str, str]:
    """Die Einträge der Datei; Zeilen ohne `=` (Wert None) fallen weg."""
    if not path:
        return {}
    return {key: value for key, value in dotenv_values(path).items() if value is not None}


def _list(value: str) -> tuple[str, ...]:
    """Zerlegt eine mit Komma getrennte Liste, leere Einträge fallen weg."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _path_or_none(value: str) -> Path | None:
    """Ein leerer Text heißt „nicht gesetzt“."""
    return Path(value) if value.strip() else None


def _bool(value: str) -> bool:
    """„true“, „1“, „yes“ und „on“ gelten als wahr, alles andere als falsch."""
    return value.strip().lower() in ("1", "true", "yes", "on")
