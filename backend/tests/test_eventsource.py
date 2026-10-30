import pytest

from coop_manager.eventsource import (
    Aggregate,
    ConcurrencyError,
    Event,
    EventStore,
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


@pytest.fixture
def store(tmp_path) -> EventStore:
    store = EventStore(connect(str(tmp_path / "eventstore.sqlite")))
    store.create_schema()
    yield store
    store.conn.close()


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
