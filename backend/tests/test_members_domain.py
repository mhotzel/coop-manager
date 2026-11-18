from datetime import date, timedelta

import pytest

from coop_manager.core import DomainError
from coop_manager.members.domain import NOTICE, PARTIAL_NOTICE, Member
from coop_manager.members.status import (
    APPLICANT,
    DECEASED,
    EXITED,
    EXPELLED,
    MEMBER,
    NOTICE_GIVEN,
    REJECTED,
    default_exit_date,
)
from coop_manager.members.values import LEGAL_ENTITY, NATURAL_PERSON, Address, Contact, PersonName

TODAY = date(2026, 11, 30)  # „heute“ für Entscheidungen; die Tests hängen nicht vom echten Datum ab
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

    member.reject(date(2026, 11, 20), TODAY)

    assert reloaded(member).status(date(2026, 11, 19)) == APPLICANT
    assert reloaded(member).status(date(2026, 11, 20)) == REJECTED


def test_rejection_is_not_a_withdrawal():
    member = apply()
    member.reject(date(2026, 11, 10), TODAY)

    assert reloaded(member).rejection_date == date(2026, 11, 10)
    assert not reloaded(member).withdrawn


def test_admit():
    member = apply()

    member.admit(date(2026, 11, 10), TODAY)

    assert reloaded(member).admission_date == date(2026, 11, 10)
    assert reloaded(member).status(date(2026, 12, 1)) == APPLICANT  # Mitglied erst mit Geldeingang


def test_admit_twice_is_rejected():
    member = apply()
    member.admit(date(2026, 11, 10), TODAY)

    with pytest.raises(DomainError, match="bereits zugelassen"):
        member.admit(date(2026, 11, 11), TODAY)


def test_board_cannot_reject_after_admission():
    member = apply()
    member.admit(date(2026, 11, 10), TODAY)

    with pytest.raises(DomainError, match="nicht mehr abgelehnt"):
        member.reject(date(2026, 11, 20), TODAY)


def test_withdraw_after_admission_is_allowed():
    member = apply()
    member.admit(date(2026, 11, 10), TODAY)

    member.withdraw(date(2026, 11, 20), TODAY)

    assert reloaded(member).status(date(2026, 11, 20)) == REJECTED
    assert reloaded(member).withdrawn


@pytest.mark.parametrize(
    "decide", [lambda m, d: m.admit(d, TODAY), lambda m, d: m.reject(d, TODAY), lambda m, d: m.withdraw(d, TODAY)]
)
def test_nothing_after_rejection(decide):
    member = apply()
    member.withdraw(date(2026, 11, 5), TODAY)

    with pytest.raises(DomainError, match="bereits abgelehnt oder zurückgenommen"):
        decide(member, date(2026, 11, 6))


@pytest.mark.parametrize(
    "decide", [lambda m, d: m.admit(d, TODAY), lambda m, d: m.reject(d, TODAY), lambda m, d: m.withdraw(d, TODAY)]
)
def test_decision_not_in_the_future(decide):
    member = apply()

    with pytest.raises(DomainError, match="nicht in der Zukunft"):
        decide(member, TODAY + timedelta(days=1))


def test_decision_today_is_allowed():
    member = apply()
    member.admit(TODAY, TODAY)

    assert reloaded(member).admission_date == TODAY


def test_decision_not_before_application():
    with pytest.raises(DomainError, match="nicht vor dem Antrag"):
        apply().admit(date(2026, 11, 1), TODAY)


# --- Geldeingang und Status „Mitglied“ ---


def test_admission_then_payment():
    member = apply()
    member.admit(date(2026, 11, 10), TODAY)
    member.record_payment(date(2026, 11, 20), TODAY)

    member = reloaded(member)
    assert member.payment_date == date(2026, 11, 20)
    assert member.entry_date() == date(2026, 11, 20)  # das spätere der beiden Daten
    assert member.status(date(2026, 11, 19)) == APPLICANT
    assert member.status(date(2026, 11, 20)) == MEMBER


