from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import bookings
from coop_manager.accounts.domain import COOPERATIVE_ACCOUNT_NUMBER, REFUND, REVERSAL, SUBSCRIPTION
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError, NotFoundError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.projections import search_members
from coop_manager.members.status import APPLICANT, MEMBER, REJECTED
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.system_settings.services import change_share_price

TODAY = date(2026, 11, 30)
PRICE = 5000  # 50,00 € je Anteil
COOP = COOPERATIVE_ACCOUNT_NUMBER


@pytest.fixture
def bare_db(tmp_path) -> Iterator[Database]:
    """Datenbank ohne Anteilspreis und ohne Genossenschaftskonto."""
    prepare(tmp_path, PROJECTORS, SCHEMAS)
    db = Database(tmp_path, PROJECTORS)
    yield db
    db.close()


@pytest.fixture
def db(bare_db) -> Database:
    """Datenbank mit Anteilspreis 50,00 € und Genossenschaftskonto, wie nach der Ersteinrichtung."""
    change_share_price(bare_db, PRICE, actor="test")
    open_cooperative_account(bare_db, "Musterladen eG", actor="test")
    return bare_db


def apply(db: Database, shares_subscribed: int = 2) -> str:
    """Erfasst einen erfundenen Antrag vom 02.11.2026 und liefert die Mitglieds-ID."""
    return services.apply_for_membership(
        db,
        person_type=NATURAL_PERSON,
        name=PersonName(first_names="Erika", last_name="Muster", gender="w"),
        address=Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt"),
        application_date=date(2026, 11, 2),
        shares_subscribed=shares_subscribed,
        contact=None,
        actor="test",
    ).subject


def number_of(db: Database, member_id: str) -> int:
    """Die Kontonummer des Mitglieds; die Vorgänge sprechen das Konto über seine Nummer an."""
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    return account.number


def subscribe(db: Database, member_id: str, shares: int = 2, value_date: date = date(2026, 11, 10)):
    return bookings.subscribe(db, number_of(db, member_id), shares, value_date, TODAY, actor="erika")


def refund(db: Database, member_id: str, shares: int = 1, value_date: date = date(2026, 11, 20)):
    return bookings.refund(db, number_of(db, member_id), shares, value_date, TODAY, actor="erika")


def balance_and_shares(db: Database, member_id: str) -> tuple[int, int]:
    number = number_of(db, member_id)
    ledger = get_ledger(db)
    return ledger.balance(number), ledger.shares(number)


def test_subscribe_with_subscribed_shares_records_payment(db):
    member_id = apply(db, shares_subscribed=2)

    result = subscribe(db, member_id, shares=2, value_date=date(2026, 11, 10))

    assert result.warning is None
    booking = result.booking
    assert (booking.kind, booking.debit, booking.credit) == (SUBSCRIPTION, COOP, 1)
    assert (booking.amount, booking.shares, booking.text) == (2 * PRICE, 2, "Eintritt")
    assert balance_and_shares(db, member_id) == (10000, 2)
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 10)
    assert db.store.read_stream(member_id)[-1].actor == "erika"


def test_member_after_admission(db):
    member_id = apply(db)
    subscribe(db, member_id, value_date=date(2026, 11, 10))
    services.admit(db, member_id, date(2026, 11, 15), TODAY, actor="test")

    member = services.get_member(db, member_id)
    assert member.entry_date() == date(2026, 11, 15)
    assert member.status(TODAY) == MEMBER


def test_member_list_shows_status_member(db):
    """Der ganze Weg bis in die Projektion: Mitglied erst mit Geldeingang und Zulassung."""
    member_id = apply(db)

    def status_in_list() -> str | None:
        rows = search_members(db.projections.conn, "muster", TODAY)
        return next(row.status for row in rows if row.id == member_id)

    subscribe(db, member_id)
    assert status_in_list() == APPLICANT

    services.admit(db, member_id, date(2026, 11, 15), TODAY, actor="test")
    assert status_in_list() == MEMBER


def test_partial_payment_warns_and_second_booking_completes(db):
    member_id = apply(db, shares_subscribed=2)

    first = subscribe(db, member_id, shares=1, value_date=date(2026, 11, 10))
    assert first.warning == "1 von 2 gezeichneten Anteilen eingezahlt."
    assert services.get_member(db, member_id).payment_date is None

    second = subscribe(db, member_id, shares=1, value_date=date(2026, 11, 12))
    assert second.warning is None
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 12)


def test_overpayment_warns_and_refund_of_surplus_completes(db):
    member_id = apply(db, shares_subscribed=2)

    result = subscribe(db, member_id, shares=3)
    assert result.warning is not None and "Mehr Anteile eingezahlt als gezeichnet (3 von 2)" in result.warning
    assert services.get_member(db, member_id).payment_date is None

    result = refund(db, member_id, shares=1, value_date=date(2026, 11, 20))
    assert result.warning is None
    assert (result.booking.kind, result.booking.debit, result.booking.credit) == (REFUND, 1, COOP)
    assert balance_and_shares(db, member_id) == (10000, 2)
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 20)


