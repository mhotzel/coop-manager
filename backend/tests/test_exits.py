"""Ausscheiden zum Jahresende buchen (Schritt 5g): Liste, Buchung, Storno."""

from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import bookings, exits
from coop_manager.accounts.domain import COOPERATIVE_ACCOUNT_NUMBER, EXIT
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.domain import EXIT_REASON_DEATH, EXIT_REASON_EXPULSION, NOTICE, PARTIAL_NOTICE
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.system_settings.services import change_share_price

TODAY = date(2026, 11, 30)
NEXT_JANUARY = date(2027, 1, 5)  # erst dann ist 2026 abgeschlossen
END_2026 = date(2026, 12, 31)
COOP = COOPERATIVE_ACCOUNT_NUMBER


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    """Datenbank mit Anteilspreis 50,00 € und Genossenschaftskonto."""
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    change_share_price(db, 5000, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")
    yield db
    db.close()


def member(db: Database, last_name: str = "Muster") -> str:
    """Erfundenes Mitglied seit dem 10.11.2026 mit 3 eingezahlten Anteilen (150,00 €)."""
    member_id = services.apply_for_membership(
        db,
        person_type=NATURAL_PERSON,
        name=PersonName(first_names="Erika", last_name=last_name, gender="w"),
        address=Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt"),
        application_date=date(2026, 11, 2),
        shares_subscribed=3,
        contact=None,
        actor="test",
    ).subject
    services.admit(db, member_id, date(2026, 11, 5), TODAY, actor="test")
    bookings.subscribe(db, account(db, member_id), 3, date(2026, 11, 10), TODAY, actor="test")
    return member_id


def account(db: Database, member_id: str) -> int:
    found = get_ledger(db).account_of(member_id)
    assert found is not None
    return found.number


def shares(db: Database, member_id: str) -> int:
    return get_ledger(db).shares(account(db, member_id))


def test_full_notice_is_listed_and_posted(db):
    member_id = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), END_2026, TODAY, actor="test")

    [entry] = exits.exits_due(db, 2026)
    assert (entry.member_id, entry.name, entry.reasons) == (member_id, "Muster, Erika", (NOTICE,))
    assert (entry.full, entry.shares, entry.balance, entry.booked) == (True, 3, 15000, False)

    [entry] = exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")

    assert entry.booked is True
    ledger = get_ledger(db)
    number = account(db, member_id)
    assert (ledger.shares(number), ledger.balance(number)) == (0, 15000)  # der Saldo ist der Anspruch
    booking = ledger.exit_booking(number, END_2026)
    assert booking is not None
    assert (booking.kind, booking.debit, booking.credit, booking.amount, booking.shares) == (EXIT, number, COOP, 0, 3)
    assert (booking.value_date, booking.booking_date, booking.text) == (
        END_2026,
        NEXT_JANUARY,
        "Ausscheiden zum 31.12.2026",
    )


def test_partial_notice_books_only_its_shares(db):
    member_id = member(db)
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 20), END_2026, TODAY, actor="test")

    [entry] = exits.exits_due(db, 2026)
    assert (entry.reasons, entry.full, entry.shares) == ((PARTIAL_NOTICE,), False, 1)

    exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")

    assert shares(db, member_id) == 2


def test_after_booked_partial_exit_its_shares_are_not_subtracted_twice(db):
    """Korrektur aus 5f: Nach gebuchtem Ausscheiden sind die Anteile schon vom Konto weg."""
    member_id = member(db)
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 20), END_2026, TODAY, actor="test")
    exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")

    # 2 Anteile übrig, einer muss bleiben: einer lässt sich noch kündigen.
    services.give_partial_notice(db, member_id, 1, NEXT_JANUARY, date(2029, 12, 31), NEXT_JANUARY, actor="test")

    assert len(services.get_member(db, member_id).notices) == 2


def test_death_and_partial_notice_in_one_booking(db):
    member_id = member(db)
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 20), END_2026, TODAY, actor="test")
    services.record_death(db, member_id, date(2026, 11, 25), TODAY, actor="test")

    [entry] = exits.exits_due(db, 2026)
    assert (entry.reasons, entry.full, entry.shares) == ((EXIT_REASON_DEATH, PARTIAL_NOTICE), True, 3)

    exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")

    assert shares(db, member_id) == 0
    assert len([b for b in get_ledger(db).bookings if b.kind == EXIT]) == 1


def test_expulsion_is_listed(db):
    member_id = member(db)
    services.expel(db, member_id, date(2026, 11, 20), TODAY, actor="test")

    [entry] = exits.exits_due(db, 2026)

    assert (entry.reasons, entry.full) == ((EXIT_REASON_EXPULSION,), True)


def test_only_the_matching_year_is_listed(db):
    leaving_2026, leaving_2028 = member(db), member(db, "Beispiel")
    member(db, "Bleibt")  # ohne Kündigung
    services.give_notice(db, leaving_2026, date(2026, 11, 20), END_2026, TODAY, actor="test")
    services.give_notice(db, leaving_2028, date(2026, 11, 20), None, TODAY, actor="test")  # Frist: 2028

    assert [e.member_id for e in exits.exits_due(db, 2026)] == [leaving_2026]
    assert exits.exits_due(db, 2027) == []
    assert [e.member_id for e in exits.exits_due(db, 2028)] == [leaving_2028]


def test_posting_twice_books_nothing_new(db):
    member_id = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), END_2026, TODAY, actor="test")
    exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")

    [entry] = exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")

    assert entry.booked is True
    assert len([b for b in get_ledger(db).bookings if b.kind == EXIT]) == 1


@pytest.mark.parametrize("today", [date(2026, 12, 31), date(2026, 11, 30)])
def test_only_completed_years_can_be_posted(db, today):
    with pytest.raises(DomainError, match="erst nach dem Jahresende"):
        exits.post_exits(db, 2026, today, actor="test")


def test_reversal_reopens_the_exit(db):
    member_id = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), END_2026, TODAY, actor="test")
    exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")
    booking = get_ledger(db).exit_booking(account(db, member_id), END_2026)
    assert booking is not None

    result = bookings.reverse(db, booking.id, "zu früh gebucht", NEXT_JANUARY, actor="test")

    assert result.warning is None
    [entry] = exits.exits_due(db, 2026)
    assert (entry.booked, entry.shares) == (False, 3)


def test_reversing_a_full_exit_after_a_partial_exit_keeps_the_payment(db):
    """Korrektur: Nach einem Storno des Ausscheidens kein Abgleich mit den gezeichneten Anteilen.

    2 von 3 gezeichneten Anteilen sind nach dem Storno wieder da; ein Abgleich hielte das für eine
    Teilzahlung und nähme den Geldeingang zurück.
    """
    member_id = member(db)
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 20), END_2026, TODAY, actor="test")
    services.give_notice(db, member_id, date(2026, 11, 21), date(2027, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, NEXT_JANUARY, actor="test")
    exits.post_exits(db, 2027, date(2028, 1, 5), actor="test")
    booking = get_ledger(db).exit_booking(account(db, member_id), date(2027, 12, 31))
    assert booking is not None

    result = bookings.reverse(db, booking.id, "Fehler", date(2028, 1, 6), actor="test")

    assert result.warning is None
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 10)
    assert shares(db, member_id) == 2
