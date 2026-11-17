import logging

from ..db import Database
from .domain import SUBJECT, Account, Ledger

log = logging.getLogger(__name__)


def get_ledger(db: Database) -> Ledger:
    """Lädt das Hauptbuch aus seinem Stream (ohne Events: noch keine Konten)."""
    return Ledger.from_events(SUBJECT, db.store.read_stream(SUBJECT))


def open_cooperative_account(db: Database, name: str, actor: str) -> Account:
    """Eröffnet das Konto der Genossenschaft, einmalig bei der Ersteinrichtung."""
    ledger = get_ledger(db)
    ledger.open_cooperative_account(name)
    db.save(ledger, actor)
    account = ledger.cooperative_account()
    assert account is not None  # gerade eröffnet
    log.info("cooperative account opened", extra={"number": account.number, "actor": actor})
    return account