def test_payment_then_admission():
    member = apply()
    member.record_payment(date(2026, 11, 5), TODAY)

    assert member.entry_date() is None  # ohne Zulassung noch kein Mitglied
    assert member.status(TODAY) == APPLICANT

    member.admit(date(2026, 11, 10), TODAY)

    assert reloaded(member).entry_date() == date(2026, 11, 10)
    assert reloaded(member).status(date(2026, 11, 10)) == MEMBER


def test_payment_only_once():
    member = apply()
    member.record_payment(date(2026, 11, 5), TODAY)

    with pytest.raises(DomainError, match="Zahlung ist bereits erfasst"):
        member.record_payment(date(2026, 11, 6), TODAY)


def test_revoke_payment():
    """Nach dem Storno des Eintritts: kein Geldeingang mehr, also auch kein Mitglied mehr."""
    member = apply()
    member.admit(date(2026, 11, 10), TODAY)
    member.record_payment(date(2026, 11, 20), TODAY)

    member.revoke_payment()

    member = reloaded(member)
    assert member.payment_date is None
    assert member.entry_date() is None
    assert member.admission_date == date(2026, 11, 10)  # die Zulassung bleibt
    assert member.status(TODAY) == APPLICANT


def test_revoke_payment_needs_payment():
    with pytest.raises(DomainError, match="kein Geldeingang erfasst"):
        apply().revoke_payment()


@pytest.mark.parametrize("decide", [lambda m, d: m.reject(d, TODAY), lambda m, d: m.withdraw(d, TODAY)])
def test_no_payment_after_rejection(decide):
    member = apply()
    decide(member, date(2026, 11, 5))

    with pytest.raises(DomainError, match="bereits abgelehnt oder zurückgenommen"):
        member.record_payment(date(2026, 11, 6), TODAY)


@pytest.mark.parametrize(
    "payment_date, message",
    [(date(2026, 11, 1), "nicht vor dem Antrag"), (TODAY + timedelta(days=1), "nicht in der Zukunft")],
)
def test_payment_date_checks(payment_date, message):
    with pytest.raises(DomainError, match=message):
        apply().record_payment(payment_date, TODAY)


def test_rejection_after_payment_before_admission():
    """Gezahlt, aber der Vorstand lehnt ab: Die Person wird nicht Mitglied, das Geld geht zurück."""
    member = apply()
    member.record_payment(date(2026, 11, 5), TODAY)
    member.reject(date(2026, 11, 10), TODAY)

    assert reloaded(member).status(TODAY) == REJECTED
    assert reloaded(member).entry_date() is None


def test_member_cannot_withdraw():
    member = apply()
    member.admit(date(2026, 11, 10), TODAY)
    member.record_payment(date(2026, 11, 20), TODAY)

    with pytest.raises(DomainError, match="bereits Mitglied"):
        member.withdraw(date(2026, 11, 25), TODAY)


# --- Kündigung und Teilkündigung ---

EXIT = date(2028, 12, 31)  # Ausscheiden nach der Frist bei Eingang im November 2026


def member_since_nov_10() -> Member:
    """Antrag 02.11., Zulassung 05.11., Geldeingang 10.11.2026: Mitglied ab dem 10.11. mit 2 Anteilen."""
    member = apply()
    member.admit(date(2026, 11, 5), TODAY)
    member.record_payment(date(2026, 11, 10), TODAY)
    return member


@pytest.mark.parametrize(
    "notice_date, exit_date",
    [
        (date(2026, 3, 15), date(2028, 12, 31)),  # Beispiel aus dem Plan
        (date(2026, 1, 1), date(2028, 12, 31)),
        (date(2026, 12, 31), date(2028, 12, 31)),  # genau zwei Jahre reichen
        (date(2027, 1, 1), date(2029, 12, 31)),
    ],
)
def test_default_exit_date(notice_date, exit_date):
    assert default_exit_date(notice_date) == exit_date


