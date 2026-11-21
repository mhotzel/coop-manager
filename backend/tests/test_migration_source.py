"""Einlesen der Altdaten (CSV aus `mdb-export`) und der Einzelfälle; alle Daten erfunden."""

import csv
from datetime import date, datetime
from pathlib import Path

from coop_manager.migration.source import load_decisions, load_legacy

# Spaltennamen gemischt geschrieben wie im echten Export; gelesen wird klein geschrieben.
PERSON_COLUMNS = [
    "PersNr", "Firma", "Geschlecht", "Name", "Vorname", "Titel", "Land", "PLZ", "Ort", "Strasse",
    "HausNr", "Telefon1", "eMail", "BriefAnrede", "AdrZeile1", "AdrZeile2", "AdrZeile3", "AdrZeile4",
    "AdrZeile5", "AdrZeile6", "Eintritt", "Kündigung", "Austritt", "Verstorben", "KeinePost", "hinweise",
]  # fmt: skip
BOOKING_COLUMNS = ["id", "kto_soll", "kto_haben", "anz_anteil", "betrag_anteil", "datum", "Buchtext"]


def person_row(**values: str) -> dict[str, str]:
    row = dict.fromkeys(PERSON_COLUMNS, "")
    row |= {"PersNr": "7", "Geschlecht": "w", "Name": "Muster", "Vorname": "Erika", "KeinePost": "0"}
    return row | values


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_legacy(
    tmp_path: Path,
    people: list[dict[str, str]],
    history: list[dict[str, str]] | None = None,
    bookings: list[dict[str, str]] | None = None,
) -> Path:
    write_csv(tmp_path / "mitglieder.csv", PERSON_COLUMNS, people)
    write_csv(tmp_path / "mitglieder_hist.csv", [*PERSON_COLUMNS, "last_update"], history or [])
    write_csv(tmp_path / "buchungen.csv", BOOKING_COLUMNS, bookings or [])
    return tmp_path


def test_reads_person_with_dates_flags_and_address_lines(tmp_path):
    row = person_row(
        Eintritt="2014-11-01 00:00:00",
        Verstorben="1899-12-30 00:00:00",  # Nullwert von Access
        KeinePost="1",
        AdrZeile1=" Frau ",
        AdrZeile2="Erika Muster",
        eMail="erika@example.org",
    )
    data = load_legacy(write_legacy(tmp_path, [row]))

    person = data.people[7]
    assert (person.first_names, person.last_name, person.gender) == ("Erika", "Muster", "w")
    assert person.entry == date(2014, 11, 1)
    assert person.death is None
    assert person.no_mail is True
    assert person.address_lines == ("Frau", "Erika Muster", "", "", "", "")
    assert person.email == "erika@example.org"
    assert person.last_update is None


def test_reads_history_sorted_by_last_update(tmp_path):
    later = person_row(Name="Neumann", last_update="2024-06-30 14:12:00")
    first = person_row(last_update="1900-01-01 00:00:00")
    data = load_legacy(write_legacy(tmp_path, [person_row()], history=[later, first]))

    versions = data.history[7]
    assert [v.last_name for v in versions] == ["Muster", "Neumann"]
    assert versions[1].last_update == datetime(2024, 6, 30, 14, 12)


def test_reads_booking_amount_in_cents(tmp_path):
    booking = {
        "id": "3",
        "kto_soll": "9999",
        "kto_haben": "7",
        "anz_anteil": "2",
        "betrag_anteil": "100.0000",
        "datum": "2014-11-11 00:00:00",
        "Buchtext": " Beitritt ",
    }
    data = load_legacy(write_legacy(tmp_path, [person_row()], bookings=[booking]))

    (b,) = data.bookings
    assert (b.id, b.debit, b.credit, b.shares, b.amount) == (3, 9999, 7, 2, 10000)
    assert (b.day, b.text) == (date(2014, 11, 11), "Beitritt")


def test_corrections_apply_to_current_state_and_history(tmp_path):
    current = person_row(Geschlecht="w", Austritt="2026-05-18 00:00:00")
    old = person_row(Geschlecht="w", last_update="1900-01-01 00:00:00")
    corrections = {7: {"geschlecht": "m", "eintritt": "2026-05-18", "austritt": ""}}

    data = load_legacy(write_legacy(tmp_path, [current], history=[old]), corrections)

    person = data.people[7]
    assert (person.gender, person.entry, person.exit) == ("m", date(2026, 5, 18), None)
    assert data.history[7][0].gender == "m"


def test_load_decisions(tmp_path):
    path = tmp_path / "migration.toml"
    path.write_text(
        """
skip_persons = [501, 502]
rejected = [503]

[skip_bookings]
901 = "Testbuchung"

[corrections.505]
geschlecht = "m"
""",
        encoding="utf-8",
    )

    decisions = load_decisions(path)

    assert decisions.skip_persons == {501, 502}
    assert decisions.rejected == {503}
    assert decisions.skip_bookings == {901: "Testbuchung"}
    assert decisions.corrections == {505: {"geschlecht": "m"}}


def test_load_decisions_empty_file(tmp_path):
    path = tmp_path / "migration.toml"
    path.write_text("", encoding="utf-8")

    decisions = load_decisions(path)

    assert (decisions.skip_persons, decisions.rejected) == (frozenset(), frozenset())
    assert (decisions.skip_bookings, decisions.corrections) == ({}, {})
