import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from .events import Event, collect_handlers
from .store import EventStore, transaction

CHECKPOINT_SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_checkpoints (
    projector TEXT PRIMARY KEY,
    position  INTEGER NOT NULL
);
"""


class Projector:
    """Hält Lesetabellen in der Projektionsdatenbank aktuell.

    Unterklassen definieren ``schema`` (DDL), ``tables`` (werden beim Neuaufbau geleert) und mit
    ``@on("<typ>")`` markierte Handler mit den Argumenten ``(conn, event)``. Eventtypen ohne
    Handler werden ignoriert. ``name`` benennt den Checkpoint; wird ein Projektor umbenannt, baut
    er sich deshalb von Grund auf neu auf.
    """

    schema: ClassVar[str] = ""
    tables: ClassVar[tuple[str, ...]] = ()
    _handlers: ClassVar[dict[str, Callable]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._handlers = collect_handlers(cls)

    @property
    def name(self) -> str:
        return type(self).__name__

    def create_schema(self, conn: sqlite3.Connection) -> None:
        if self.schema:
            conn.executescript(self.schema)

    def reset(self, conn: sqlite3.Connection) -> None:
        for table in self.tables:
            conn.execute(f"DELETE FROM {table}")

    def handle(self, conn: sqlite3.Connection, event: Event) -> None:
        handler = self._handlers.get(event.type)
        if handler is not None:
            handler(self, conn, event)


class Projections:
    """Lässt die Projektoren gegen den Event Store laufen; jeder hat seinen eigenen Checkpoint.

    Lesetabellen und Checkpoint ändern sich in einer Transaktion der Projektionsdatenbank und
    passen deshalb immer zusammen. Scheitert ein Projektor, wird sein Durchlauf zurückgerollt, und
    er macht beim nächsten `catch_up()` am alten Checkpoint weiter; die Events bleiben gespeichert.
    """

    def __init__(self, conn: sqlite3.Connection, projectors: Sequence[Projector]) -> None:
        self.conn = conn
        self.projectors = list(projectors)

    def create_schema(self) -> None:
        self.conn.executescript(CHECKPOINT_SCHEMA)
        for projector in self.projectors:
            projector.create_schema(self.conn)

    def catch_up(self, store: EventStore) -> None:
        for projector in self.projectors:
            with transaction(self.conn):
                self._project(projector, store, after=self._checkpoint(projector))

    def rebuild(self, store: EventStore) -> None:
        """Leert alle Lesetabellen und spielt die komplette Historie neu ab."""
        for projector in self.projectors:
            with transaction(self.conn):
                projector.reset(self.conn)
                self._project(projector, store, after=0)

    def _project(self, projector: Projector, store: EventStore, after: int) -> None:
        last_position = after
        for position, event in store.read_all(after):
            projector.handle(self.conn, event)
            last_position = position
        self.conn.execute(
            "INSERT INTO projection_checkpoints (projector, position) VALUES (?, ?)"
            " ON CONFLICT (projector) DO UPDATE SET position = excluded.position",
            (projector.name, last_position),
        )

    def _checkpoint(self, projector: Projector) -> int:
        row = self.conn.execute(
            "SELECT position FROM projection_checkpoints WHERE projector = ?", (projector.name,)
        ).fetchone()
        return row["position"] if row else 0
