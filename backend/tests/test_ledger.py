from datetime import date

import pytest

from coop_manager.accounts import services
from coop_manager.accounts.domain import (
    COOPERATIVE_ACCOUNT,
    COOPERATIVE_ACCOUNT_NUMBER,
    EXIT,
    MEMBER_ACCOUNT,
    PAYOUT,
    REFUND,
    REVERSAL,
    SUBJECT,
    SUBSCRIPTION,
    TRANSFER,
    Account,
    Booking,
    Ledger,
)
from coop_manager.core import DomainError

COOP_NAME = "Musterladen eG"  # erfunden
COOP = COOPERATIVE_ACCOUNT_NUMBER
TODAY = date(2026, 11, 30)


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


# --- Buchungen ---


def ledger_for_bookings() -> Ledger:
    """Hauptbuch mit Genossenschaftskonto und den Mitgliedskonten 1 und 2."""
    ledger = ledger_with(1, 2)
    ledger.open_cooperative_account(COOP_NAME)
    return ledger


def post(ledger: Ledger, debit: int = COOP, credit: int = 1, amount: int = 10000, shares: int = 2, **overrides):
    """Bucht mit erfundenen Werten; Vorgabe ist ein Eintritt über 2 Anteile zu 100,00 €."""
    data = {"kind": SUBSCRIPTION, "text": "Eintritt", "value_date": date(2026, 11, 20), "booking_date": TODAY}
    return ledger.post_booking(debit=debit, credit=credit, amount=amount, shares=shares, **(data | overrides))


def test_new_account_has_balance_and_shares_zero():
    ledger = ledger_for_bookings()

    assert (ledger.balance(1), ledger.shares(1), ledger.bookings_of(1)) == (0, 0, [])


def test_post_booking():
    ledger = ledger_for_bookings()
    booking = post(ledger, text="  Eintritt 2 Anteile ")

    reloaded = Ledger.from_events(SUBJECT, ledger.uncommitted_events)
    assert reloaded.bookings == [booking]
    assert booking == Booking(
        id=booking.id,
        kind=SUBSCRIPTION,
        debit=COOP,
        credit=1,
        amount=10000,
        shares=2,
        text="Eintritt 2 Anteile",
        booking_date=TODAY,
        value_date=date(2026, 11, 20),
    )
    assert len(booking.id) == 36  # UUID als Text


def test_balance_and_shares_credit_positive_debit_negative():
    ledger = ledger_for_bookings()
    post(ledger, credit=1, amount=10000, shares=2)  # Eintritt Mitglied 1
    post(ledger, credit=2, amount=5000, shares=1)  # Eintritt Mitglied 2
    post(ledger, kind=TRANSFER, debit=1, credit=2, amount=5000, shares=1)  # Umbuchung 1 → 2

    assert (ledger.balance(1), ledger.shares(1)) == (5000, 1)
    assert (ledger.balance(2), ledger.shares(2)) == (10000, 2)
    assert (ledger.balance(COOP), ledger.shares(COOP)) == (-15000, -3)  # darf negativ werden
    assert len(ledger.bookings_of(1)) == 2


def test_exit_moves_shares_but_keeps_balance():
    """Ausscheiden: Die Anteile verlassen den Bestand, der Saldo bleibt als Anspruch stehen."""
    ledger = ledger_for_bookings()
    post(ledger)
    post(ledger, kind=EXIT, debit=1, credit=COOP, amount=0, shares=2)

    assert (ledger.balance(1), ledger.shares(1)) == (10000, 0)


def test_payout_moves_amount_without_shares():
    ledger = ledger_for_bookings()
    post(ledger)
    post(ledger, kind=EXIT, debit=1, credit=COOP, amount=0, shares=2)
    post(ledger, kind=PAYOUT, debit=1, credit=COOP, amount=4000, shares=0)

    assert (ledger.balance(1), ledger.shares(1)) == (6000, 0)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"kind": "gift"}, "Unbekannte Buchungsart"),
        ({"debit": 7}, "Konto 7 gibt es nicht"),
        ({"credit": 7}, "Konto 7 gibt es nicht"),
        ({"debit": 1, "credit": 1}, "verschieden"),
        ({"amount": -1}, "nicht negativ"),
        ({"shares": -1}, "nicht negativ"),
        ({"amount": 0, "shares": 0}, "größer als 0"),
        ({"text": "  "}, "Buchungstext fehlt"),
        ({"value_date": date(2026, 12, 1)}, "nicht nach dem Buchungstag"),
    ],
)
def test_post_booking_checks_input(overrides, message):
    with pytest.raises(DomainError, match=message):
        post(ledger_for_bookings(), **overrides)