def test_give_notice_and_status():
    member = member_since_nov_10()

    member.give_notice(date(2026, 11, 20), EXIT, TODAY)

    member = reloaded(member)
    [notice] = member.notices
    assert (notice.kind, notice.notice_date, notice.exit_date, notice.shares) == (
        NOTICE,
        date(2026, 11, 20),
        EXIT,
        None,
    )
    assert member.status(date(2026, 11, 19)) == MEMBER
    assert member.status(date(2026, 11, 20)) == NOTICE_GIVEN
    assert member.status(date(2028, 12, 31)) == NOTICE_GIVEN  # am 31.12. noch dabei
    assert member.status(date(2029, 1, 1)) == EXITED


def test_exit_date_may_be_earlier_than_the_notice_period():
    member = member_since_nov_10()

    member.give_notice(date(2026, 11, 20), date(2026, 12, 31), TODAY)

    assert reloaded(member).status(date(2027, 1, 1)) == EXITED


@pytest.mark.parametrize(
    "notice_date, exit_date, message",
    [
        (date(2026, 12, 1), EXIT, "nicht in der Zukunft"),
        (date(2026, 11, 9), EXIT, "nur, wer am Tag des Eingangs Mitglied ist"),
        (date(2026, 11, 20), date(2028, 12, 30), "immer zum 31.12."),
        (date(2026, 11, 20), date(2025, 12, 31), "nach dem Eingang"),
    ],
)
def test_give_notice_checks(notice_date, exit_date, message):
    with pytest.raises(DomainError, match=message):
        member_since_nov_10().give_notice(notice_date, exit_date, TODAY)


def test_applicant_cannot_give_notice():
    with pytest.raises(DomainError, match="Mitglied"):
        apply().give_notice(date(2026, 11, 20), EXIT, TODAY)


def test_notice_only_once():
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 20), EXIT, TODAY)

    with pytest.raises(DomainError, match="bereits gekündigt"):
        member.give_notice(date(2026, 11, 21), EXIT, TODAY)
    with pytest.raises(DomainError, match="bereits gekündigt"):
        member.give_partial_notice(1, date(2026, 11, 21), EXIT, TODAY, held=2)


def test_partial_notice_keeps_membership():
    member = member_since_nov_10()

    member.give_partial_notice(1, date(2026, 11, 20), EXIT, TODAY, held=2)

    member = reloaded(member)
    [notice] = member.notices
    assert (notice.kind, notice.shares) == (PARTIAL_NOTICE, 1)
    assert member.partially_noticed_shares() == 1
    assert member.status(date(2029, 1, 1)) == MEMBER
    assert member.has_partial_notice(EXIT) is True
    assert member.has_partial_notice(date(2029, 1, 1)) is False


def test_partial_notices_leave_at_least_one_share():
    member = member_since_nov_10()
    member.give_partial_notice(2, date(2026, 11, 20), EXIT, TODAY, held=4)

    with pytest.raises(DomainError, match="höchstens 1 von 2"):
        member.give_partial_notice(2, date(2026, 11, 21), EXIT, TODAY, held=4)

    member.give_partial_notice(1, date(2026, 11, 21), EXIT, TODAY, held=4)
    assert member.partially_noticed_shares() == 3


@pytest.mark.parametrize("shares", [0, 2])
def test_partial_notice_shares_checks(shares):
    with pytest.raises(DomainError):
        member_since_nov_10().give_partial_notice(shares, date(2026, 11, 20), EXIT, TODAY, held=2)


def test_full_notice_after_partial_notice():
    member = member_since_nov_10()
    member.give_partial_notice(1, date(2026, 11, 20), EXIT, TODAY, held=2)

    member.give_notice(date(2026, 11, 25), EXIT, TODAY)

    assert len(reloaded(member).notices) == 2
    assert reloaded(member).status(TODAY) == NOTICE_GIVEN


def test_withdraw_notice():
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 20), EXIT, TODAY)
    notice_id = member.notices[0].id

    member.withdraw_notice(notice_id, TODAY)

    member = reloaded(member)
    assert member.notices == []
    assert member.status(date(2029, 1, 1)) == MEMBER
    member.give_notice(date(2026, 11, 25), EXIT, TODAY)  # danach geht es wieder


