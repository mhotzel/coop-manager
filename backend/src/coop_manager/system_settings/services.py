from ..db import Database
from .domain import SUBJECT, SystemSettings


def get_system_settings(db: Database) -> SystemSettings:
    """Lädt die Systemeinstellungen aus ihrem Stream (ohne Events: nichts festgelegt)."""
    return SystemSettings.from_events(SUBJECT, db.store.read_stream(SUBJECT))


def change_share_price(db: Database, share_price: int, actor: str) -> SystemSettings:
    """Setzt den Anteilspreis (in Cent) und speichert das Event."""
    system_settings = get_system_settings(db)
    system_settings.change_share_price(share_price)
    db.save(system_settings, actor)
    return system_settings
