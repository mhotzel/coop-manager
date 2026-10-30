import sqlite3

import pytest

from coop_manager.eventsource import (
    Aggregate,
    ConcurrencyError,
    Event,
    EventStore,
    Projections,
    Projector,
    UnknownEventError,
    connect,
    on,
)


class Party(Aggregate):
    """Erfundenes Mini-Aggregat, nur für diese Tests."""

    def __init__(self, subject: str) -> None:
        super().__init__(subject)
        self.name = ""
        self.archived = False

    @classmethod
    def register(cls, subject: str, name: str) -> Party:
        party = cls(subject)
        party._record("party.registered", name=name)
        return party

    def rename(self, name: str) -> None:
        if name != self.name:
            self._record("party.renamed", name=name)

    def archive(self) -> None:
        self._record("party.archived")

    @on("party.registered", "party.renamed")
    def _set_name(self, event: Event) -> None:
        self.name = event.data["name"]

    @on("party.archived")
    def _archived(self, event: Event) -> None:
        self.archived = True


class PartyList(Projector):
    schema = "CREATE TABLE IF NOT EXISTS party_list (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)"
    tables = ("party_list",)

    @on("party.registered")
    def _registered(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("INSERT INTO party_list VALUES (?, ?)", (event.subject, event.data["name"]))

    @on("party.renamed")
    def _renamed(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("UPDATE party_list SET name = ? WHERE id = ?", (event.data["name"], event.subject))


class EventCounter(Projector):
    schema = """
    CREATE TABLE IF NOT EXISTS event_count (n INTEGER NOT NULL);
    INSERT INTO event_count SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM event_count);
    """

    def reset(self, conn: sqlite3.Connection) -> None:
        conn.execute("UPDATE event_count SET n = 0")

    @on("party.registered", "party.renamed", "party.archived")
    def _count(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute("UPDATE event_count SET n = n + 1")


@pytest.fixture
def store(tmp_path) -> EventStore:
    store = EventStore(connect(str(tmp_path / "eventstore.sqlite")))
    store.create_schema()
    yield store
    store.conn.close()


@pytest.fixture
def make_projections(tmp_path):
    opened: list[Projections] = []

    def make(*projectors: Projector) -> Projections:
        projections = Projections(connect(str(tmp_path / "projections.sqlite")), projectors)
        projections.create_schema()
        opened.append(projections)
        return projections

    yield make
    for projections in opened:
        projections.conn.close()


@pytest.fixture
def projections(make_projections) -> Projections:
    return make_projections(PartyList())


def party_names(projections: Projections) -> list[str]:
    rows = projections.conn.execute("SELECT name FROM party_list ORDER BY name")
    return [row["name"] for row in rows]


def event_count(projections: Projections) -> int:
    return projections.conn.execute("SELECT n FROM event_count").fetchone()["n"]


def test_recorded_events_change_state_and_version():
    party = Party.register("p-1", "Bäckerei Schmidt")
    party.rename("Bäckerei Schmidt GmbH")

    assert party.name == "Bäckerei Schmidt GmbH"
    assert party.version == 2
    assert [e.version for e in party.uncommitted_events] == [1, 2]


def test_one_handler_can_serve_several_event_types():
    assert Party._handlers["party.registered"] is Party._handlers["party.renamed"]


def test_unknown_event_type_is_rejected():
    with pytest.raises(UnknownEventError):
        Party.from_events("p-1", [Event(type="party.exploded", subject="p-1", version=1)])


def test_saved_aggregate_can_be_loaded(store):
    party = Party.register("p-1", "Molkerei Müller")
    store.save(party, actor="matthias")
    assert party.uncommitted_events == []

    loaded = store.load(Party, "p-1")

    assert loaded.name == "Molkerei Müller"
    assert loaded.version == 1
    assert store.read_stream("p-1")[0].actor == "matthias"


def test_stored_event_comes_back_unchanged(store):
    event = Event(type="party.registered", subject="p-1", data={"name": "Müller"}, version=1, actor="matthias")
    store.append([event])

    assert store.read_stream("p-1") == [event]


def test_load_of_unknown_subject_returns_none(store):
    assert store.load(Party, "does-not-exist") is None


def test_concurrent_modification_is_detected(store):
    store.save(Party.register("p-1", "Alt"))
    first = store.load(Party, "p-1")
    second = store.load(Party, "p-1")

    first.rename("Neu A")
    store.save(first)
    second.rename("Neu B")

    with pytest.raises(ConcurrencyError):
        store.save(second)
    assert store.load(Party, "p-1").name == "Neu A"


def test_events_of_one_save_are_stored_all_or_none(store):
    events = [
        Event(type="party.registered", subject="p-1", data={"name": "A"}, version=1),
        Event(type="party.registered", subject="p-1", data={"name": "B"}, version=1),
    ]

    with pytest.raises(ConcurrencyError):
        store.append(events)

    assert store.read_stream("p-1") == []


def test_read_all_returns_events_after_the_given_position(store):
    store.save(Party.register("p-1", "Eins"))
    store.save(Party.register("p-2", "Zwei"))

    positions = [position for position, _ in store.read_all()]

    assert len(positions) == 2
    assert [event.subject for _, event in store.read_all(after=positions[0])] == ["p-2"]


def test_event_store_and_projections_live_in_separate_databases(store, projections):
    store.save(Party.register("p-1", "Eins"))
    projections.catch_up(store)

    event_tables = {r["name"] for r in store.conn.execute("SELECT name FROM sqlite_master")}
    assert "party_list" not in event_tables
    assert party_names(projections) == ["Eins"]


def test_catch_up_processes_each_event_only_once(store, make_projections):
    projections = make_projections(EventCounter())
    store.save(Party.register("p-1", "Eins"))
    projections.catch_up(store)
    store.save(Party.register("p-2", "Zwei"))
    projections.catch_up(store)
    projections.catch_up(store)

    assert event_count(projections) == 2


def test_failing_projection_keeps_event_and_stays_at_old_checkpoint(store, projections):
    store.save(Party.register("p-1", "Doppelt"))
    store.save(Party.register("p-2", "Doppelt"))

    with pytest.raises(sqlite3.IntegrityError):
        projections.catch_up(store)

    # Das Event ist gespeichert, die Projektion wurde als Ganzes zurückgerollt und bleibt zurück.
    assert len(store.read_stream("p-2")) == 1
    assert party_names(projections) == []

    party = store.load(Party, "p-2")
    party.rename("Einzeln")
    store.save(party)
    with pytest.raises(sqlite3.IntegrityError):
        projections.catch_up(store)  # weiter blockiert: Events werden der Reihe nach abgespielt


def test_rebuild_replays_history(store, projections):
    store.save(Party.register("p-1", "Eins"))
    store.save(Party.register("p-2", "Zwei"))
    projections.catch_up(store)
    projections.conn.execute("DELETE FROM party_list")

    projections.rebuild(store)

    assert party_names(projections) == ["Eins", "Zwei"]


def test_projector_added_later_catches_up_from_the_beginning(store, projections, make_projections):
    store.save(Party.register("p-1", "Eins"))
    projections.catch_up(store)

    extended = make_projections(PartyList(), EventCounter())
    extended.catch_up(store)

    assert event_count(extended) == 1
    assert party_names(extended) == ["Eins"]