def test_withdraw_notice_checks():
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 20), date(2026, 12, 31), TODAY)
    notice_id = member.notices[0].id

    with pytest.raises(DomainError, match="gibt es nicht"):
        member.withdraw_notice("unbekannt", TODAY)
    with pytest.raises(DomainError, match="bereits vorbei"):
        member.withdraw_notice(notice_id, date(2027, 1, 1))
    member.withdraw_notice(notice_id, date(2026, 12, 31))  # am 31.12. geht es noch


# --- Tod ---


def test_record_death_and_status():
    member = member_since_nov_10()

    member.record_death(date(2026, 11, 20), TODAY)

    member = reloaded(member)
    assert member.date_of_death == date(2026, 11, 20)
    assert member.exit_date() == date(2026, 12, 31)
    assert member.status(date(2026, 11, 19)) == MEMBER
    assert member.status(date(2026, 11, 20)) == DECEASED
    assert member.status(date(2026, 12, 31)) == DECEASED
    assert member.status(date(2027, 1, 1)) == EXITED


def test_death_brings_exit_of_a_notice_forward():
    """Kündigung zum 31.12.2028, Tod im März 2027: ausgeschieden ab 2028, die Kündigung ist gegenstandslos."""
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 20), EXIT, TODAY)

    member.record_death(date(2027, 3, 10), date(2027, 3, 15))

    member = reloaded(member)
    assert member.status(date(2027, 3, 9)) == NOTICE_GIVEN
    assert member.status(date(2027, 3, 10)) == DECEASED
    assert member.status(date(2028, 1, 1)) == EXITED
    assert member.exit_date() == date(2027, 12, 31)


def test_death_can_be_recorded_retroactively():
    """Erst im Februar 2027 erfährt man vom Tod am 20.11.2026: ausgeschieden rückwirkend zum 31.12.2026."""
    member = member_since_nov_10()

    member.record_death(date(2026, 11, 20), today=date(2027, 2, 5))

    member = reloaded(member)
    assert member.status(date(2026, 11, 20)) == DECEASED
    assert member.status(date(2027, 2, 5)) == EXITED
    assert member.exit_date() == date(2026, 12, 31)


def test_death_on_the_day_of_entry_and_today():
    member = member_since_nov_10()
    member.record_death(date(2026, 11, 10), TODAY)  # am Tag des Eintritts

    other = member_since_nov_10()
    other.record_death(TODAY, TODAY)  # heute

    assert (member.status(TODAY), other.status(TODAY)) == (DECEASED, DECEASED)


def test_death_after_exit_is_rejected():
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 20), date(2026, 12, 31), TODAY)

    with pytest.raises(DomainError, match="nur bei Mitgliedern"):
        member.record_death(date(2027, 2, 1), date(2027, 2, 5))


@pytest.mark.parametrize(
    "date_of_death, message",
    [
        (date(2026, 12, 1), "nicht in der Zukunft"),
        (date(2026, 11, 9), "nur bei Mitgliedern"),  # vor dem Eintritt
    ],
)
def test_record_death_checks(date_of_death, message):
    with pytest.raises(DomainError, match=message):
        member_since_nov_10().record_death(date_of_death, TODAY)


def test_applicant_death_is_not_recorded():
    with pytest.raises(DomainError, match="Antrag zurücknehmen"):
        apply().record_death(date(2026, 11, 20), TODAY)


def test_death_only_once():
    member = member_since_nov_10()
    member.record_death(date(2026, 11, 20), TODAY)

    with pytest.raises(DomainError, match="bereits erfasst"):
        member.record_death(date(2026, 11, 21), TODAY)


def test_no_notice_after_death():
    member = member_since_nov_10()
    member.record_death(date(2026, 11, 20), TODAY)

    with pytest.raises(DomainError, match="Mitglied"):
        member.give_notice(date(2026, 11, 25), EXIT, TODAY)


def test_revoke_death():
    member = member_since_nov_10()
    member.record_death(date(2026, 11, 20), TODAY)

    member.revoke_death()

    member = reloaded(member)
    assert member.date_of_death is None
    assert member.status(date(2027, 1, 1)) == MEMBER
    member.record_death(date(2026, 11, 21), TODAY)  # mit richtigem Datum neu erfassen


