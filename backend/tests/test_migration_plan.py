"""Fachlogik der Migration: `make_plan` aus Altdaten und Einzelfällen; alle Daten erfunden."""

from dataclasses import replace
from datetime import date, datetime

from coop_manager.accounts.domain import ADDITIONAL_SHARES, SHARE_DONATION, SUBSCRIPTION, TRANSFER
from coop_manager.members.domain import Member
from coop_manager.members.status import DECEASED, EXITED, MEMBER, NOTICE_GIVEN, REJECTED
from coop_manager.members.values import LEGAL_ENTITY, NATURAL_PERSON
from coop_manager.migration.plan import MigrationPlan, PersonPlan, make_plan
from coop_manager.migration.source import Decisions, LegacyBooking, LegacyData, LegacyPerson

COOP = 9999
TODAY = date(2026, 11, 30)
ENTRY = date(2014, 11, 1)
LINES = ("Frau", "Erika Muster", "Hauptstraße 1", "12345 Musterstadt", "", "")


def person(number: int, **values) -> LegacyPerson:
    data = {
        "number": number,
        "company": "",
        "gender": "w",
        "last_name": "Muster",
        "first_names": "Erika",
        "title": "",
        "country": "",
        "postal_code": "12345",
        "city": "Musterstadt",
        "street": "Hauptstraße",
        "house_number": "1",
        "phone": "",
        "email": "",
        "salutation": "Sehr geehrte Frau Muster",
        "address_lines": LINES,
        "entry": ENTRY,
        "notice": None,
        "exit": None,
        "death": None,
        "no_mail": False,
        "notes": "",
    }
    return LegacyPerson(**(data | values))


def booking(id: int, debit: int, credit: int, shares: int = 1, day: date = ENTRY, text: str = "Beitritt"):
    return LegacyBooking(id=id, debit=debit, credit=credit, shares=shares, amount=shares * 5000, day=day, text=text)


def plan(people, bookings=(), history=None, **decisions) -> MigrationPlan:
    data = LegacyData(
        people={p.number: p for p in [person(COOP, company="Genossenschaft", entry=None), *people]},
        history=history or {},
        bookings=list(bookings),
    )
    return make_plan(data, Decisions(**decisions))


def only(result: MigrationPlan, number: int) -> PersonPlan:
    assert result.problems == []
    return next(p for p in result.persons if p.number == number)


def test_member_enters_on_old_entry_date_with_first_payment():
    result = plan([person(7)], [booking(1, COOP, 7, shares=2, day=date(2014, 11, 11))])

    p = only(result, 7)
    assert (p.person_type, p.application_date, p.entry_date, p.shares_subscribed) == (NATURAL_PERSON, ENTRY, ENTRY, 2)
    assert p.first.address_lines == LINES
    assert p.first.salutation == ""  # wie erzeugt, also keine abweichende Briefanrede
    assert result.bookings[0].kind == SUBSCRIPTION
    assert result.bookings[0].value_date == date(2014, 11, 11)


def test_company_and_different_salutation():
    company = person(7, company="Musterverein e.V.", salutation="Sehr geehrter Herr Muster")

    p = only(plan([company], [booking(1, COOP, 7)]), 7)

    assert p.person_type == LEGAL_ENTITY
    assert p.first.salutation == "Sehr geehrter Herr Muster"


def test_invalid_email_is_dropped():
    p = only(plan([person(7, email="mal fragen")], [booking(1, COOP, 7)]), 7)

    assert p.first.contact.email == ""
    assert "mal fragen" not in p.first.notes


def test_skipped_person_and_booking_are_listed_with_reason():
    result = plan(
        [person(7), person(8, entry=None)],
        [booking(1, COOP, 7), booking(2, COOP, COOP, text="Testbuchung")],
        skip_persons=frozenset({8}),
        skip_bookings={2: "Testbuchung"},
    )

    assert result.problems == []
    assert [p.number for p in result.persons] == [7]
    assert result.skipped_persons == [8]
    assert result.skipped_bookings == [(2, "Testbuchung")]


