"""Umbuchung zwischen Mitgliedskonten (5h-3): auf Erben und unter Lebenden, Ausscheiden, Storno."""

from collections.abc import Iterator
from datetime import date

import pytest

from coop_manager.accounts import bookings, exits
from coop_manager.accounts.domain import REVERSAL, TRANSFER
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.projections import search_members
from coop_manager.members.status import APPLICANT, DECEASED, EXITED, MEMBER
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


def person(
    db: Database,
    last_name: str,
    shares: int = 3,
    applied: date = date(2026, 11, 2),
    admit: bool = True,
    pay: bool = True,
) -> tuple[str, int]:
    """Erfundene Person: (Mitglieds-ID, Kontonummer). Zulassung 3 Tage, Einzahlung 8 Tage nach Antrag."""
    member_id = services.apply_for_membership(
        db,
        person_type=NATURAL_PERSON,
        name=PersonName(first_names="Erika", last_name=last_name, gender="w"),
        address=Address(street="Hauptstraße", house_number="1", postal_code="12345", city="Musterstadt"),
        application_date=applied,
        shares_subscribed=shares,
        contact=None,
        actor="test",
    ).subject
    if admit:
        services.admit(db, member_id, date.fromordinal(applied.toordinal() + 3), TODAY, actor="test")
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    if pay:
        bookings.subscribe(db, account.number, shares, date.fromordinal(applied.toordinal() + 8), TODAY, actor="test")
    return member_id, account.number


def transfer(db: Database, source: int, target: int, shares: int, day: date = date(2026, 11, 20), today=TODAY):
    return bookings.transfer(db, source, target, shares, day, today, actor="test")


def test_heir_becomes_member_and_deceased_exits(db):
    deceased_id, deceased = person(db, "Muster")
    services.record_death(db, deceased_id, date(2026, 11, 15), TODAY, actor="test")
    heir_id, heir = person(db, "Erbe", pay=False)  # zeichnet die geerbten 3 Anteile

    result = transfer(db, deceased, heir, 3, date(2026, 11, 20))

    booking = result.booking
    assert (booking.kind, booking.debit, booking.credit) == (TRANSFER, deceased, heir)
    assert (booking.amount, booking.shares, booking.text) == (15000, 3, "Umbuchung")
    assert result.warning is None
    ledger = get_ledger(db)
    assert (ledger.balance(deceased), ledger.shares(deceased)) == (0, 0)
    assert (ledger.balance(heir), ledger.shares(heir)) == (15000, 3)
    h = services.get_member(db, heir_id)
    assert h.entry_date() == date(2026, 11, 20)
    assert h.status(date(2026, 11, 20)) == MEMBER
    d = services.get_member(db, deceased_id)
    assert d.transfer_date == date(2026, 11, 20)
    assert d.exit_date() == date(2026, 11, 20)  # früher als der 31.12. des Todesjahres
    assert d.status(date(2026, 11, 20)) == DECEASED
    assert d.status(date(2026, 11, 21)) == EXITED


def test_partial_transfer_between_living_members(db):
    source_id, source = person(db, "Muster")
    target_id, target = person(db, "Beispiel")

    result = transfer(db, source, target, 1)

    assert result.warning is None
    ledger = get_ledger(db)
    assert (ledger.balance(source), ledger.shares(source)) == (10000, 2)
    assert (ledger.balance(target), ledger.shares(target)) == (20000, 4)
    s = services.get_member(db, source_id)
    assert (s.transfer_date, s.status(TODAY)) == (None, MEMBER)
    t = services.get_member(db, target_id)
    assert (t.payment_date, t.status(TODAY)) == (date(2026, 11, 10), MEMBER)  # kein Abgleich


def test_all_shares_to_a_living_member_ends_membership(db):
    source_id, source = person(db, "Muster")
    _, target = person(db, "Beispiel")

    transfer(db, source, target, 3, date(2026, 11, 20))

    assert services.get_member(db, source_id).status(date(2026, 11, 21)) == EXITED
    rows = search_members(db.projections.conn, "", TODAY)  # beide Personen, nach Nummer sortiert
    assert [r.status for r in rows] == [EXITED, MEMBER]


def test_heir_with_fewer_shares_than_subscribed_gets_a_warning(db):
    deceased_id, deceased = person(db, "Muster", shares=2)
    services.record_death(db, deceased_id, date(2026, 11, 15), TODAY, actor="test")
    heir_id, heir = person(db, "Erbe", shares=3, pay=False)

    result = transfer(db, deceased, heir, 2)

    assert result.warning == "2 von 3 gezeichneten Anteilen eingezahlt."
    assert services.get_member(db, heir_id).status(TODAY) == APPLICANT


