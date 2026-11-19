"""Auszahlung, Kürzung Verlustvortrag, Ausbuchung Verjährung (5h-1) und Liste offener Ansprüche (5h-2)."""

from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import bookings, claims, exits
from coop_manager.accounts.domain import COOPERATIVE_ACCOUNT_NUMBER, LIMITATION_WRITEOFF, LOSS_DEDUCTION, PAYOUT
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.status import EXITED, MEMBER
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.system_settings.services import change_share_price

TODAY = date(2026, 11, 30)
JANUARY = date(2027, 1, 15)
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


def member(db: Database, last_name: str = "Muster") -> int:
    """Erfundenes Mitglied seit dem 10.11.2026 mit 3 Anteilen (150,00 €); liefert die Kontonummer."""
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
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    bookings.subscribe(db, account.number, 3, date(2026, 11, 10), TODAY, actor="test")
    return account.number


@pytest.fixture
def exited(db) -> int:
    """Ausgeschieden zum 31.12.2026, Ausscheiden gebucht: Anspruch 150,00 €."""
    number = member(db)
    member_id = get_ledger(db).accounts[number].member_id
    assert member_id is not None
    services.give_notice(db, member_id, date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")
    return number


def claim(db: Database, number: int) -> int:
    return get_ledger(db).claim(number, PRICE)


def test_claim_after_exit(db, exited):
    assert claim(db, exited) == 15000


def test_no_claim_while_shares_are_held(db):
    assert claim(db, member(db)) == 0


def test_partial_payout_and_rest(db, exited):
    result = bookings.payout(db, exited, 10000, JANUARY, JANUARY, actor="test")

    booking = result.booking
    assert (booking.kind, booking.debit, booking.credit, booking.amount, booking.shares) == (
        PAYOUT,
        exited,
        COOP,
        10000,
        0,
    )
    assert (booking.text, result.warning) == ("Auszahlung", None)
    assert claim(db, exited) == 5000

    bookings.payout(db, exited, 5000, JANUARY, JANUARY, actor="test", text="Rest überwiesen")

    assert claim(db, exited) == 0
    assert get_ledger(db).balance(exited) == 0  # Austritt abgeschlossen: Saldo und Anteile 0


def test_payout_not_above_claim(db, exited):
    with pytest.raises(DomainError, match="höher als der offene Anspruch von 150,00"):
        bookings.payout(db, exited, 15001, JANUARY, JANUARY, actor="test")


@pytest.mark.parametrize("amount", [0, -100])
def test_payout_needs_positive_amount(db, exited, amount):
    with pytest.raises(DomainError, match="größer als 0"):
        bookings.payout(db, exited, amount, JANUARY, JANUARY, actor="test")


def test_payout_needs_claim(db):
    number = member(db)

    with pytest.raises(DomainError, match="keinen offenen Auseinandersetzungsanspruch"):
        bookings.payout(db, number, 100, JANUARY, JANUARY, actor="test")


@pytest.mark.parametrize("value_date", [date(2026, 12, 31), date(2026, 12, 1)])
def test_value_date_after_exit(db, exited, value_date):
    with pytest.raises(DomainError, match="nach dem Ausscheiden zum 31.12.2026"):
        bookings.payout(db, exited, 100, value_date, JANUARY, actor="test")


def test_claim_after_partial_exit(db):
    """Teilkündigung über 1 Anteil: 2 Anteile bleiben, der Anspruch ist der Wert des einen."""
    number = member(db)
    member_id = get_ledger(db).accounts[number].member_id
    assert member_id is not None
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    assert claim(db, number) == 5000

    bookings.payout(db, number, 5000, JANUARY, JANUARY, actor="test")

    ledger = get_ledger(db)
    assert (ledger.balance(number), ledger.shares(number), claim(db, number)) == (10000, 2, 0)


def test_deduct_loss(db, exited):
    result = bookings.deduct_loss(db, exited, 2000, JANUARY, JANUARY, actor="test")

    assert (result.booking.kind, result.booking.text) == (LOSS_DEDUCTION, "Kürzung Verlustvortrag")
    assert claim(db, exited) == 13000


def test_write_off_takes_the_whole_rest(db, exited):
    bookings.payout(db, exited, 10000, JANUARY, JANUARY, actor="test")

    result = bookings.write_off(db, exited, date(2030, 1, 2), date(2030, 1, 2), actor="test")

    assert (result.booking.kind, result.booking.amount, result.booking.text) == (
        LIMITATION_WRITEOFF,
        5000,
        "Ausbuchung Verjährung",
    )
    assert claim(db, exited) == 0

    with pytest.raises(DomainError, match="keinen offenen"):
        bookings.write_off(db, exited, date(2030, 1, 2), date(2030, 1, 2), actor="test")


def test_reverse_payout_restores_claim(db, exited):
    booking = bookings.payout(db, exited, 10000, JANUARY, JANUARY, actor="test").booking

    result = bookings.reverse(db, booking.id, "falsches Konto", JANUARY, actor="test")

    assert result.warning is None
    assert claim(db, exited) == 15000


# --- Liste offener Ansprüche (5h-2) ---


def member_id_of(db: Database, number: int) -> str:
    member_id = get_ledger(db).accounts[number].member_id
    assert member_id is not None
    return member_id


def test_open_claims_lists_exited_member(db, exited):
    [entry] = claims.open_claims(db, JANUARY)

    assert (entry.account_number, entry.name, entry.status) == (exited, "Muster, Erika", EXITED)
    assert (entry.exit_date, entry.claim) == (date(2026, 12, 31), 15000)


def test_open_claims_shows_rest_and_drops_paid(db, exited):
    bookings.payout(db, exited, 10000, JANUARY, JANUARY, actor="test")
    assert [e.claim for e in claims.open_claims(db, JANUARY)] == [5000]

    bookings.payout(db, exited, 5000, JANUARY, JANUARY, actor="test")

    assert claims.open_claims(db, JANUARY) == []


def test_open_claims_after_partial_exit(db):
    number = member(db)
    services.give_partial_notice(
        db, member_id_of(db, number), 1, date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test"
    )
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    [entry] = claims.open_claims(db, JANUARY)

    assert (entry.status, entry.claim) == (MEMBER, 5000)


def test_open_claims_needs_booked_exit(db):
    member(db)  # Mitglied ohne Ausscheiden
    change_share_price(db, 4000, actor="test")  # rechnerisch läge der Saldo nun über dem Wert

    assert claims.open_claims(db, JANUARY) == []


def test_open_claims_oldest_exit_first(db):
    later = member(db, "Später")
    earlier = member(db, "Früher")
    services.give_notice(db, member_id_of(db, later), date(2026, 11, 20), date(2027, 12, 31), TODAY, actor="test")
    services.give_notice(db, member_id_of(db, earlier), date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")
    exits.post_exits(db, 2027, date(2028, 1, 5), actor="test")

    entries = claims.open_claims(db, date(2028, 1, 5))

    assert [e.account_number for e in entries] == [earlier, later]
