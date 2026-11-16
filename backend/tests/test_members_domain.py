from datetime import date

import pytest

from coop_manager.core import DomainError
from coop_manager.members.domain import Member
from coop_manager.members.status import APPLICANT, REJECTED
from coop_manager.members.values import LEGAL_ENTITY, NATURAL_PERSON, Address, Contact, PersonName

ADDRESS = Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt")
ERIKA = PersonName(first_names="Erika", last_name="Muster", gender="w")


def apply(**overrides) -> Member:
    data = {
        "member_number": 42,
        "person_type": NATURAL_PERSON,
        "name": ERIKA,
        "address": ADDRESS,
        "application_date": date(2026, 11, 2),
        "shares_subscribed": 2,
    }
    return Member.apply(**(data | overrides))


def reloaded(member: Member) -> Member:
    """Baut das Mitglied aus seinen Events neu auf, wie nach dem Laden aus dem Event Store."""
    return Member.from_events(member.subject, member.uncommitted_events)


def test_apply_records_application_with_generated_address_lines():
    member = reloaded(apply())

    assert member.subject.startswith("member-")
    assert (member.member_number, member.shares_subscribed) == (42, 2)
    assert member.application_date == date(2026, 11, 2)
    assert member.name == ERIKA
    assert member.address_lines[:2] == ("Frau", "Erika Muster")


def test_apply_cleans_input():
    member = apply(
        name=PersonName(first_names="  Erika   Maria ", last_name="Muster", gender="W"),
        contact=Contact(phone=" 0123 / 456 ", email=" Erika@Example.org "),
    )

    assert member.name.first_names == "Erika Maria"
    assert member.name.gender == "w"
    assert member.contact == Contact(phone="0123 / 456", email="erika@example.org")


def test_apply_company():
    member = apply(person_type=LEGAL_ENTITY, name=PersonName(company_name="Musterbau GmbH"))

    assert member.address_lines[0] == "Musterbau GmbH"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"person_type": "verein"}, "Art der Person"),
        ({"name": PersonName(last_name="Muster")}, "Vornamen und Nachname"),
        ({"name": PersonName(company_name="Musterbau GmbH", first_names="E", last_name="M")}, "keinen Firmennamen"),
        ({"person_type": LEGAL_ENTITY, "name": PersonName(first_names="Erika", last_name="Muster")}, "Firmenname"),
        ({"name": PersonName(first_names="Erika", last_name="Muster", gender="x")}, "Geschlecht"),
        ({"address": Address(street="", house_number="", postal_code="12345", city="Musterstadt")}, "Straße"),
        ({"address": Address(street="Weg", house_number="", postal_code="1234", city="Musterstadt")}, "fünf Ziffern"),
        ({"contact": Contact(email="erika-at-example")}, "E-Mail"),
        ({"contact": Contact(phone="0123 abc")}, "Telefonnummer"),
        ({"shares_subscribed": 0}, "mindestens ein Anteil"),
        ({"member_number": 0}, "Mitgliedsnummer"),
    ],
)
def test_invalid_application_is_rejected(overrides, message):
    with pytest.raises(DomainError, match=message):
        apply(**overrides)


def test_foreign_postal_code_is_free():
    address = Address(street="Dorfweg", house_number="", postal_code="1010", city="Wien", country="Österreich")

    assert apply(address=address).address.postal_code == "1010"


def test_change_name():
    member = apply()

    member.change_name(PersonName(first_names="Erika", last_name="Beispiel", gender="w"))

    assert reloaded(member).name.last_name == "Beispiel"
    assert member.uncommitted_events[-1].type == "member.name-changed"


def test_change_name_does_not_touch_address_lines():
    """Die Zeilen ändert nur „Adresszeilen erzeugen“ bzw. die Pflege von Hand."""
    member = apply()

    member.change_name(PersonName(first_names="Erika", last_name="Beispiel", gender="w"))

    assert reloaded(member).address_lines[1] == "Erika Muster"


def test_person_type_rules_apply_on_change():
    member = apply()

    with pytest.raises(DomainError, match="keinen Firmennamen"):
        member.change_name(PersonName(company_name="Musterbau GmbH", first_names="Erika", last_name="Muster"))


