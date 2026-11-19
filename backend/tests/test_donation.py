"""Ausscheiden mit Spende des Anteils (5j): Domäne, Buchung, Storno, Jahresende und Suche."""

from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import bookings, claims, exits
from coop_manager.accounts.domain import COOPERATIVE_ACCOUNT_NUMBER, REVERSAL, SHARE_DONATION
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.domain import EXIT_REASON_DONATION
from coop_manager.members.projections import search_members
from coop_manager.members.status import EXITED, MEMBER, NOTICE_GIVEN
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.system_settings.services import change_share_price

TODAY = date(2026, 11, 30)
PRICE = 5000
COOP = COOPERATIVE_ACCOUNT_NUMBER


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    change_share_price(db, PRICE, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")
    yield db
    db.close()


def member(db: Database, admit: bool = True, pay: bool = True) -> tuple[str, int]:
    """Erfundenes Mitglied seit dem 10.11.2026 mit 3 Anteilen (150,00 €): (Mitglieds-ID, Kontonummer)."""
    member_id = services.apply_for_membership(
        db,
        person_type=NATURAL_PERSON,
        name=PersonName(first_names="Erika", last_name="Muster", gender="w"),
        address=Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt"),
        application_date=date(2026, 11, 2),
        shares_subscribed=3,
        contact=None,
        actor="test",
    ).subject
    if admit:
        services.admit(db, member_id, date(2026, 11, 5), TODAY, actor="test")
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    if pay:
        bookings.subscribe(db, account.number, 3, date(2026, 11, 10), TODAY, actor="test")
    return member_id, account.number


def donate(db: Database, number: int, day: date = date(2026, 11, 20), today: date = TODAY):
    return bookings.donate(db, number, day, today, actor="test")


def test_donation_books_everything_to_the_cooperative(db):
    _, number = member(db)

    result = donate(db, number)

    booking = result.booking
    assert (booking.kind, booking.debit, booking.credit) == (SHARE_DONATION, number, COOP)
    assert (booking.amount, booking.shares, booking.text) == (15000, 3, "Spende Anteil")
    assert booking.value_date == date(2026, 11, 20)
    ledger = get_ledger(db)
    assert (ledger.balance(number), ledger.shares(number), ledger.claim(number, PRICE)) == (0, 0, 0)
    assert result.warning is None


def test_exited_from_the_day_after_the_donation(db):
    member_id, number = member(db)
    donate(db, number, date(2026, 11, 20))

    m = services.get_member(db, member_id)
    assert m.donation_date == date(2026, 11, 20)
    assert m.exit_date() == date(2026, 11, 20)
    assert m.status(date(2026, 11, 20)) == MEMBER
    assert m.status(date(2026, 11, 21)) == EXITED


def test_donation_makes_running_notices_moot(db):
    member_id, number = member(db)
    services.give_notice(db, member_id, date(2026, 11, 12), date(2028, 12, 31), TODAY, actor="test")

    donate(db, number, date(2026, 11, 20))

    m = services.get_member(db, member_id)
    assert m.status(date(2026, 11, 15)) == NOTICE_GIVEN
    assert m.exit_date() == date(2026, 11, 20)
    assert m.status(date(2026, 12, 1)) == EXITED
    assert m.full_notice() is not None  # bleibt stehen, ist aber gegenstandslos


def test_partial_notice_ends_with_the_donation(db):
    member_id, number = member(db)
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 12), date(2028, 12, 31), TODAY, actor="test")

    donate(db, number, date(2026, 11, 20))

    m = services.get_member(db, member_id)
    assert m.has_partial_notice(date(2026, 11, 20))
    assert not m.has_partial_notice(date(2026, 11, 21))
    [row] = search_members(db.projections.conn, "muster", date(2026, 11, 30))
    assert (row.status, row.partial_notice) == (EXITED, False)


def test_reversal_revokes_the_donation(db):
    member_id, number = member(db)
    donation = donate(db, number).booking

    result = bookings.reverse(db, donation.id, "falsches Mitglied", TODAY, actor="test")

    assert result.booking.kind == REVERSAL
    ledger = get_ledger(db)
    assert (ledger.balance(number), ledger.shares(number)) == (15000, 3)
    m = services.get_member(db, member_id)
    assert m.donation_date is None
    assert m.status(TODAY) == MEMBER


def test_donation_after_reversal_is_possible_again(db):
    member_id, number = member(db)
    donation = donate(db, number).booking
    bookings.reverse(db, donation.id, "falsches Datum", TODAY, actor="test")

    donate(db, number, date(2026, 11, 25))

    assert services.get_member(db, member_id).donation_date == date(2026, 11, 25)


def test_only_once(db):
    _, number = member(db)
    donate(db, number)

    with pytest.raises(DomainError):
        donate(db, number, date(2026, 11, 25))


def test_applicant_cannot_donate(db):
    member_id, number = member(db, admit=False)

    with pytest.raises(DomainError, match="Mitglied"):
        donate(db, number)
    assert services.get_member(db, member_id).donation_date is None
    assert get_ledger(db).shares(number) == 3  # nichts gebucht


def test_not_before_entry(db):
    _, number = member(db)

    with pytest.raises(DomainError, match="Mitglied"):
        donate(db, number, date(2026, 11, 9))


def test_not_in_the_future(db):
    _, number = member(db)

    with pytest.raises(DomainError):
        donate(db, number, date(2026, 12, 1))


def test_not_after_exit_by_notice(db):
    member_id, number = member(db)
    services.give_notice(db, member_id, date(2026, 11, 12), date(2026, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    with pytest.raises(DomainError):
        donate(db, number, date(2027, 1, 10), today=date(2027, 1, 10))


def test_no_notice_after_donation(db):
    member_id, number = member(db)
    donate(db, number, date(2026, 11, 20))

    with pytest.raises(DomainError, match="Spende"):
        services.give_notice(db, member_id, date(2026, 11, 20), date(2028, 12, 31), TODAY, actor="test")


def test_donation_on_31_12_is_not_a_year_end_exit(db):
    _, number = member(db)
    donate(db, number, date(2026, 12, 31), today=date(2027, 1, 5))

    m = services.get_member(db, get_ledger(db).accounts[number].member_id or "")
    due = m.exit_due(date(2026, 12, 31))
    assert due is not None and due.reasons == (EXIT_REASON_DONATION,)
    # Nichts mehr auf dem Konto: Die Seite Jahresende zeigt es nicht, gebucht wird nichts.
    assert exits.exits_due(db, 2026) == []


def test_not_in_open_claims(db):
    _, number = member(db)
    donate(db, number)

    assert claims.open_claims(db, TODAY) == []
