import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Die Konfiguration der App, nach dem Start unveränderlich."""

    data_dir: Path
    log_level: str = "INFO"
    trusted_proxies: tuple[str, ...] = ()
    login_max_attempts: int = 3
    login_lockout_seconds: int = 900


def load_settings() -> Settings:
    """Liest die Konfiguration aus den CM_*-Umgebungsvariablen (siehe .env.example)."""
    env = os.environ
    return Settings(
        data_dir=Path(env.get("CM_DATA_DIR", "data")),
        log_level=env.get("CM_LOG_LEVEL", "INFO").upper(),
        trusted_proxies=_list(env.get("CM_TRUSTED_PROXIES", "")),
        login_max_attempts=int(env.get("CM_LOGIN_MAX_ATTEMPTS", "3")),
        login_lockout_seconds=int(env.get("CM_LOGIN_LOCKOUT_SECONDS", "900")),
    )


def _list(value: str) -> tuple[str, ...]:
    """Zerlegt eine mit Komma getrennte Liste, leere Einträge fallen weg."""
    return tuple(item.strip() for item in value.split(",") if item.strip())