def test_payment_after_rejection_warns_and_can_be_refunded(db):
    member_id = apply(db)
    services.reject(db, member_id, date(2026, 11, 5), TODAY, actor="test")

    result = subscribe(db, member_id, value_date=date(2026, 11, 10))
    assert result.warning is not None and "zurückgezahlt" in result.warning
    assert services.get_member(db, member_id).payment_date is None

    result = refund(db, member_id, shares=2)
    assert result.warning is None
    assert balance_and_shares(db, member_id) == (0, 0)
    assert services.get_member(db, member_id).status(TODAY) == REJECTED


def test_refund_after_rejection_of_paid_applicant(db):
    """Passend gezahlt, dann lehnt der Vorstand ab: Rückzahlung ist möglich."""
    member_id = apply(db)
    subscribe(db, member_id)
    services.reject(db, member_id, date(2026, 11, 15), TODAY, actor="test")

    refund(db, member_id, shares=2)

    assert balance_and_shares(db, member_id) == (0, 0)


def test_no_refund_after_recorded_payment(db):
    member_id = apply(db)
    subscribe(db, member_id)

    with pytest.raises(DomainError, match="Zurückgezahlt wird nur"):
        refund(db, member_id, shares=2)


def test_no_subscription_when_fully_paid(db):
    member_id = apply(db)
    subscribe(db, member_id)

    with pytest.raises(DomainError, match="bereits eingezahlt"):
        subscribe(db, member_id, shares=1)


def test_no_subscription_when_overpaid(db):
    member_id = apply(db, shares_subscribed=2)
    subscribe(db, member_id, shares=3)

    with pytest.raises(DomainError, match="bereits eingezahlt"):
        subscribe(db, member_id, shares=1)


def test_value_date_not_before_application(db):
    member_id = apply(db)

    with pytest.raises(DomainError, match="nicht vor dem Antrag"):
        subscribe(db, member_id, value_date=date(2026, 11, 1))


def test_at_least_one_share(db):
    member_id = apply(db)

    with pytest.raises(DomainError, match="mindestens ein Anteil"):
        subscribe(db, member_id, shares=0)


def test_needs_share_price(bare_db):
    open_cooperative_account(bare_db, "Musterladen eG", actor="test")
    member_id = apply(bare_db)

    with pytest.raises(DomainError, match="kein Anteilspreis"):
        subscribe(bare_db, member_id)


def test_needs_cooperative_account(bare_db):
    change_share_price(bare_db, PRICE, actor="test")
    member_id = apply(bare_db)

    with pytest.raises(DomainError, match="Genossenschaftskonto fehlt"):
        subscribe(bare_db, member_id)


def test_unknown_account(db):
    with pytest.raises(NotFoundError, match="Konto 7 gibt es nicht"):
        bookings.subscribe(db, 7, 1, date(2026, 11, 10), TODAY, actor="erika")


def test_cooperative_account_is_not_a_member_account(db):
    with pytest.raises(DomainError, match="kein Mitgliedskonto"):
        bookings.refund(db, COOP, 1, date(2026, 11, 10), TODAY, actor="erika")


def test_own_booking_text(db):
    member_id = apply(db)

    result = bookings.subscribe(
        db, number_of(db, member_id), 2, date(2026, 11, 10), TODAY, "erika", "Eintritt Überweisung"
    )

    assert result.booking.text == "Eintritt Überweisung"


def test_failed_booking_saves_nothing(db):
    """Die Rückzahlung über mehr Anteile als vorhanden scheitert im Hauptbuch; nichts wird gespeichert."""
    member_id = apply(db)
    services.reject(db, member_id, date(2026, 11, 5), TODAY, actor="test")
    subscribe(db, member_id, shares=1)
    ledger_events = len(db.store.read_stream("ledger"))
    member_events = len(db.store.read_stream(member_id))

    with pytest.raises(DomainError, match="nicht so viele Anteile|reicht nicht"):
        refund(db, member_id, shares=2)

    assert len(db.store.read_stream("ledger")) == ledger_events
    assert len(db.store.read_stream(member_id)) == member_events


def test_concurrent_booking_is_retried_with_fresh_balance(db, tmp_path, monkeypatch):
    """Simuliert: Während dieser Eintritt läuft, bucht ein zweiter Request den ersten Anteil.

    Unser erster Versuch scheitert an der Versionsprüfung des Hauptbuchs; der zweite rechnet mit
    dem neuen Stand und erkennt, dass jetzt beide gezeichneten Anteile eingezahlt sind.
    """
    member_id = apply(db, shares_subscribed=2)
    load_ledger = bookings.get_ledger
    calls = []

    def load_and_let_someone_else_win(db_: Database):
        ledger = load_ledger(db_)  # sieht noch keine Buchung
        calls.append(1)
        if len(calls) == 1:
            other = Database(tmp_path, PROJECTORS)  # eigene Verbindung, wie ein zweiter Request
            monkeypatch.setattr(bookings, "get_ledger", load_ledger)
            subscribe(other, member_id, shares=1, value_date=date(2026, 11, 10))
            monkeypatch.setattr(bookings, "get_ledger", load_and_let_someone_else_win)
            other.close()
        return ledger

    monkeypatch.setattr(bookings, "get_ledger", load_and_let_someone_else_win)
    result = subscribe(db, member_id, shares=1, value_date=date(2026, 11, 12))

    assert len(calls) == 2  # ein Konflikt, dann Erfolg
    assert result.warning is None
    assert balance_and_shares(db, member_id) == (10000, 2)
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 12)