def test_death_known_after_year_end(db):
    deceased_id, deceased = person(db, "Muster", applied=date(2025, 3, 1))
    services.record_death(db, deceased_id, date(2025, 6, 1), TODAY, actor="test")
    heir_id, heir = person(db, "Erbe", pay=False)

    transfer(db, deceased, heir, 3, date(2026, 11, 20))

    d = services.get_member(db, deceased_id)
    assert d.exit_date() == date(2025, 12, 31)  # das Ausscheiden bleibt rückwirkend
    assert services.get_member(db, heir_id).status(TODAY) == MEMBER
    assert exits.exits_due(db, 2025) == []  # nichts mehr auf dem Konto, nichts zu buchen


def test_booked_exit_must_be_reversed_first(db):
    deceased_id, deceased = person(db, "Muster", applied=date(2025, 3, 1))
    services.record_death(db, deceased_id, date(2025, 6, 1), TODAY, actor="test")
    exits.post_exits(db, 2025, TODAY, actor="test")
    _, heir = person(db, "Erbe", pay=False)

    with pytest.raises(DomainError, match="zuerst die Ausscheidensbuchung stornieren"):
        transfer(db, deceased, heir, 3)


def test_reversal_restores_both_sides(db):
    deceased_id, deceased = person(db, "Muster")
    services.record_death(db, deceased_id, date(2026, 11, 15), TODAY, actor="test")
    heir_id, heir = person(db, "Erbe", pay=False)
    booking = transfer(db, deceased, heir, 3).booking

    result = bookings.reverse(db, booking.id, "falscher Erbe", TODAY, actor="test")

    assert result.booking.kind == REVERSAL
    assert (result.booking.debit, result.booking.credit) == (heir, deceased)
    assert result.warning is not None and "Geldeingang ist zurückgenommen" in result.warning
    ledger = get_ledger(db)
    assert (ledger.shares(deceased), ledger.shares(heir)) == (3, 0)
    d = services.get_member(db, deceased_id)
    assert (d.transfer_date, d.exit_date()) == (None, date(2026, 12, 31))
    assert services.get_member(db, heir_id).status(TODAY) == APPLICANT


def test_reversal_of_partial_transfer_leaves_target_membership(db):
    _, source = person(db, "Muster")
    target_id, target = person(db, "Beispiel")
    booking = transfer(db, source, target, 1).booking

    result = bookings.reverse(db, booking.id, "Irrtum", TODAY, actor="test")

    assert result.warning is None
    assert services.get_member(db, target_id).status(TODAY) == MEMBER


def test_partially_noticed_shares_stay(db):
    source_id, source = person(db, "Muster")
    _, target = person(db, "Beispiel")
    services.give_partial_notice(db, source_id, 2, date(2026, 11, 12), date(2028, 12, 31), TODAY, actor="test")

    with pytest.raises(DomainError, match="Höchstens 1"):
        transfer(db, source, target, 2)
    transfer(db, source, target, 3)  # alle Anteile gehen; die Teilkündigung wird gegenstandslos

    assert not services.get_member(db, source_id).has_partial_notice(date(2026, 11, 21))


def test_not_more_than_held(db):
    _, source = person(db, "Muster")
    _, target = person(db, "Beispiel")

    with pytest.raises(DomainError, match="nur 3 Anteile"):
        transfer(db, source, target, 4)


def test_target_must_be_admitted(db):
    _, source = person(db, "Muster")
    _, target = person(db, "Beispiel", admit=False, pay=False)

    with pytest.raises(DomainError, match="zugelassener Antragsteller"):
        transfer(db, source, target, 1)


def test_not_to_the_same_account(db):
    _, source = person(db, "Muster")

    with pytest.raises(DomainError, match="verschieden"):
        transfer(db, source, source, 1)


def test_not_to_the_cooperative(db):
    _, source = person(db, "Muster")

    with pytest.raises(DomainError, match="kein Mitgliedskonto"):
        transfer(db, source, 9999, 1)


def test_expelled_cannot_give(db):
    source_id, source = person(db, "Muster")
    _, target = person(db, "Beispiel")
    services.expel(db, source_id, date(2026, 11, 15), TODAY, actor="test")

    with pytest.raises(DomainError, match="Mitglied"):
        transfer(db, source, target, 1)


def test_no_notice_after_transferring_everything(db):
    source_id, source = person(db, "Muster")
    _, target = person(db, "Beispiel")
    transfer(db, source, target, 3, date(2026, 11, 20))

    with pytest.raises(DomainError, match="übertragen"):
        services.give_notice(db, source_id, date(2026, 11, 20), date(2028, 12, 31), TODAY, actor="test")
