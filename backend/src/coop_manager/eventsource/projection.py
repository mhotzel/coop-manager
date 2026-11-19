import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, ClassVar

from .events import Event, collect_handlers
from .store import EventStore, transaction

CHECKPOINT_SCHEMA = """
CREATE TABLE IF NOT EXISTS projection_checkpoints (
    projector TEXT PRIMARY KEY,
    position  INTEGER NOT NULL,
    version   INTEGER NOT NULL  -- Schemaversion, mit der die Lesetabellen angelegt wurden
);
"""


class Projector:
    """Hält Lesetabellen in der Projektionsdatenbank aktuell.

    Unterklassen definieren ``schema`` (DDL), ``tables`` (werden beim Neuaufbau geleert) und mit
    ``@on("<typ>")`` markierte Handler mit den Argumenten ``(conn, event)``. Eventtypen ohne
    Handler werden ignoriert. ``name`` benennt den Checkpoint; wird ein Projektor umbenannt, baut
    er sich deshalb von Grund auf neu auf.

    **Wer ``schema`` ändert, erhöht ``version``.** Beim nächsten Start werden die Tabellen in
    ``tables`` dann gelöscht, neu angelegt und aus allen Events neu befüllt. ``tables`` muss
    deshalb alle Tabellen des Projektors nennen.
    """

    schema: ClassVar[str] = ""
    tables: ClassVar[tuple[str, ...]] = ()
    version: ClassVar[int] = 1
    _handlers: ClassVar[dict[str, Callable]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Sammelt beim Definieren jeder Unterklasse ihre ``@on``-Handler ein."""
        super().__init_subclass__(**kwargs)
        cls._handlers = collect_handlers(cls)

    @property
    def name(self) -> str:
        """Name des Checkpoints, der Klassenname."""
        return type(self).__name__

    def create_schema(self, conn: sqlite3.Connection) -> None:
        """Legt die Lesetabellen an."""
        if self.schema:
            conn.executescript(self.schema)

    def drop_schema(self, conn: sqlite3.Connection) -> None:
        """Löscht die Lesetabellen samt Indizes, damit sie mit dem neuen Schema entstehen können."""
        for table in self.tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")

    def reset(self, conn: sqlite3.Connection) -> None:
        """Leert die Lesetabellen für den Neuaufbau."""
        for table in self.tables:
            conn.execute(f"DELETE FROM {table}")

    def handle(self, conn: sqlite3.Connection, event: Event) -> None:
        """Ruft den Handler für den Eventtyp auf; ohne Handler passiert nichts."""
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
        """Legt die Checkpoint-Tabelle und die Lesetabellen aller Projektoren an.

        Passt die gespeicherte Schemaversion eines Projektors nicht zu seiner ``version`` (oder ist
        er neu), werden seine Tabellen gelöscht und der Checkpoint auf 0 gesetzt. Das nächste
        `catch_up()` befüllt sie dann aus allen Events neu; die anderen Projektoren bleiben, wie sie
        sind.
        """
        self.conn.executescript(CHECKPOINT_SCHEMA)
        for projector in self.projectors:
            if self._version(projector) != projector.version:
                with transaction(self.conn):
                    projector.drop_schema(self.conn)
                    self._save_checkpoint(projector, 0)
            # Außerhalb der Transaktion: executescript() schließt eine offene Transaktion vorher ab.
            projector.create_schema(self.conn)

    def catch_up(self, store: EventStore) -> None:
        """Wendet die Events an, die seit dem Checkpoint des jeweiligen Projektors dazugekommen sind."""
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
        """Gibt alle Events nach Position ``after`` an den Projektor und merkt sich die letzte Position."""
        last_position = after
        for position, event in store.read_all(after):
            projector.handle(self.conn, event)
            last_position = position
        self._save_checkpoint(projector, last_position)

    def _save_checkpoint(self, projector: Projector, position: int) -> None:
        """Speichert Position und Schemaversion des Projektors."""
        self.conn.execute(
            "INSERT INTO projection_checkpoints (projector, position, version) VALUES (?, ?, ?)"
            " ON CONFLICT (projector) DO UPDATE SET position = excluded.position, version = excluded.version",
            (projector.name, position, projector.version),
        )

    def _version(self, projector: Projector) -> int | None:
        """Liefert die Schemaversion, mit der die Tabellen angelegt wurden; None, wenn er noch nie lief."""
        row = self.conn.execute(
            "SELECT version FROM projection_checkpoints WHERE projector = ?", (projector.name,)
        ).fetchone()
        return row["version"] if row else None

    def _checkpoint(self, projector: Projector) -> int:
        """Liefert die zuletzt verarbeitete Position des Projektors, 0 wenn er noch nie lief."""
        row = self.conn.execute(
            "SELECT position FROM projection_checkpoints WHERE projector = ?", (projector.name,)
        ).fetchone()
        return row["position"] if row else 0
