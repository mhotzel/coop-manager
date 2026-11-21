"""Verlauf der Personendaten (Schritt 11); alle Daten erfunden."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import pytest

from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import NotFoundError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.domain import Member, PersonData
from coop_manager.members.history import member_history
from coop_manager.members.values import NATURAL_PERSON, Address, Contact, PersonName
from coop_manager.users import services as users
from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY, ADMIN

ERIKA = PersonName(first_names="Erika", last_name="Muster", gender="w")
ADDRESS = Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt")


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    yield db
    db.close()


def apply(db: Database, actor: str = "cli") -> str:
    return services.apply_for_membership(
        db,
        person_type=NATURAL_PERSON,
        name=ERIKA,
        address=ADDRESS,
        application_date=date(2026, 11, 2),
        shares_subscribed=1,
        contact=Contact(phone="0123 456"),
        actor=actor,
    ).subject


def test_application_is_the_oldest_entry(db):
    member_id = apply(db)

    history = member_history(db, member_id)

    assert [(e.part, e.before, e.after) for e in history] == [
        ("Adresszeilen", "", "Frau / Erika Muster / Hauptstraße 1 / 12345 Musterstadt"),
        ("Kontakt", "", "Telefon 0123 456"),
        ("Anschrift", "", "Hauptstraße 1, 12345 Musterstadt"),
        ("Name", "", "Muster, Erika (weiblich)"),
    ]
    assert {(e.valid_from, e.actor) for e in history} == {(date(2026, 11, 2), "Kommandozeile")}


def test_changes_show_before_and_after_newest_first(db):
    clara = users.register_user(db, "clara", "Clara Chefin", "Geheim-123", ACCOUNTING, actor="cli").subject
    member_id = apply(db)
    services.change_address(db, member_id, replace(ADDRESS, city="Bergdorf"), actor=clara)
    services.change_notes(db, member_id, "Zieht im Mai um.", actor=clara)
    services.change_salutation(db, member_id, "Liebe Erika", actor=clara)
    services.change_mail_preference(db, member_id, True, actor=clara)

    newest = member_history(db, member_id)[:4]

    assert [(e.part, e.before, e.after) for e in newest] == [
        ("Keine Post", "nein", "ja"),
        ("Briefanrede", "(erzeugt)", "Liebe Erika"),
        ("Hinweise", "", "Zieht im Mai um."),
        ("Anschrift", "Hauptstraße 1, 12345 Musterstadt", "Hauptstraße 1, 12345 Bergdorf"),
    ]
    assert {(e.actor, e.valid_from) for e in newest} == {("Clara Chefin", None)}  # gültig ab Speichern


def test_unchanged_saving_adds_nothing(db):
    member_id = apply(db)
    before = len(member_history(db, member_id))

    services.change_address(db, member_id, ADDRESS, actor="cli")

    assert len(member_history(db, member_id)) == before


def test_migrated_history_uses_valid_from(db):
    lines = ("Frau", "Erika Muster", "Hauptstraße 1", "12345 Altdorf", "", "")
    data = PersonData(name=ERIKA, address=replace(ADDRESS, city="Altdorf"), address_lines=lines)
    member = Member.migrate(7, NATURAL_PERSON, data, date(2014, 11, 1), 1)
    member.migrate_version(replace(data, address=ADDRESS), date(2024, 6, 30))
    db.save(member, "migration")

    newest = member_history(db, member.subject)[0]

    assert (newest.part, newest.after, newest.valid_from, newest.actor) == (
        "Anschrift",
        "Hauptstraße 1, 12345 Musterstadt",
        date(2024, 6, 30),
        "Migration",
    )
    assert newest.before == "Hauptstraße 1, 12345 Altdorf"


def test_status_events_are_not_part_of_the_history(db):
    member_id = apply(db)
    before = len(member_history(db, member_id))

    services.admit(db, member_id, date(2026, 11, 5), date(2026, 11, 30), actor="cli")

    assert len(member_history(db, member_id)) == before


def test_unknown_member(db):
    with pytest.raises(NotFoundError):
        member_history(db, "member-gibt-es-nicht")


def test_api_history(client, db, register, login):
    member_id = apply(db)
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    response = client.get(f"/api/members/{member_id}/history")

    assert response.status_code == 200
    assert response.json()[-1] | {"recorded_at": None} == {
        "recorded_at": None,
        "valid_from": "2026-11-02",
        "actor": "Kommandozeile",
        "part": "Name",
        "before": "",
        "after": "Muster, Erika (weiblich)",
    }
    assert client.get("/api/members/member-gibt-es-nicht/history").status_code == 404


def test_api_history_needs_accounting_role(client, db, register, login):
    member_id = apply(db)
    register("ada", ADMIN, full_name="Ada Admin")
    login("ada")

    assert client.get(f"/api/members/{member_id}/history").status_code == 403