def test_rejected_person_gets_skipped_bookings_as_notes():
    note = booking(5, 7, 7, shares=4, day=date(2014, 11, 9), text="Spende 200 EUR")
    result = plan([person(7, entry=None)], [note], rejected=frozenset({7}), skip_bookings={5: "Notiz"})

    p = only(result, 7)
    assert (p.application_date, p.withdrawal_date, p.entry_date) == (date(2014, 11, 9), date(2014, 11, 9), None)
    assert p.shares_subscribed == 4
    assert p.first.notes == "Altsystem 2014-11-09: Spende 200 EUR (200,00 €, 4 Anteile)"
    assert result.bookings == []


def test_rejected_person_without_booking_uses_entry_date():
    p = only(plan([person(7)], rejected=frozenset({7})), 7)

    assert (p.application_date, p.withdrawal_date, p.shares_subscribed) == (ENTRY, ENTRY, 1)


def test_history_versions_with_valid_from_and_unchanged_ones_dropped():
    first = replace(person(7), last_update=datetime(1900, 1, 1))
    status_only = replace(person(7, exit=date(2023, 1, 1)), last_update=datetime(2023, 6, 1))
    renamed = replace(person(7, last_name="Neumann"), last_update=datetime(2024, 6, 30, 14, 12))
    current = person(7, last_name="Neumann", city="Bergdorf")

    p = only(plan([current], [booking(1, COOP, 7)], history={7: [first, status_only, renamed]}), 7)

    assert p.first.name.last_name == "Muster"
    assert [(valid_from, v.name.last_name, v.address.city) for valid_from, v in p.versions] == [
        (date(2024, 6, 30), "Neumann", "Musterstadt"),
        (None, "Neumann", "Bergdorf"),  # aktueller Stand nach der letzten Version: Datum unbekannt
    ]


def test_second_payment_is_additional_shares():
    result = plan([person(7)], [booking(1, COOP, 7, shares=2), booking(2, COOP, 7, shares=3, day=date(2015, 6, 21))])

    p = only(result, 7)
    assert p.shares_subscribed == 2
    assert p.additional_shares == [(date(2015, 6, 21), 3)]
    assert [b.kind for b in result.bookings] == [SUBSCRIPTION, ADDITIONAL_SHARES]


def test_donation_of_all_shares_is_exit_and_differing_exit_date_becomes_note():
    gone = date(2023, 7, 3)
    result = plan([person(7, exit=date(2023, 6, 27))], [booking(1, COOP, 7, shares=2), booking(2, 7, COOP, 2, gone)])

    p = only(result, 7)
    assert p.donation_date == gone
    assert p.first.notes == "Altsystem: Austritt am 2023-06-27"
    assert result.bookings[1].kind == SHARE_DONATION


def test_partial_donation_is_a_problem():
    result = plan([person(7)], [booking(1, COOP, 7, shares=2), booking(2, 7, COOP, 1, date(2023, 7, 3))])

    assert result.problems == [
        "Buchung 2 (2023-07-03, 7 an 9999): Spende, aber es bleiben 1 Anteile; gespendet wird immer alles."
    ]


def test_transfer_of_all_shares_to_heir():
    died, moved = date(2020, 1, 1), date(2021, 9, 7)
    heir = person(8, first_names="Max", entry=moved)
    result = plan(
        [person(7, death=died, exit=moved), heir],
        [booking(1, COOP, 7, shares=3), booking(2, 7, 8, shares=3, day=moved)],
    )

    giver, receiver = only(result, 7), only(result, 8)
    assert (giver.date_of_death, giver.transfer_date) == (died, moved)
    assert giver.first.notes == ""  # Austritt = Tag der Umbuchung, keine Notiz
    assert (receiver.entry_date, receiver.shares_subscribed) == (moved, 3)
    assert result.bookings[1].kind == TRANSFER


def test_partial_transfer_is_no_exit():
    result = plan([person(7), person(8)], [booking(1, COOP, 7, 3), booking(2, COOP, 8), booking(3, 7, 8, 1)])

    assert only(result, 7).transfer_date is None


