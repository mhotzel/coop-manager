import sqlite3
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient

from coop_manager.app import create_app
from coop_manager.config import Settings
from coop_manager.db import EVENTSTORE_DB, PROJECTIONS_DB, Database, get_db, prepare
from coop_manager.eventsource import Aggregate, Event, Projector, on


class Note(Aggregate):
    """Erfundenes Mini-Aggregat, nur für diese Tests."""

    def __init__(self, subject: str) -> None:
        super().__init__(subject)
        self.text = ""

    @classmethod
    def write(cls, subject: str, text: str) -> Note:
        note = cls(subject)
        note._record("note.written", text=text)
        return note

    @on("note.written")
    def _written(self, event: Event) -> None:
        self.text = event.data["text"]


class NoteList(Projector):
    schema = "CREATE TABLE IF NOT EXISTS note_list (id TEXT PRIMARY KEY, text TEXT NOT NULL)"
    tables = ("note_list",)

    @on("note.written")
    def _written(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("INSERT INTO note_list VALUES (?, ?)", (event.subject, event.data["text"]))


def note_texts(db: Database) -> list[str]:
    return [row["text"] for row in db.projections.conn.execute("SELECT text FROM note_list ORDER BY text")]


def test_startup_creates_both_databases(tmp_path):
    data_dir = tmp_path / "data"

    with TestClient(create_app(Settings(data_dir))):
        assert (data_dir / EVENTSTORE_DB).exists()
        assert (data_dir / PROJECTIONS_DB).exists()


def test_save_updates_read_tables_immediately(tmp_path):
    prepare(tmp_path, [NoteList()])
    db = Database(tmp_path, [NoteList()])

    db.save(Note.write("n-1", "Erste Notiz"))

    assert note_texts(db) == ["Erste Notiz"]
    db.close()


def test_startup_rebuilds_deleted_projections(tmp_path):
    prepare(tmp_path, [NoteList()])
    db = Database(tmp_path, [NoteList()])
    db.save(Note.write("n-1", "Bleibt erhalten"))
    db.close()
    (tmp_path / PROJECTIONS_DB).unlink()

    with TestClient(create_app(Settings(tmp_path), [NoteList()])):
        db = Database(tmp_path, [NoteList()])
        assert note_texts(db) == ["Bleibt erhalten"]
        db.close()


def test_endpoint_uses_database_through_dependency(tmp_path):
    app = create_app(Settings(tmp_path), [NoteList()])

    @app.post("/notes/{note_id}")
    def write_note(note_id: str, db: Annotated[Database, Depends(get_db)]) -> list[str]:
        db.save(Note.write(note_id, f"Notiz {note_id}"))
        return note_texts(db)

    with TestClient(app) as client:
        client.post("/notes/1")
        response = client.post("/notes/2")

    assert response.status_code == 200
    assert response.json() == ["Notiz 1", "Notiz 2"]


def test_simultaneous_requests_work(tmp_path):
    """Nur bei gleichzeitigen Requests laufen Dependency und Endpunkt in verschiedenen Threads."""
    app = create_app(Settings(tmp_path), [NoteList()])

    @app.post("/notes/{note_id}")
    def write_note(note_id: str, db: Annotated[Database, Depends(get_db)]) -> None:
        db.save(Note.write(note_id, f"Notiz {note_id}"))

    with TestClient(app, raise_server_exceptions=False) as client, ThreadPoolExecutor(8) as pool:
        responses = list(pool.map(lambda n: client.post(f"/notes/{n}"), range(40)))

    assert [r.status_code for r in responses] == [200] * 40
