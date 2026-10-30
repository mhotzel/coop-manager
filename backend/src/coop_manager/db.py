from collections.abc import Iterator, Sequence
from pathlib import Path

from fastapi import Request

from .eventsource import Aggregate, EventStore, Projections, Projector, connect

EVENTSTORE_DB = "eventstore.sqlite"
PROJECTIONS_DB = "projections.sqlite"


class Database:
    """Beide Datenbanken für die Dauer eines Requests."""

    def __init__(self, data_dir: Path, projectors: Sequence[Projector]) -> None:
        self.store = EventStore(connect(str(data_dir / EVENTSTORE_DB)))
        self.projections = Projections(connect(str(data_dir / PROJECTIONS_DB)), projectors)

    def save(self, aggregate: Aggregate, actor: str | None = None) -> None:
        """Speichert die neuen Events des Aggregats und bringt die Projektionen auf den neuesten Stand."""
        self.store.save(aggregate, actor)
        self.projections.catch_up(self.store)

    def close(self) -> None:
        self.store.conn.close()
        self.projections.conn.close()


def prepare(data_dir: Path, projectors: Sequence[Projector]) -> None:
    """Legt beide Datenbanken an und holt die Projektionen auf, z. B. wenn deren Datei gelöscht wurde."""
    data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(data_dir, projectors)
    try:
        db.store.create_schema()
        db.projections.create_schema()
        db.projections.catch_up(db.store)
    finally:
        db.close()


def get_db(request: Request) -> Iterator[Database]:
    """FastAPI-Dependency: Jeder Request bekommt eigene Verbindungen, die danach geschlossen werden."""
    db = Database(request.app.state.data_dir, request.app.state.projectors)
    try:
        yield db
    finally:
        db.close()
