"""Migration aus dem Altsystem am Mitglied: `Member.migrate` und `Member.migrate_version`.

Alle Daten sind erfunden (siehe AGENTS.md).
"""

from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import pytest

from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members.domain import Member, PersonData
from coop_manager.members.projections import search_members
from coop_manager.members.status import MEMBER
from coop_manager.members.values import LEGAL_ENTITY, NATURAL_PERSON, Address, Contact, PersonName

TODAY = date(2026, 11, 30)  # Tag der Migration; die Altdaten liegen Jahre davor
ENTRY = date(2014, 11, 1)
ERIKA = PersonName(first_names="Erika", last_name="Muster", gender="w")
ADDRESS = Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt")
LINES = ("Frau", "Erika Muster", "Hauptstraße 1", "12345 Musterstadt", "", "")
DATA = PersonData(name=ERIKA, address=ADDRESS, address_lines=LINES)


def migrate(**overrides) -> Member:
    args = {
        "member_number": 7,
        "person_type": NATURAL_PERSON,
        "data": DATA,
        "application_date": ENTRY,
        "shares_subscribed": 2,
    }
    return Member.migrate(**(args | overrides))


def event_types(member: Member) -> list[str]:
    return [event.type for event in member.uncommitted_events]


def reloaded(member: Member) -> Member:
    """Baut das Mitglied aus seinen Events neu auf, wie nach dem Laden aus dem Event Store."""
    return Member.from_events(member.subject, member.uncommitted_events)


def test_migrate_records_application_with_given_address_lines():
    lines = ("Frau", "Erika Muster", "c/o Altenheim", "Hauptstraße 1", "12345 Musterstadt", "VERZOGEN")
    member = migrate(data=replace(DATA, address_lines=lines))

    assert event_types(member) == ["member.applied"]
    member = reloaded(member)
    assert (member.member_number, member.shares_subscribed) == (7, 2)
    assert member.application_date == ENTRY
    assert member.name == ERIKA
    assert member.address_lines == lines  # übernommen, nicht erzeugt


def test_migrate_cleans_input():
    data = replace(
        DATA,
        name=PersonName(first_names=" Erika  Maria ", last_name="Muster", gender="W"),
        contact=Contact(phone=" 0123 / 456 ", email=" Erika@Example.org "),
    )
    member = reloaded(migrate(data=data))

    assert member.name.first_names == "Erika Maria"
    assert member.name.gender == "w"
    assert member.contact == Contact(phone="0123 / 456", email="erika@example.org")


def test_migrate_allows_missing_address():
    data = replace(DATA, address=Address(street="", house_number="", postal_code="", city="Musterstadt"))

    member = reloaded(migrate(data=data))

    assert member.address.street == ""
    assert member.address.city == "Musterstadt"


def test_migrate_still_checks_given_postal_code():
    data = replace(DATA, address=replace(ADDRESS, postal_code="1234"))

    with pytest.raises(DomainError, match="fünf Ziffern"):
        migrate(data=data)


def test_migrate_still_needs_name():
    with pytest.raises(DomainError, match="Nachname"):
        migrate(data=replace(DATA, name=PersonName(first_names="Erika")))


def test_migrate_company():
    data = replace(DATA, name=PersonName(company_name="Musterverein e.V."))

    member = reloaded(migrate(person_type=LEGAL_ENTITY, data=data))

    assert member.name.company_name == "Musterverein e.V."


def test_migrate_records_salutation_mail_preference_and_notes_only_when_set():
    data = replace(DATA, salutation="Liebe Erika", no_mail=True, notes="Altsystem: Spende 50 EUR")

    member = migrate(data=data)

    assert event_types(member) == [
        "member.applied",
        "member.salutation-changed",
        "member.mail-preference-changed",
        "member.notes-changed",
    ]
    member = reloaded(member)
    assert (member.salutation, member.no_mail, member.notes) == ("Liebe Erika", True, "Altsystem: Spende 50 EUR")


def test_migrate_version_records_only_changed_parts_with_valid_from():
    member = reloaded(migrate())
    moved = replace(ADDRESS, street="Bergweg", house_number="5")
    lines = ("Frau", "Erika Muster", "Bergweg 5", "12345 Musterstadt", "", "")
    data = replace(DATA, address=moved, address_lines=lines)

    member.migrate_version(data, valid_from=date(2024, 6, 30))

    events = member.uncommitted_events
    assert [e.type for e in events] == ["member.address-changed", "member.address-lines-changed"]
    assert all(e.data["valid_from"] == "2024-06-30" for e in events)
    assert member.address == moved


def test_migrate_version_without_change_records_nothing():
    member = reloaded(migrate())

    member.migrate_version(DATA, valid_from=date(2024, 6, 30))

    assert member.uncommitted_events == []


def test_migrate_does_not_add_valid_from_to_first_version():
    member = migrate(data=replace(DATA, notes="Hinweis"))

    assert all("valid_from" not in e.data for e in member.uncommitted_events)


def test_migrated_member_enters_on_old_entry_date():
    """So nutzt die Migration die normalen Methoden: Zulassung und Zahlung am alten Eintritt."""
    member = reloaded(migrate())

    member.admit(ENTRY, TODAY)
    member.record_payment(ENTRY, TODAY)

    assert member.entry_date() == ENTRY
    assert member.status(ENTRY) == MEMBER
    assert member.status(TODAY) == MEMBER


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    yield db
    db.close()


def test_migrated_history_shows_current_state_in_member_list(db):
    member = migrate()
    member.migrate_version(replace(DATA, name=replace(ERIKA, last_name="Neumann")), valid_from=date(2025, 3, 1))
    db.save(member, "migration")

    rows = search_members(db.projections.conn, "neumann", TODAY)

    assert [(row.member_number, row.list_name) for row in rows] == [(7, "Neumann, Erika")]
    assert all(event.actor == "migration" for event in db.store.read_stream(member.subject))
