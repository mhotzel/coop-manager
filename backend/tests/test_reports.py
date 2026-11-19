"""Reports zum Stichtag: GenG-Liste (6a), Generalversammlung (6c), Seriendruck (6d), Warnungen (6e)."""

from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook

from coop_manager.accounts import bookings, exits
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.db import Database
from coop_manager.members import services
from coop_manager.members.values import NATURAL_PERSON, Address, PersonName
from coop_manager.reports.services import (
    AssemblyRow,
    GengRow,
    members_assembly,
    members_geng,
    members_mailing,
    sort_key,
    warnings,
)
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
    assert sheet["A3"].value is None  # keine Warnung
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


# --- Seriendruck-Liste (6d) ---

MAILING_HEADERS = [
    "PersNr",
    "name_mitgl",
    "Land",
    "PLZ",
    "Ort",
    "Strasse",
    "HausNr",
    "BriefAnrede",
    "AdrZeile1",
    "AdrZeile2",
    "AdrZeile3",
    "AdrZeile4",
    "AdrZeile5",
    "AdrZeile6",
    "austritt",
    "summe_anteile",
    "anz_anteile",
    "jahr_report",
    "Verstorben",
]


def test_mailing_row(db, setup):
    member(db)

    [row] = members_mailing(db, YEAR_END)

    assert (row.member_number, row.name, row.country) == (1, "Muster, Erika", "")
    assert (row.street, row.house_number, row.postal_code, row.city) == ("Hauptstraße", "1", "12345", "Musterstadt")
    assert row.salutation == "Sehr geehrte Frau Muster"
    assert row.address_lines == ("Frau", "Erika Muster", "Hauptstraße 1", "12345 Musterstadt", "", "")
    assert (row.exit_date, row.date_of_death) == (None, None)
    assert (row.amount, row.shares) == (15000, 3)


def test_mailing_salutation_override(db, setup):
    member_id = member(db)
    services.change_salutation(db, member_id, "Liebe Familie Muster", actor="test")

    assert [row.salutation for row in members_mailing(db, YEAR_END)] == ["Liebe Familie Muster"]


def test_mailing_deceased(db, setup):
    member_id = member(db)
    services.record_death(db, member_id, date(2026, 11, 25), TODAY, actor="test")

    # Vor dem Tod zum Stichtag noch wie ein Mitglied.
    [before] = members_mailing(db, date(2026, 11, 24))
    assert (before.salutation, before.exit_date, before.date_of_death) == ("Sehr geehrte Frau Muster", None, None)
    [row] = members_mailing(db, YEAR_END)
    assert row.salutation == "Sehr geehrte Damen und Herren"
    assert (row.exit_date, row.date_of_death) == (YEAR_END, date(2026, 11, 25))


def test_mailing_notice(db, setup):
    services.give_notice(db, member(db), date(2026, 11, 20), YEAR_END, TODAY, actor="test")

    assert [row.exit_date for row in members_mailing(db, YEAR_END)] == [YEAR_END]


def test_mailing_without_no_mail_and_expelled(db, setup):
    services.change_mail_preference(db, member(db, "Ohnepost"), True, actor="test")
    services.expel(db, member(db, "Raus"), date(2026, 11, 25), TODAY, actor="test")
    member(db, "Bleibt")

    assert [row.name for row in members_mailing(db, YEAR_END)] == ["Bleibt, Erika"]


def test_mailing_download(client, db, setup, register, login):
    member(db)
    register("rita", ACCOUNTING_READONLY)
    login("rita")

    response = client.get("/api/reports/members-mailing", params={"reference_date": "2027-04-01"})

    assert response.status_code == 200
    assert "Seriendruck-2027-04-01.xlsx" in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet is not None
    # Erste Zeile = Feldnamen, sonst findet Word die Felder nicht.
    assert [cell.value for cell in sheet[1]] == MAILING_HEADERS
    row = dict(zip(MAILING_HEADERS, [cell.value for cell in sheet[2]], strict=True))
    assert (row["PersNr"], row["name_mitgl"], row["AdrZeile3"]) == (1, "Muster, Erika", "Hauptstraße 1")
    assert (row["summe_anteile"], row["anz_anteile"], row["jahr_report"]) == (150, 3, 2027)
    assert (row["austritt"], row["Verstorben"]) == (None, None)


# --- Warnung bei nicht gebuchtem Ausscheiden (6e) ---

JANUARY = date(2027, 1, 15)
OPEN_EXIT = (
    "Zum 31.12.2026 ist 1 Ausscheiden noch nicht gebucht (Seite Jahresende)."
    " Anteile und Beträge können deshalb zu hoch sein."
)


@pytest.fixture
def partial_notice(db, setup) -> None:
    """Teilkündigung über 1 Anteil zum 31.12.2026, das Ausscheiden ist noch nicht gebucht."""
    services.give_partial_notice(db, member(db), 1, date(2026, 11, 20), YEAR_END, TODAY, actor="test")


def test_warning_for_open_exit(db, partial_notice):
    assert warnings(db, JANUARY) == [OPEN_EXIT]
    # Ohne Buchung zählen die gekündigten Anteile noch mit; genau davor warnt der Hinweis.
    assert shares(db, JANUARY) == [3]


def test_no_warning_once_posted(db, partial_notice):
    exits.post_exits(db, 2026, date(2027, 1, 5), actor="test")

    assert warnings(db, JANUARY) == []


def test_no_warning_up_to_year_end(db, partial_notice):
    # Bis einschließlich 31.12. zählen die Anteile ohnehin noch (siehe Plan).
    assert warnings(db, YEAR_END) == []


def test_warning_in_download(client, db, partial_notice, register, login):
    register("rita", ACCOUNTING_READONLY)
    login("rita")

    assert client.get("/api/reports/warnings", params={"reference_date": "2027-01-15"}).json() == [OPEN_EXIT]
    for path in ("members-geng", "members-assembly"):
        response = client.get(f"/api/reports/{path}", params={"reference_date": "2027-01-15"})
        sheet = load_workbook(BytesIO(response.content)).active
        assert sheet is not None
        assert sheet["A3"].value == OPEN_EXIT
