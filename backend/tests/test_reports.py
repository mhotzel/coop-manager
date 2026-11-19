"""Reports zum Stichtag: Mitgliederliste nach GenG (6a), Liste zur Generalversammlung (6c)."""

from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook

from coop_manager.accounts import bookings, exits
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.db import Database
from coop_manager.members import services
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.reports.services import AssemblyRow, GengRow, members_assembly, members_geng, sort_key
from coop_manager.system_settings.services import change_share_price
from coop_manager.users.domain import ACCOUNTING_READONLY, ADMIN

TODAY = date(2026, 11, 30)
ENTRY = date(2026, 11, 10)
YEAR_END = date(2026, 12, 31)
NEW_YEAR = date(2027, 1, 1)


@pytest.fixture
def setup(db) -> None:
    """Ersteinrichtung: Anteilspreis 50,00 € und Genossenschaftskonto."""
    change_share_price(db, 5000, actor="test")
    open_cooperative_account(db, "Musterladen eG", actor="test")


def applicant(db: Database, last_name: str = "Muster") -> str:
    """Erfundener Antrag über 3 Anteile, zugelassen am 05.11.2026; liefert die ID."""
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
    return member_id


def member(db: Database, last_name: str = "Muster") -> str:
    """Wie `applicant`, dazu eingezahlt am 10.11.2026: Mitglied mit 3 Anteilen (150,00 €)."""
    member_id = applicant(db, last_name)
    bookings.subscribe(db, account_number(db, member_id), 3, ENTRY, TODAY, actor="test")
    return member_id


def account_number(db: Database, member_id: str) -> int:
    account = get_ledger(db).account_of(member_id)
    assert account is not None
    return account.number


def shares(db: Database, day: date) -> list[int]:
    return [row.shares for row in members_geng(db, day)]


def test_member_row(db, setup):
    member(db)

    assert members_geng(db, YEAR_END) == [
        GengRow(
            member_number=1,
            name="Muster, Erika",
            address="Hauptstraße 1, 12345 Musterstadt",
            entry_date=ENTRY,
            amount=15000,
            shares=3,
        )
    ]


def test_only_from_entry(db, setup):
    member(db)

    assert members_geng(db, date(2026, 11, 9)) == []
    assert shares(db, ENTRY) == [3]


def test_applicant_not_listed(db, setup):
    applicant(db)

    assert members_geng(db, YEAR_END) == []


def test_notice_listed_until_year_end(db, setup):
    member_id = member(db)
    services.give_notice(db, member_id, date(2026, 11, 20), YEAR_END, TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    # Die Ausscheidensbuchung hat Wertstellung 31.12., zählt im Report aber erst ab dem 01.01.
    assert shares(db, YEAR_END) == [3]
    assert members_geng(db, NEW_YEAR) == []


def test_partial_notice_counts_until_year_end(db, setup):
    member_id = member(db)
    services.give_partial_notice(db, member_id, 1, date(2026, 11, 20), YEAR_END, TODAY, actor="test")
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    assert shares(db, YEAR_END) == [3]
    assert shares(db, NEW_YEAR) == [2]


def test_not_listed_on_day_of_donation(db, setup):
    member_id = member(db)
    bookings.donate(db, account_number(db, member_id), date(2026, 11, 25), TODAY, actor="test")

    assert shares(db, date(2026, 11, 24)) == [3]
    assert members_geng(db, date(2026, 11, 25)) == []


def test_reversed_payment_not_listed(db, setup):
    member_id = member(db)
    [subscription] = get_ledger(db).bookings_of(account_number(db, member_id))
    bookings.reverse(db, subscription.id, "falsch erfasst", TODAY, actor="test")

    assert members_geng(db, YEAR_END) == []


def test_sorted_by_member_number(db, setup):
    member(db, "Zabel")
    member(db, "Adler")

    assert [row.name for row in members_geng(db, YEAR_END)] == ["Zabel, Erika", "Adler, Erika"]


def test_download(client, db, setup, register, login):
    member(db)
    register("rita", ACCOUNTING_READONLY)
    login("rita")

    response = client.get("/api/reports/members-geng", params={"reference_date": "2026-12-31"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "Mitgliederliste-GenG-2026-12-31.xlsx" in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    assert sheet["A2"].value == "Stichtag: 31.12.2026"
    assert [cell.value for cell in sheet[4]] == ["Nr.", "Name", "Anschrift", "Eintritt", "Betrag", "Anteile"]
    row = [cell.value for cell in sheet[5]]
    assert row[:3] == [1, "Muster, Erika", "Hauptstraße 1, 12345 Musterstadt"]
    assert row[4:] == [150, 3]


def test_admin_may_not_download(client, setup, register, login):
    register("anna", ADMIN)
    login("anna")

    response = client.get("/api/reports/members-geng", params={"reference_date": "2026-12-31"})

    assert response.status_code == 403


# --- Liste zur Generalversammlung (6c) ---


def names(db: Database, day: date = YEAR_END) -> list[str]:
    return [row.name for row in members_assembly(db, day)]


def test_assembly_row(db, setup):
    member(db)

    assert members_assembly(db, YEAR_END) == [
        AssemblyRow(member_number=1, name="Muster, Erika", address="Hauptstraße 1, 12345 Musterstadt")
    ]


def test_assembly_sorted_by_name(db, setup):
    member(db, "Zabel")
    member(db, "Ölmann")
    member(db, "Adler")

    assert names(db) == ["Adler, Erika", "Ölmann, Erika", "Zabel, Erika"]


def test_assembly_with_notice_and_deceased(db, setup):
    services.give_notice(db, member(db, "Kündig"), date(2026, 11, 20), YEAR_END, TODAY, actor="test")
    services.record_death(db, member(db, "Verstorben"), date(2026, 11, 25), TODAY, actor="test")

    assert names(db) == ["Kündig, Erika", "Verstorben, Erika"]


def test_assembly_without_expelled(db, setup):
    member_id = member(db)
    services.expel(db, member_id, date(2026, 11, 25), TODAY, actor="test")

    assert names(db, date(2026, 11, 24)) == ["Muster, Erika"]
    assert names(db, date(2026, 11, 25)) == []
    # In der GenG-Liste stehen Ausgeschlossene bis zum Ausscheiden weiter.
    assert shares(db, date(2026, 11, 25)) == [3]


def test_assembly_without_applicant(db, setup):
    applicant(db)

    assert names(db) == []


def test_sort_key():
    assert sorted(["Zabel", "Äpfel", "abel", "Strauß", "Strausberg"], key=sort_key) == [
        "abel",
        "Äpfel",
        "Strausberg",
        "Strauß",
        "Zabel",
    ]


def test_assembly_download(client, db, setup, register, login):
    member(db)
    register("rita", ACCOUNTING_READONLY)
    login("rita")

    response = client.get("/api/reports/members-assembly", params={"reference_date": "2027-05-20"})

    assert response.status_code == 200
    assert "Generalversammlung-2027-05-20.xlsx" in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    assert sheet["A2"].value == "Stichtag: 20.05.2027"
    assert [cell.value for cell in sheet[4]] == ["Nr.", "Mitglied", "Adresse", "Vertreten durch", "Unterschrift"]
    assert [cell.value for cell in sheet[5]][:3] == [1, "Muster, Erika", "Hauptstraße 1, 12345 Musterstadt"]
    assert sheet.page_setup.orientation == "landscape"