# --- Storno ---


def reverse(db: Database, booking_id: str, reason: str = "falsch zugeordnet"):
    return bookings.reverse(db, booking_id, reason, TODAY, actor="erika")


def status_in_list(db: Database, member_id: str) -> str | None:
    rows = search_members(db.projections.conn, "muster", TODAY)
    return next(row.status for row in rows if row.id == member_id)


def test_reverse_subscription_revokes_payment_and_membership(db):
    member_id = apply(db)
    original = subscribe(db, member_id, value_date=date(2026, 11, 10)).booking
    services.admit(db, member_id, date(2026, 11, 15), TODAY, actor="test")
    assert status_in_list(db, member_id) == MEMBER

    result = reverse(db, original.id, " falsch zugeordnet ")

    booking = result.booking
    assert (booking.kind, booking.debit, booking.credit) == (REVERSAL, 1, COOP)
    assert booking.text == "Storno zu „Eintritt“: falsch zugeordnet"
    assert (booking.value_date, booking.reverses) == (date(2026, 11, 10), original.id)
    assert result.warning == (
        "Der Geldeingang ist zurückgenommen, 0 von 2 gezeichneten Anteilen eingezahlt. "
        "Die Person ist nicht mehr Mitglied. Bitte klären."
    )
    assert balance_and_shares(db, member_id) == (0, 0)
    member = services.get_member(db, member_id)
    assert (member.payment_date, member.status(TODAY)) == (None, APPLICANT)
    assert status_in_list(db, member_id) == APPLICANT  # auch die Projektion
    assert db.store.read_stream(member_id)[-1].type == "member.paid-in-revoked"


def test_reverse_subscription_before_admission_warns_without_membership_note(db):
    member_id = apply(db)
    original = subscribe(db, member_id).booking

    result = reverse(db, original.id)

    assert (
        result.warning == "Der Geldeingang ist zurückgenommen, 0 von 2 gezeichneten Anteilen eingezahlt. Bitte klären."
    )
    assert services.get_member(db, member_id).payment_date is None


def test_reverse_partial_payment_leaves_member_unchanged(db):
    member_id = apply(db, shares_subscribed=2)
    original = subscribe(db, member_id, shares=1).booking
    member_events = len(db.store.read_stream(member_id))

    result = reverse(db, original.id)

    assert result.warning == "0 von 2 gezeichneten Anteilen eingezahlt."
    assert len(db.store.read_stream(member_id)) == member_events


def test_reverse_refund_records_payment_again(db):
    """Überzahlt (3 von 2), 1 Anteil zurück → Geldeingang; Storno der Rückzahlung → wieder überzahlt."""
    member_id = apply(db, shares_subscribed=2)
    subscribe(db, member_id, shares=3)
    refunded = refund(db, member_id, shares=1, value_date=date(2026, 11, 20)).booking
    assert services.get_member(db, member_id).payment_date == date(2026, 11, 20)

    result = reverse(db, refunded.id)

    assert result.warning is not None and "zurückgenommen, 3 von 2" in result.warning
    assert services.get_member(db, member_id).payment_date is None


def test_reversal_completing_payment_records_it_with_warning(db):
    """Ein Storno, nach dem die gezeichneten Anteile voll eingezahlt sind (z. B. Storno einer Rückzahlung).

    Mit den heutigen Vorgängen lässt sich das nicht herstellen: Wer die gezeichneten Anteile
    erreicht, hat sofort den Geldeingang, und danach ist keine Rückzahlung mehr erlaubt. Deshalb
    wird der Abgleich hier direkt mit einer passenden Stornobuchung aufgerufen.
    """
    member_id = apply(db, shares_subscribed=2)
    member = services.get_member(db, member_id)
    ledger = get_ledger(db)
    booking = ledger.post_booking(REVERSAL, COOP, 1, 2 * PRICE, 2, "Storno", date(2026, 11, 20), TODAY)

    warning = bookings._reconcile(member, ledger, 1, booking, TODAY)

    assert warning == "Der Geldeingang ist jetzt mit Wertstellung 20.11.2026 erfasst. Bitte prüfen."
    assert member.payment_date == date(2026, 11, 20)


def test_reverse_needs_reason(db):
    member_id = apply(db)
    original = subscribe(db, member_id).booking

    with pytest.raises(DomainError, match="Stornogrund fehlt"):
        reverse(db, original.id, "  ")


def test_reverse_unknown_booking(db):
    with pytest.raises(NotFoundError, match="Buchung gibt es nicht"):
        reverse(db, "unbekannt")


def test_reverse_only_once(db):
    member_id = apply(db)
    original = subscribe(db, member_id).booking
    reverse(db, original.id)

    with pytest.raises(DomainError, match="bereits storniert"):
        reverse(db, original.id)
