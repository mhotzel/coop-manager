import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime

from .aggregate import Aggregate
from .events import Event

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    position INTEGER PRIMARY KEY AUTOINCREMENT,
    id       TEXT    NOT NULL UNIQUE,
    type     TEXT    NOT NULL,
    subject  TEXT    NOT NULL,
    version  INTEGER NOT NULL,
    time     TEXT    NOT NULL,
    data     TEXT    NOT NULL,
    actor    TEXT,
    UNIQUE (subject, version)
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (type);
"""


class ConcurrencyError(Exception):
    """Der Stream wurde geändert, seit das Aggregat geladen wurde."""


def connect(path: str) -> sqlite3.Connection:
    """Öffnet eine Verbindung im Autocommit-Modus; Transaktionen steuert `transaction()`.

    FastAPI kann Dependency und Endpunkt in verschiedenen Threads ausführen, deshalb
    `check_same_thread=False`. Sicher ist das, weil jeder Request eine eigene Verbindung hat.
    """
    conn = sqlite3.connect(path, autocommit=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Schreibtransaktion; verschachtelte Aufrufe schließen sich der äußeren an."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


class EventStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create_schema(self) -> None:
        self.conn.executescript(SCHEMA)

    def append(self, events: Iterable[Event], actor: str | None = None) -> None:
        with transaction(self.conn):
            for event in events:
                if actor is not None:
                    event = replace(event, actor=actor)
                try:
                    self.conn.execute(
                        "INSERT INTO events (id, type, subject, version, time, data, actor)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(event.id),
                            event.type,
                            event.subject,
                            event.version,
                            event.time.isoformat(),
                            json.dumps(event.data, ensure_ascii=False),
                            event.actor,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ConcurrencyError(f"Version {event.version} von '{event.subject}' gibt es schon") from exc

    def save(self, aggregate: Aggregate, actor: str | None = None) -> None:
        self.append(aggregate.uncommitted_events, actor)
        aggregate.mark_committed()

    def load[A: Aggregate](self, cls: type[A], subject: str) -> A | None:
        events = self.read_stream(subject)
        return cls.from_events(subject, events) if events else None

    def read_stream(self, subject: str) -> list[Event]:
        rows = self.conn.execute("SELECT * FROM events WHERE subject = ? ORDER BY version", (subject,))
        return [self._to_event(row) for row in rows]

    def read_all(self, after: int = 0) -> Iterator[tuple[int, Event]]:
        for row in self.conn.execute("SELECT * FROM events WHERE position > ? ORDER BY position", (after,)):
            yield row["position"], self._to_event(row)

    @staticmethod
    def _to_event(row: sqlite3.Row) -> Event:
        return Event(
            type=row["type"],
            subject=row["subject"],
            data=json.loads(row["data"]),
            version=row["version"],
            id=uuid.UUID(row["id"]),
            time=datetime.fromisoformat(row["time"]),
            actor=row["actor"],
        )