def test_revoke_death_needs_death():
    with pytest.raises(DomainError, match="kein Tod erfasst"):
        member_since_nov_10().revoke_death()


# --- Ausschluss ---


def test_expel_and_status():
    member = member_since_nov_10()

    member.expel(date(2026, 11, 20), TODAY)

    member = reloaded(member)
    assert member.expulsion_date == date(2026, 11, 20)
    assert member.exit_date() == date(2026, 12, 31)
    assert member.status(date(2026, 11, 19)) == MEMBER
    assert member.status(date(2026, 11, 20)) == EXPELLED
    assert member.status(date(2026, 12, 31)) == EXPELLED
    assert member.status(date(2027, 1, 1)) == EXITED


def test_expulsion_brings_exit_of_a_notice_forward():
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 15), EXIT, TODAY)

    member.expel(date(2026, 11, 20), TODAY)

    assert reloaded(member).exit_date() == date(2026, 12, 31)
    assert reloaded(member).status(TODAY) == EXPELLED


@pytest.mark.parametrize(
    "decision_date, message",
    [
        (date(2026, 12, 1), "nicht in der Zukunft"),
        (date(2026, 11, 9), "am Tag des Beschlusses Mitglied"),  # vor dem Eintritt
    ],
)
def test_expel_checks(decision_date, message):
    with pytest.raises(DomainError, match=message):
        member_since_nov_10().expel(decision_date, TODAY)


def test_expel_only_once_and_not_after_death():
    member = member_since_nov_10()
    member.expel(date(2026, 11, 20), TODAY)
    with pytest.raises(DomainError, match="bereits erfasst"):
        member.expel(date(2026, 11, 21), TODAY)

    dead = member_since_nov_10()
    dead.record_death(date(2026, 11, 20), TODAY)
    with pytest.raises(DomainError, match="Mitglied"):
        dead.expel(date(2026, 11, 21), TODAY)


def test_death_after_expulsion_in_the_same_year():
    """Bis zum 31.12. ist der Ausgeschlossene noch Mitglied; stirbt er vorher, wird das erfasst."""
    member = member_since_nov_10()
    member.expel(date(2026, 11, 20), TODAY)

    member.record_death(date(2026, 11, 25), TODAY)

    assert reloaded(member).status(TODAY) == DECEASED
    assert reloaded(member).exit_date() == date(2026, 12, 31)


def test_no_notice_after_expulsion():
    member = member_since_nov_10()
    member.expel(date(2026, 11, 20), TODAY)

    with pytest.raises(DomainError, match="Mitglied"):
        member.give_notice(date(2026, 11, 25), EXIT, TODAY)


def test_lift_expulsion_even_after_year_end():
    """Der Aufsichtsrat gibt dem Widerspruch im Januar statt: Die Person war nie ausgeschieden."""
    member = member_since_nov_10()
    member.give_notice(date(2026, 11, 15), EXIT, TODAY)
    member.expel(date(2026, 11, 20), TODAY)

    member.lift_expulsion(date(2027, 1, 10), date(2027, 1, 12))

    member = reloaded(member)
    assert member.expulsion_date is None
    assert member.status(date(2027, 1, 12)) == NOTICE_GIVEN  # die Kündigung gilt wieder
    assert member.exit_date() == EXIT


@pytest.mark.parametrize(
    "decision_date, message",
    [
        (date(2026, 12, 1), "nicht in der Zukunft"),
        (date(2026, 11, 19), "nicht vor dem Ausschluss"),
    ],
)
def test_lift_expulsion_checks(decision_date, message):
    member = member_since_nov_10()
    member.expel(date(2026, 11, 20), TODAY)

    with pytest.raises(DomainError, match=message):
        member.lift_expulsion(decision_date, TODAY)


def test_lift_expulsion_needs_expulsion():
    with pytest.raises(DomainError, match="kein Ausschluss erfasst"):
        member_since_nov_10().lift_expulsion(TODAY, TODAY)
