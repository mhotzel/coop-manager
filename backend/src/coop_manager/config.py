import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Die Konfiguration der App, nach dem Start unveränderlich."""

    data_dir: Path


def load_settings() -> Settings:
    """Liest die Konfiguration aus den CM_*-Umgebungsvariablen (siehe .env.example)."""
    env = os.environ
    return Settings(data_dir=Path(env.get("CM_DATA_DIR", "data")))
