"""Saldenliste: Guthaben jedes Mitgliedskontos zum Stichtag und Abstimmung mit dem Genossenschaftskonto.

Alle Daten sind erfunden.
"""

from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import balances, bookings, exits
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.status import APPLICANT, EXITED, MEMBER
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.system_settings.services import change_share_price
from coop_manager.users.domain import ACCOUNTING_READONLY, ADMIN

TODAY = date(2026, 11, 30)
NEW_YEAR = date(2027, 1, 1)
JANUARY = date(2027, 1, 15)
PRICE = 5000


@pytest.fixture
def db(tmp_path) -> Iterator[Database]:
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    change_share_price(db, PRICE, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")
    yield db
    db.close()


def apply(db: Database, last_name: str = "Muster") -> tuple[str, int]:
    """Erfundener Antrag über 3 Anteile; liefert Mitglieds-ID und Kontonummer."""
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
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    return member_id, account.number


def member(db: Database, last_name: str = "Muster") -> tuple[str, int]:
    """Mitglied seit dem 10.11.2026 mit 3 Anteilen (150,00 €)."""
    member_id, number = apply(db, last_name)
    services.admit(db, member_id, date(2026, 11, 5), TODAY, actor="test")
    bookings.subscribe(db, number, 3, date(2026, 11, 10), TODAY, actor="test")
    return member_id, number


def entries(result: balances.BalanceList) -> dict[int, balances.BalanceEntry]:
    return {e.account_number: e for e in result.entries}


def test_member_has_share_capital_and_no_claim(db):
    _, number = member(db)

    result = balances.account_balances(db, TODAY)

    entry = entries(result)[number]
    assert (entry.name, entry.status) == ("Muster, Erika", MEMBER)
    assert (entry.shares, entry.balance, entry.share_capital, entry.claim) == (3, 15000, 15000, 0)
    assert entry.exit_not_booked is False


def test_totals_balance_against_cooperative_account(db):
    member(db, "Muster")
    member(db, "Beispiel")

    result = balances.account_balances(db, TODAY)

    assert (result.total_shares, result.total_balance, result.total_share_capital, result.total_claim) == (
        6,
        30000,
        30000,
        0,
    )
    assert result.cooperative_balance == -30000
    assert result.balanced is True


def test_stichtag_counts_only_bookings_up_to_that_day(db):
    _, number = member(db)

    before = balances.account_balances(db, date(2026, 11, 9))
    with_zero = balances.account_balances(db, date(2026, 11, 9), include_zero=True)

    assert before.entries == []  # vor der Einzahlung Saldo 0
    assert entries(with_zero)[number].balance == 0
    assert entries(with_zero)[number].status == APPLICANT  # zugelassen, aber noch nicht eingezahlt


def test_exit_not_booked_is_flagged(db):
    member_id, number = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test")

    entry = entries(balances.account_balances(db, NEW_YEAR))[number]

    assert (entry.status, entry.shares, entry.claim) == (EXITED, 3, 0)
    assert entry.exit_not_booked is True


def test_booked_exit_turns_share_capital_into_claim(db):
    member_id, number = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    on_31_12 = entries(balances.account_balances(db, date(2026, 12, 31)))[number]
    after = entries(balances.account_balances(db, NEW_YEAR))[number]

    assert (on_31_12.shares, on_31_12.claim) == (3, 0)  # bis einschließlich 31.12. noch mit Anteilen
    assert (after.shares, after.balance, after.share_capital, after.claim) == (0, 15000, 0, 15000)
    assert after.exit_not_booked is False


def test_payout_reduces_balance(db):
    member_id, number = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), date(2026, 12, 31), TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")
    bookings.payout(db, number, 10000, JANUARY, JANUARY, actor="test")

    result = balances.account_balances(db, JANUARY)

    assert entries(result)[number].claim == 5000
    assert (result.total_balance, result.cooperative_balance, result.balanced) == (5000, -5000, True)


def test_reversed_booking_does_not_count(db):
    _, number = member(db)
    booking_id = get_ledger(db).bookings_of(number)[0].id
    bookings.reverse(db, booking_id, "Zahlung falsch zugeordnet", TODAY, actor="test")

    result = balances.account_balances(db, TODAY)

    assert result.entries == []
    assert (result.total_balance, result.balanced) == (0, True)


def test_api_balances(client, db, register, login):
    member(db)
    register("rita", ACCOUNTING_READONLY, full_name="Rita Lesend")
    login("rita")

    response = client.get("/api/accounts/balances", params={"day": "2026-11-30"})

    assert response.status_code == 200
    body = response.json()
    assert body["day"] == "2026-11-30"
    assert [(e["account_number"], e["balance"]) for e in body["entries"]] == [(1, 15000)]
    assert body["balanced"] is True


def test_api_balances_needs_accounting_role(client, db, register, login):
    register("ada", ADMIN, full_name="Ada Admin")
    login("ada")

    assert client.get("/api/accounts/balances").status_code == 403
