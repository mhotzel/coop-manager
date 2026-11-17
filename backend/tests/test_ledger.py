import pytest

from coop_manager.accounts import services
from coop_manager.accounts.domain import (
    COOPERATIVE_ACCOUNT,
    COOPERATIVE_ACCOUNT_NUMBER,
    MEMBER_ACCOUNT,
    SUBJECT,
    Account,
    Ledger,
)
from coop_manager.core import DomainError

COOP_NAME = "Musterladen eG"  # erfunden


def ledger_with(*numbers: int) -> Ledger:
    """Hauptbuch mit Mitgliedskonten zu den Nummern; das Mitglied heißt „member-<Nummer>“."""
    ledger = Ledger()
    for number in numbers:
        ledger.open_member_account(number, f"member-{number}")
    return ledger


def test_new_ledger_has_no_accounts():
    ledger = Ledger()

    assert ledger.accounts == {}
    assert ledger.cooperative_account() is None


def test_open_member_account():
    ledger = ledger_with(1, 2)

    reloaded = Ledger.from_events(SUBJECT, ledger.uncommitted_events)
    assert reloaded.account_of("member-2") == Account(number=2, kind=MEMBER_ACCOUNT, member_id="member-2")
    assert reloaded.account_of("member-3") is None
    assert reloaded.member_account_numbers() == {1, 2}


@pytest.mark.parametrize(
    "number, message",
    [(0, "positiv"), (7, "bereits vergeben"), (COOPERATIVE_ACCOUNT_NUMBER, "gehört der Genossenschaft")],
)
def test_open_member_account_checks_number(number, message):
    with pytest.raises(DomainError, match=message):
        ledger_with(7).open_member_account(number, "member-x")


def test_member_has_only_one_account():
    with pytest.raises(DomainError, match="bereits ein Konto"):
        ledger_with(7).open_member_account(8, "member-7")


def test_open_cooperative_account():
    ledger = ledger_with(1)
    ledger.open_cooperative_account("  " + COOP_NAME + " ")

    reloaded = Ledger.from_events(SUBJECT, ledger.uncommitted_events)
    expected = Account(number=COOPERATIVE_ACCOUNT_NUMBER, kind=COOPERATIVE_ACCOUNT, name=COOP_NAME)
    assert reloaded.cooperative_account() == expected
    assert reloaded.member_account_numbers() == {1}  # das Genossenschaftskonto zählt nicht mit


def test_cooperative_account_exists_only_once():
    ledger = Ledger()
    ledger.open_cooperative_account(COOP_NAME)

    with pytest.raises(DomainError, match="gibt es bereits"):
        ledger.open_cooperative_account("Noch eins eG")


def test_cooperative_account_needs_name():
    with pytest.raises(DomainError, match="Bezeichnung"):
        Ledger().open_cooperative_account("  ")


def test_service_opens_cooperative_account(db):
    services.open_cooperative_account(db, COOP_NAME, actor="admin")

    account = services.get_ledger(db).cooperative_account()
    assert account is not None and account.name == COOP_NAME
    assert db.store.read_stream(SUBJECT)[0].actor == "admin"
