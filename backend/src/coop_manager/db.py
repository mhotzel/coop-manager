import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path

from fastapi import Request

from .eventsource import Aggregate, EventStore, Projections, Projector, connect, transaction

EVENTSTORE_DB = "eventstore.sqlite"
PROJECTIONS_DB = "projections.sqlite"


class Database:
    """Beide Datenbanken für die Dauer eines Requests."""

    def __init__(self, data_dir: Path, projectors: Sequence[Projector]) -> None:
        """Öffnet die Verbindungen zu Event Store und Projektionsdatenbank im Datenverzeichnis."""
        self.store = EventStore(connect(str(data_dir / EVENTSTORE_DB)))
        self.projections = Projections(connect(str(data_dir / PROJECTIONS_DB)), projectors)

    def save(self, aggregate: Aggregate, actor: str | None = None) -> None:
        """Speichert die neuen Events des Aggregats und bringt die Projektionen auf den neuesten Stand."""
        self.store.save(aggregate, actor)
        self.projections.catch_up(self.store)

    def save_all(self, aggregates: Sequence[Aggregate], actor: str | None = None) -> None:
        """Speichert mehrere Aggregate in einer Transaktion: alle oder keines.

        Scheitert eines an der Versionsprüfung, bleibt auch von den anderen nichts gespeichert.
        """
        with transaction(self.store.conn):
            for aggregate in aggregates:
                self.store.save(aggregate, actor)
        self.projections.catch_up(self.store)

    def close(self) -> None:
        """Schließt beide Verbindungen."""
        self.store.conn.close()
        self.projections.conn.close()


def prepare(data_dir: Path, projectors: Sequence[Projector], schemas: Sequence[str] = ()) -> None:
    """Legt beide Datenbanken an und holt die Projektionen auf, z. B. wenn deren Datei gelöscht wurde.

    ``schemas`` sind weitere Tabellen in der Projektionsdatenbank, die nicht aus Events entstehen
    (z. B. die Login-Versuche).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(data_dir, projectors)
    try:
        db.store.create_schema()
        db.projections.create_schema()
        for schema in schemas:
            db.projections.conn.executescript(schema)
        db.projections.catch_up(db.store)
    finally:
        db.close()


def backup_event_store(data_dir: Path, target: Path) -> int:
    """Schreibt eine stimmige Kopie des Event Store nach `target`, auch während die App läuft.

    Liefert die Anzahl der Events. Die Kopie ist eine einzige Datei (ohne -wal/-shm) und erscheint
    erst unter ihrem Namen, wenn sie fertig und geprüft ist. Eine Dateisicherung, die gleichzeitig
    läuft (Hyper Backup), sieht so nie eine halb geschriebene Datei.
    """
    source_path = data_dir / EVENTSTORE_DB
    if not source_path.is_file():
        # Sonst legte sqlite3.connect eine leere Datei an, und wir sicherten still nichts.
        raise FileNotFoundError(f"Kein Event Store unter {source_path}.")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    partial.unlink(missing_ok=True)
    source = connect(str(source_path))
    copy = sqlite3.connect(partial)
    try:
        source.backup(copy)  # die Backup-API von SQLite
        copy.execute("PRAGMA journal_mode = DELETE")  # eine einzige Datei ohne -wal/-shm
        if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Die Kopie des Event Store ist beschädigt.")
        count = copy.execute("SELECT count(*) FROM events").fetchone()[0]
    finally:
        copy.close()
        source.close()
    partial.replace(target)  # Umbenennen in einem Zug
    return count


def get_db(request: Request) -> Iterator[Database]:
    """FastAPI-Dependency: Jeder Request bekommt eigene Verbindungen, die danach geschlossen werden."""
    db = Database(request.app.state.settings.data_dir, request.app.state.projectors)
    try:
        yield db
    finally:
        db.close()
