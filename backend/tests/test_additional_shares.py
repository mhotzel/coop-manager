"""Weitere Anteile zeichnen und einzahlen (5i): Zeichnung am Mitglied, Buchung, Storno, Abgleich."""

from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import bookings
from coop_manager.accounts.domain import ADDITIONAL_SHARES, COOPERATIVE_ACCOUNT_NUMBER, SUBSCRIPTION
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.status import MEMBER
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.system_settings.services import change_share_price

TODAY = date(2026, 11, 30)
PRICE = 5000


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    change_share_price(db, PRICE, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")
    yield db
    db.close()


@pytest.fixture
def member(db) -> tuple[str, int]:
    """Erfundenes Mitglied seit dem 10.11.2026 mit 3 Anteilen: (Mitglieds-ID, Kontonummer)."""
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
    services.admit(db, member_id, date(2026, 11, 5), TODAY, actor="test")
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    bookings.subscribe(db, account.number, 3, date(2026, 11, 10), TODAY, actor="test")
    return member_id, account.number


def subscribe_more(db: Database, member_id: str, shares: int = 2, day: date = date(2026, 11, 15)):
    return services.subscribe_additional_shares(db, member_id, shares, day, TODAY, actor="test")


def pay(db: Database, number: int, shares: int = 2, day: date = date(2026, 11, 20)):
    return bookings.pay_additional_shares(db, number, shares, day, TODAY, actor="test")


def test_subscribe_and_pay(db, member):
    member_id, number = member
    m = subscribe_more(db, member_id)
    assert (m.additional_shares_subscribed(), m.total_shares_subscribed()) == (2, 5)

    result = pay(db, number)

    booking = result.booking
    assert (booking.kind, booking.debit, booking.credit) == (ADDITIONAL_SHARES, COOPERATIVE_ACCOUNT_NUMBER, number)
    assert (booking.amount, booking.shares, booking.text) == (10000, 2, "Weitere Anteile")
    assert result.warning is None
    ledger = get_ledger(db)
    assert (ledger.balance(number), ledger.shares(number), ledger.paid_additional_shares(number)) == (25000, 5, 2)


def test_partial_payment_warns(db, member):
    member_id, number = member
    subscribe_more(db, member_id, 3)

    first = pay(db, number, 1)
    second = pay(db, number, 2)

    assert first.warning == "1 von 3 weiteren Anteilen eingezahlt."
    assert second.warning is None


def test_not_more_than_open(db, member):
    member_id, number = member
    subscribe_more(db, member_id, 2)

    with pytest.raises(DomainError, match="nur 2"):
        pay(db, number, 3)


def test_nothing_open(db, member):
    _, number = member

    with pytest.raises(DomainError, match="keine weiteren Anteile"):
        pay(db, number, 1)


def test_not_before_decision(db, member):
    member_id, number = member
    subscribe_more(db, member_id, day=date(2026, 11, 15))

    with pytest.raises(DomainError, match="Zulassung"):
        pay(db, number, day=date(2026, 11, 14))


def test_only_members_subscribe(db, member):
    member_id, _ = member

    with pytest.raises(DomainError, match="Mitglied"):
        subscribe_more(db, member_id, day=date(2026, 11, 9))  # vor dem Eintritt
    services.give_notice(db, member_id, date(2026, 11, 12), date(2028, 12, 31), TODAY, actor="test")
    with pytest.raises(DomainError, match="Mitglied"):
        subscribe_more(db, member_id, day=date(2026, 11, 15))


def test_revoke_open_subscription(db, member):
    member_id, _ = member
    subscription = subscribe_more(db, member_id).additional_subscriptions[0]

    m = services.revoke_additional_shares(db, member_id, subscription.id, actor="test")

    assert m.additional_subscriptions == []


def test_revoke_paid_subscription_needs_reversal_first(db, member):
    member_id, number = member
    subscription = subscribe_more(db, member_id).additional_subscriptions[0]
    booking = pay(db, number).booking

    with pytest.raises(DomainError, match="stornieren"):
        services.revoke_additional_shares(db, member_id, subscription.id, actor="test")
    bookings.reverse(db, booking.id, "Irrtum", TODAY, actor="test")
    services.revoke_additional_shares(db, member_id, subscription.id, actor="test")


def test_reversal_reopens_the_shares(db, member):
    member_id, number = member
    subscribe_more(db, member_id)
    booking = pay(db, number).booking

    result = bookings.reverse(db, booking.id, "falsches Konto", TODAY, actor="test")

    assert result.warning is None
    assert get_ledger(db).paid_additional_shares(number) == 0
    assert services.get_member(db, member_id).status(TODAY) == MEMBER  # Mitgliedschaft unberührt
    pay(db, number)  # wieder offen


def test_entry_reconcile_ignores_additional_shares(db, member):
    """Storno und Neubuchung des Eintritts: Die weiteren Anteile stören den Abgleich nicht."""
    member_id, number = member
    subscribe_more(db, member_id, 3)  # so viele wie im Antrag
    pay(db, number, 3)
    entry = next(b for b in get_ledger(db).bookings if b.kind == SUBSCRIPTION)

    bookings.reverse(db, entry.id, "falsches Datum", TODAY, actor="test")
    assert services.get_member(db, member_id).payment_date is None
    result = bookings.subscribe(db, number, 3, date(2026, 11, 11), TODAY, actor="test")

    assert result.warning is None
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 11)
