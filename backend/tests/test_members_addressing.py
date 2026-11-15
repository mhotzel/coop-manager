import pytest

from coop_manager.members.addressing import address_lines, list_name, long_address_lines, salutation
from coop_manager.members.values import LEGAL_ENTITY, NATURAL_PERSON, Address, PersonName

ADDRESS = Address(street="Hauptstraße", house_number="1a", postal_code="12345", city="Musterstadt")
ERIKA = PersonName(first_names="Erika Maria", last_name="Muster", gender="w")
COMPANY = PersonName(company_name="Musterbau GmbH")


def test_lines_for_woman():
    assert address_lines(NATURAL_PERSON, ERIKA, ADDRESS) == (
        "Frau",
        "Erika Maria Muster",
        "Hauptstraße 1a",
        "12345 Musterstadt",
        "",
        "",
    )


def test_lines_for_man_with_title_abroad():
    name = PersonName(title="Dr.", first_names="Max", last_name="Beispiel", gender="m")
    address = Address(street="Dorfweg", house_number="", postal_code="1010", city="Wien", country="Österreich")

    assert address_lines(NATURAL_PERSON, name, address) == (
        "Herrn",
        "Dr. Max Beispiel",
        "Dorfweg",
        "1010 Wien",
        "ÖSTERREICH",
        "",
    )


@pytest.mark.parametrize("gender", ["d", ""])
def test_lines_without_form_of_address_move_up(gender):
    name = PersonName(first_names="Kim", last_name="Muster", gender=gender)

    assert address_lines(NATURAL_PERSON, name, ADDRESS)[:2] == ("Kim Muster", "Hauptstraße 1a")


def test_lines_for_company_with_contact_person():
    name = PersonName(company_name="Musterbau GmbH", first_names="Erika", last_name="Muster", gender="w")

    assert address_lines(LEGAL_ENTITY, name, ADDRESS)[:3] == (
        "Musterbau GmbH",
        "z. H. Frau Erika Muster",
        "Hauptstraße 1a",
    )


def test_lines_for_company_without_contact_person():
    assert address_lines(LEGAL_ENTITY, COMPANY, ADDRESS)[:2] == ("Musterbau GmbH", "Hauptstraße 1a")


def test_germany_is_not_printed():
    address = Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt", country="DE")

    assert "DE" not in address_lines(NATURAL_PERSON, ERIKA, address)


def test_long_lines_are_reported():
    lines = ("Frau", "x" * 36, "", "", "", "y" * 35)

    assert long_address_lines(lines) == [2]


@pytest.mark.parametrize(
    "name, expected",
    [
        (ERIKA, "Sehr geehrte Frau Muster"),
        (
            PersonName(title="Prof. Dr.", first_names="Max", last_name="Beispiel", gender="m"),
            "Sehr geehrter Herr Prof. Dr. Beispiel",
        ),
        (PersonName(first_names="Kim", last_name="Muster", gender="d"), "Liebes Mitglied"),
        (PersonName(first_names="Kim", last_name="Muster"), "Liebes Mitglied"),
    ],
)
def test_salutation_for_natural_persons(name, expected):
    assert salutation(NATURAL_PERSON, name) == expected


def test_salutation_for_company():
    assert salutation(LEGAL_ENTITY, COMPANY) == "Sehr geehrte Damen und Herren"


def test_override_wins_over_generated_salutation():
    assert salutation(NATURAL_PERSON, ERIKA, override="Liebe Familie Muster") == "Liebe Familie Muster"


def test_deceased_always_get_formal_salutation():
    assert salutation(NATURAL_PERSON, ERIKA, override="Liebe Erika", deceased=True) == "Sehr geehrte Damen und Herren"


def test_list_name():
    assert list_name(NATURAL_PERSON, ERIKA) == "Muster, Erika Maria"
    assert list_name(LEGAL_ENTITY, COMPANY) == "Musterbau GmbH"
