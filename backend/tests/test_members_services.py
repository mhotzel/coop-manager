from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.db import Database, prepare
from coop_manager.eventsource import ConcurrencyError
from coop_manager.members import services
from coop_manager.members.projections import search_members
from coop_manager.members.status import APPLICANT, REJECTED
from coop_manager.members.values import LEGAL_ENTITY, NATURAL_PERSON, Address, PersonName

TODAY = date(2026, 11, 15)


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    yield db
    db.close()


def apply(db: Database, first_names="Erika", last_name="Muster", city="Musterstadt", **overrides) -> str:
    """Erfasst einen erfundenen Antrag und liefert die Mitglieds-ID."""
    data = {
        "person_type": NATURAL_PERSON,
        "name": PersonName(first_names=first_names, last_name=last_name, gender="w"),
        "address": Address(street="Hauptstraße", house_number="1", postal_code="12345", city=city),
        "application_date": date(2026, 11, 2),
        "shares_subscribed": 1,
        "contact": None,
        "actor": "test",
    }
    return services.apply_for_membership(db, **(data | overrides)).subject


def search(db: Database, query: str) -> list[str]:
    return [row.list_name for row in search_members(db.projections.conn, query, TODAY)]


def test_numbers_are_assigned_in_order(db):
    first, second = apply(db), apply(db, "Max", "Beispiel")

    assert services.get_member(db, first).member_number == 1
    assert services.get_member(db, second).member_number == 2


def test_application_appears_in_search(db):
    member_id = apply(db)

    [row] = search_members(db.projections.conn, "", TODAY)
    assert (row.id, row.member_number, row.list_name, row.status) == (member_id, 1, "Muster, Erika", APPLICANT)
    assert (row.street, row.postal_code, row.city) == ("Hauptstraße 1", "12345", "Musterstadt")


def test_search_needs_every_word_and_ignores_case(db):
    apply(db, "Erika", "Müller", city="Musterstadt")
    apply(db, "Max", "Müller", city="Beispieldorf")
    apply(db, "Erika", "Beispiel", city="Musterstadt")

    assert search(db, "MÜLLER") == ["Müller, Erika", "Müller, Max"]
    assert search(db, "müller muster") == ["Müller, Erika"]
    assert search(db, "2") == ["Müller, Max"]  # Mitgliedsnummer genau, nicht die 2 in „12345“
    assert search(db, "123") == ["Müller, Erika", "Müller, Max", "Beispiel, Erika"]  # Anfang der PLZ
    assert search(db, "123 erika beispiel") == ["Beispiel, Erika"]  # „Beispieldorf“ allein reicht nicht


def test_search_finds_company(db):
    apply(db, person_type=LEGAL_ENTITY, name=PersonName(company_name="Musterbau GmbH"))

    assert search(db, "bau") == ["Musterbau GmbH"]


def test_search_treats_percent_literally(db):
    apply(db)

    assert search(db, "%") == []


def test_changes_update_search(db):
    member_id = apply(db)

    services.change_name(db, member_id, PersonName(first_names="Erika", last_name="Beispiel", gender="w"), "test")
    services.change_address(db, member_id, Address("Dorfweg", "3", "54321", "Neustadt"), "test")

    assert search(db, "muster") == []
    assert search(db, "beispiel neustadt") == ["Beispiel, Erika"]


def test_rejection_shows_in_status(db):
    member_id = apply(db)

    services.reject(db, member_id, date(2026, 11, 10), TODAY, actor="test")

    [row] = search_members(db.projections.conn, "", TODAY)
    assert row.status == REJECTED


def test_rebuild_restores_projection(db):
    member_id = apply(db)
    services.withdraw(db, member_id, date(2026, 11, 10), TODAY, actor="test")
    before = search_members(db.projections.conn, "", TODAY)

    db.projections.rebuild(db.store)

    assert search_members(db.projections.conn, "", TODAY) == before


def test_concurrent_applications_get_different_numbers(db, tmp_path, monkeypatch):
    """Simuliert: Während dieser Antrag läuft, vergibt ein zweiter Antrag die Nummer 1."""
    load_numbers = services._load_numbers
    calls = []

    def load_and_let_someone_else_win(db_: Database):
        numbers = load_numbers(db_)  # sieht noch keine Nummer, würde also 1 vergeben
        calls.append(1)
        if len(calls) == 1:
            other = Database(tmp_path, PROJECTORS)  # eigene Verbindung, wie ein zweiter Request
            monkeypatch.setattr(services, "_load_numbers", load_numbers)
            apply(other, "Max", "Beispiel")
            monkeypatch.setattr(services, "_load_numbers", load_and_let_someone_else_win)
            other.close()
        return numbers

    monkeypatch.setattr(services, "_load_numbers", load_and_let_someone_else_win)

    member_id = apply(db)

    assert len(calls) == 2  # einmal gescheitert, einmal geklappt
    assert services.get_member(db, member_id).member_number == 2
    assert search(db, "") == ["Beispiel, Max", "Muster, Erika"]


def test_failed_save_stores_nothing(db):
    """save_all ist atomar: Scheitert das zweite Aggregat, fehlt auch das erste."""
    member_id = apply(db)
    stale = services.get_member(db, member_id)
    services.change_notes(db, member_id, "von jemand anderem", "test")  # stale ist jetzt veraltet
    numbers = services._load_numbers(db)
    numbers.assign(numbers.next_number(), "member-x")
    stale.change_notes("veraltet")

    with pytest.raises(ConcurrencyError):
        db.save_all([numbers, stale], "test")

    assert services._load_numbers(db).assigned == {1: member_id}