def test_value_date_may_be_booking_date():
    booking = post(ledger_for_bookings(), value_date=TODAY)

    assert booking.value_date == TODAY


def test_member_account_balance_must_not_become_negative():
    ledger = ledger_for_bookings()
    post(ledger, amount=10000, shares=2)

    with pytest.raises(DomainError, match="Saldo von Konto 1 reicht nicht"):
        post(ledger, kind=PAYOUT, debit=1, credit=COOP, amount=10001, shares=0)
    post(ledger, kind=PAYOUT, debit=1, credit=COOP, amount=10000, shares=0)  # genau der Saldo geht


def test_member_account_shares_must_not_become_negative():
    ledger = ledger_for_bookings()
    post(ledger, amount=10000, shares=2)

    with pytest.raises(DomainError, match="Konto 1 hat nicht so viele Anteile"):
        post(ledger, kind=EXIT, debit=1, credit=COOP, amount=0, shares=3)


def test_failed_booking_records_no_event():
    ledger = ledger_for_bookings()
    events_before = len(ledger.uncommitted_events)

    with pytest.raises(DomainError):
        post(ledger, debit=1, credit=COOP)  # Konto 1 ist noch leer

    assert len(ledger.uncommitted_events) == events_before
    assert ledger.bookings == []


def test_bookings_survive_event_store(db):
    """Über den echten Event Store, also mit JSON dazwischen (Datum als Text)."""
    ledger = ledger_for_bookings()
    booking = post(ledger)
    db.save(ledger, "test")

    reloaded = services.get_ledger(db)
    assert reloaded.bookings == [booking]
    assert (reloaded.balance(1), reloaded.shares(1)) == (10000, 2)


# --- Storno ---


def test_reverse_swaps_accounts_and_keeps_values():
    ledger = ledger_for_bookings()
    original = post(ledger)  # Eintritt Konto 1, Wertstellung 20.11.2026

    reversal = ledger.reverse(original.id, "Storno zu „Eintritt“: falsch zugeordnet", date(2026, 12, 3))

    assert (reversal.kind, reversal.debit, reversal.credit) == (REVERSAL, 1, COOP)
    assert (reversal.amount, reversal.shares) == (original.amount, original.shares)
    assert reversal.value_date == original.value_date  # Wertstellung wie das Original
    assert reversal.booking_date == date(2026, 12, 3)  # gebucht wird heute
    assert reversal.reverses == original.id
    assert (ledger.balance(1), ledger.shares(1)) == (0, 0)
    reloaded = Ledger.from_events(SUBJECT, ledger.uncommitted_events)
    assert reloaded.reversal_of(original.id) == reversal
    assert reloaded.booking(original.id) == original


def test_booking_can_be_reversed_only_once():
    ledger = ledger_for_bookings()
    original = post(ledger, shares=4, amount=20000)
    ledger.reverse(original.id, "Storno", TODAY)

    with pytest.raises(DomainError, match="bereits storniert"):
        ledger.reverse(original.id, "Storno", TODAY)


def test_reversal_cannot_be_reversed():
    ledger = ledger_for_bookings()
    reversal = ledger.reverse(post(ledger).id, "Storno", TODAY)

    with pytest.raises(DomainError, match="Storno kann nicht storniert"):
        ledger.reverse(reversal.id, "Storno", TODAY)


def test_reverse_unknown_booking():
    with pytest.raises(DomainError, match="Buchung gibt es nicht"):
        ledger_for_bookings().reverse("unbekannt", "Storno", TODAY)


def test_reverse_must_not_make_member_account_negative():
    """Eintritt, dann schon zurückgezahlt: Ein Storno des Eintritts würde das Konto ins Minus bringen."""
    ledger = ledger_for_bookings()
    original = post(ledger)
    post(ledger, kind=REFUND, debit=1, credit=COOP)

    with pytest.raises(DomainError, match="reicht nicht aus"):
        ledger.reverse(original.id, "Storno", TODAY)


def test_old_events_without_reverses_still_load():
    """Events von vor Schritt 5e haben kein Feld „reverses“."""
    ledger = ledger_for_bookings()
    post(ledger)
    events = ledger.uncommitted_events
    del events[-1].data["reverses"]

    assert Ledger.from_events(SUBJECT, events).bookings[0].reverses is None