@pytest.mark.parametrize(
    "change, event_type",
    [
        (lambda m: m.change_address(Address("Neuer Weg", "2", "12345", "Musterstadt")), "member.address-changed"),
        (lambda m: m.change_contact(Contact(email="erika@example.org")), "member.contact-changed"),
        (lambda m: m.change_address_lines(["An die Erben", "", "", "", "", ""]), "member.address-lines-changed"),
        (lambda m: m.change_salutation("Liebe Familie Muster"), "member.salutation-changed"),
        (lambda m: m.change_mail_preference(True), "member.mail-preference-changed"),
        (lambda m: m.change_notes("Erbnachweis liegt vor.\nAkte 7"), "member.notes-changed"),
    ],
)
def test_each_change_has_its_own_event(change, event_type):
    member = apply()

    change(member)

    assert member.uncommitted_events[-1].type == event_type
    assert reloaded(member).version == 2


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.change_name(PersonName(first_names=" Erika", last_name="Muster ", gender="w")),
        lambda m: m.change_address(Address("Hauptstraße", "1", "12345", "Musterstadt")),
        lambda m: m.change_contact(Contact()),
        lambda m: m.change_salutation(""),
        lambda m: m.change_mail_preference(False),
        lambda m: m.change_notes("  "),
    ],
)
def test_unchanged_values_record_nothing(change):
    member = apply()

    change(member)

    assert len(member.uncommitted_events) == 1


def test_notes_keep_line_breaks():
    member = apply()

    member.change_notes("  Zeile 1\nZeile 2  ")

    assert reloaded(member).notes == "Zeile 1\nZeile 2"


def test_address_lines_must_be_six():
    with pytest.raises(DomainError, match="genau 6"):
        apply().change_address_lines(["Frau", "Erika Muster"])


# --- Zulassung, Ablehnung, Rücknahme und Status ---


def test_status_follows_the_dates():
    member = apply()  # Antrag am 02.11.2026

    assert member.status(date(2026, 11, 1)) is None
    assert member.status(date(2026, 11, 2)) == APPLICANT

    member.reject(date(2026, 11, 20))

    assert reloaded(member).status(date(2026, 11, 19)) == APPLICANT
    assert reloaded(member).status(date(2026, 11, 20)) == REJECTED


def test_rejection_is_not_a_withdrawal():
    member = apply()
    member.reject(date(2026, 11, 10))

    assert reloaded(member).rejection_date == date(2026, 11, 10)
    assert not reloaded(member).withdrawn


def test_admit():
    member = apply()

    member.admit(date(2026, 11, 10))

    assert reloaded(member).admission_date == date(2026, 11, 10)
    assert reloaded(member).status(date(2026, 12, 1)) == APPLICANT  # Mitglied erst mit Geldeingang


def test_admit_twice_is_rejected():
    member = apply()
    member.admit(date(2026, 11, 10))

    with pytest.raises(DomainError, match="bereits zugelassen"):
        member.admit(date(2026, 11, 11))


def test_board_cannot_reject_after_admission():
    member = apply()
    member.admit(date(2026, 11, 10))

    with pytest.raises(DomainError, match="nicht mehr abgelehnt"):
        member.reject(date(2026, 11, 20))


def test_withdraw_after_admission_is_allowed():
    member = apply()
    member.admit(date(2026, 11, 10))

    member.withdraw(date(2026, 11, 20))

    assert reloaded(member).status(date(2026, 11, 20)) == REJECTED
    assert reloaded(member).withdrawn


@pytest.mark.parametrize("decide", [lambda m, d: m.admit(d), lambda m, d: m.reject(d), lambda m, d: m.withdraw(d)])
def test_nothing_after_rejection(decide):
    member = apply()
    member.withdraw(date(2026, 11, 5))

    with pytest.raises(DomainError, match="bereits abgelehnt oder zurückgenommen"):
        decide(member, date(2026, 11, 6))


def test_decision_not_before_application():
    with pytest.raises(DomainError, match="nicht vor dem Antrag"):
        apply().admit(date(2026, 11, 1))