def test_bookings_in_order_of_day_then_old_id():
    day = date(2021, 8, 27)
    # Erbe empfängt und spendet am selben Tag; die Liste kommt durcheinander herein.
    result = plan(
        [person(7), person(8, entry=day)],
        [booking(4, 8, COOP, 4, day), booking(3, 7, 8, 4, day), booking(1, COOP, 7, 4)],
    )

    assert result.problems == []
    assert [b.legacy_id for b in result.bookings] == [1, 3, 4]
    assert only(result, 8).donation_date == day


def test_notice_is_kept_with_exit_after_period():
    p = only(plan([person(7, notice=date(2021, 9, 3))], [booking(1, COOP, 7)]), 7)

    assert p.notice == (date(2021, 9, 3), date(2023, 12, 31))


def test_notice_after_death_becomes_note():
    died, noticed = date(2018, 9, 29), date(2019, 2, 2)
    p = only(plan([person(7, death=died, notice=noticed)], [booking(1, COOP, 7)]), 7)

    assert p.notice is None
    assert p.first.notes == "Altsystem: Kündigung am 2019-02-02, nicht übernommen (schon ausgeschieden)"


def test_notes_are_appended_to_existing_notes():
    p = only(plan([person(7, notes="Erbschein liegt vor", exit=date(2023, 1, 1))], [booking(1, COOP, 7)]), 7)

    assert p.first.notes == "Erbschein liegt vor\nAltsystem: Austritt am 2023-01-01"


def test_problems():
    result = plan(
        [person(7, entry=None), person(8), person(9)],
        [booking(1, 9, 9), booking(2, COOP, COOP)],
        rejected=frozenset({9, 404}),
        skip_bookings={77: "gibt es nicht"},
    )

    assert result.problems == [
        "Person 404 aus migration.toml gibt es nicht.",
        "Buchung 77 aus migration.toml gibt es nicht.",
        "Buchung 1 (2014-11-01, 9 an 9): Konto 9 ist kein übernommenes Mitglied.",
        "Buchung 2 (2014-11-01, 9999 an 9999): Soll und Haben sind gleich.",
        "Person 7: kein Eintritt und nicht in rejected.",
        "Person 8: Eintritt, aber keine Einzahlung und keine empfangene Umbuchung.",
    ]


def test_plan_is_accepted_by_member_methods():
    """Spielt einen kleinen Plan im Speicher mit den Methoden am Mitglied durch (so wie später `run.py`)."""
    died, moved = date(2020, 1, 1), date(2021, 9, 7)
    result = plan(
        [
            person(7, death=died),
            person(8, first_names="Max", entry=moved),
            person(9, notice=date(2021, 9, 3)),
            person(10),  # abgelehnt: Eintritt im Altsystem, aber nie eingezahlt
        ],
        [booking(1, COOP, 7, 3), booking(2, 7, 8, 3, moved), booking(3, COOP, 9)],
        rejected=frozenset({10}),
    )
    assert result.problems == []

    members = {}
    for p in result.persons:
        member = Member.migrate(p.number, p.person_type, p.first, p.application_date, p.shares_subscribed)
        for valid_from, version in p.versions:
            member.migrate_version(version, valid_from)
        if p.entry_date is not None:
            member.admit(p.entry_date, TODAY)
            member.record_payment(p.entry_date, TODAY)
        if p.withdrawal_date is not None:
            member.withdraw(p.withdrawal_date, TODAY)
        if p.notice is not None:
            member.give_notice(*p.notice, TODAY)
        if p.date_of_death is not None:
            member.record_death(p.date_of_death, TODAY)
        if p.transfer_date is not None:
            member.transfer_all_shares(p.transfer_date, TODAY)
        members[p.number] = member

    assert members[7].status(date(2020, 6, 1)) == DECEASED
    assert members[7].status(TODAY) == EXITED
    assert members[8].status(TODAY) == MEMBER
    assert members[9].status(TODAY) == EXITED  # gekündigt zum 31.12.2023
    assert members[9].status(date(2022, 1, 1)) == NOTICE_GIVEN
    assert members[10].status(TODAY) == REJECTED
