"""Migration von den CSV-Dateien bis in den Event Store: `run`, `check` und `coop-manager migrate`.

Alle Daten sind erfunden (siehe AGENTS.md).
"""

import csv
import sys
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from coop_manager import cli
from coop_manager.accounts.services import get_ledger, open_cooperative_account
from coop_manager.app import PROJECTORS, SCHEMAS
from coop_manager.core import DomainError
from coop_manager.db import Database, prepare
from coop_manager.members import services
from coop_manager.members.projections import search_members
from coop_manager.members.status import EXITED, MEMBER, REJECTED
from coop_manager.migration import check, run
from coop_manager.migration.plan import make_plan
from coop_manager.migration.source import Decisions, LegacyData, load_decisions, load_legacy

TODAY = date(2026, 11, 30)
PERSON_COLUMNS = [
    "PersNr", "Firma", "Geschlecht", "Name", "Vorname", "Titel", "Land", "PLZ", "Ort", "Strasse",
    "HausNr", "Telefon1", "eMail", "BriefAnrede", "AdrZeile1", "AdrZeile2", "AdrZeile3", "AdrZeile4",
    "AdrZeile5", "AdrZeile6", "Eintritt", "Kündigung", "Austritt", "Verstorben", "KeinePost", "hinweise",
]  # fmt: skip
BOOKING_COLUMNS = ["id", "kto_soll", "kto_haben", "anz_anteil", "betrag_anteil", "datum", "Buchtext"]
DECISIONS = """
skip_persons = [12]
rejected = [11]

[skip_bookings]
4 = "Notiz: Einzahlung als Spende vereinnahmt"
7 = "Testbuchung"
"""


def person(number: int, first: str, entry: str = "2014-11-01", **values: str) -> dict[str, str]:
    row = dict.fromkeys(PERSON_COLUMNS, "")
    row |= {
        "PersNr": str(number),
        "Geschlecht": "w",
        "Name": "Muster",
        "Vorname": first,
        "PLZ": "12345",
        "Ort": "Musterstadt",
        "Strasse": "Hauptstraße",
        "HausNr": str(number),
        "AdrZeile1": "Frau",
        "AdrZeile2": f"{first} Muster",
        "AdrZeile3": f"Hauptstraße {number}",
        "AdrZeile4": "12345 Musterstadt",
        "Eintritt": f"{entry} 00:00:00" if entry else "",
        "KeinePost": "0",
    }
    return row | values


def booking(id: int, debit: int, credit: int, shares: int, day: str, text: str = "Beitritt") -> dict[str, str]:
    values = [str(id), str(debit), str(credit), str(shares), f"{shares * 50}.0000", f"{day} 00:00:00", text]
    return dict(zip(BOOKING_COLUMNS, values, strict=True))


PEOPLE = [
    person(7, "Erika", Ort="Musterstadt"),
    person(8, "Max", Verstorben="2020-01-01 00:00:00"),
    person(9, "Moritz", entry="2021-09-07"),
    person(10, "", entry="2015-01-10", Firma="Musterverein e.V.", Name="", AdrZeile1="Musterverein e.V."),
    person(11, "Lisa", entry=""),  # nie Mitglied geworden: „abgelehnt“
    person(12, "Kurt", entry=""),  # nur Kontakt: nicht übernehmen
    person(9999, "", entry="", Firma="Genossenschaft", Name=""),
]
HISTORY = [
    person(7, "Erika", Ort="Altdorf", AdrZeile4="12345 Altdorf", last_update="1900-01-01 00:00:00"),
    person(7, "Erika", last_update="2024-06-30 14:12:00"),
]
BOOKINGS = [
    booking(1, 9999, 7, 2, "2014-11-11"),
    booking(2, 9999, 8, 3, "2014-11-11"),
    booking(3, 9999, 10, 1, "2015-01-10"),
    booking(4, 11, 11, 1, "2014-11-09", "Spende 50 EUR"),
    booking(5, 8, 9, 3, "2021-09-07", "Umbuchung Erbe"),
    booking(6, 10, 9999, 1, "2023-07-03", "Austritt / Spende"),
    booking(7, 9999, 9999, 1, "2025-06-24", "Testbuchung"),
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def legacy_dir(tmp_path) -> Path:
    """Ordner mit den drei CSV-Dateien und `migration.toml`, wie aus `mdb-export`."""
    folder = tmp_path / "altdaten"
    folder.mkdir()
    write_csv(folder / "mitglieder.csv", PERSON_COLUMNS, PEOPLE)
    write_csv(folder / "mitglieder_hist.csv", [*PERSON_COLUMNS, "last_update"], HISTORY)
    write_csv(folder / "buchungen.csv", BOOKING_COLUMNS, BOOKINGS)
    (folder / "migration.toml").write_text(DECISIONS, encoding="utf-8")
    return folder


@pytest.fixture
def data_dir(tmp_path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def db(data_dir) -> Iterator[Database]:
    """Datenverzeichnis wie nach der Ersteinrichtung: nur das Genossenschaftskonto."""
    prepare(data_dir, PROJECTORS, SCHEMAS)
    db = Database(data_dir, PROJECTORS)
    open_cooperative_account(db, "Genossenschaft", actor="cli")
    yield db
    db.close()


def load(legacy_dir: Path) -> tuple[LegacyData, Decisions]:
    decisions = load_decisions(legacy_dir / "migration.toml")
    return load_legacy(legacy_dir, decisions.corrections), decisions


def build(db: Database, legacy_dir: Path) -> run.Built:
    legacy, decisions = load(legacy_dir)
    plan = make_plan(legacy, decisions)
    assert plan.problems == []
    return run.build(db, plan, TODAY)


def event_count(db: Database) -> int:
    return len(list(db.store.read_all()))


def test_build_and_save_writes_members_accounts_and_bookings(db, legacy_dir):
    built = build(db, legacy_dir)
    assert built.errors == []
    before = event_count(db)

    count = run.save(db, built)

    events = list(db.store.read_all())
    assert len(events) == before + count
    assert {event.actor for _, event in events[before:]} == {"migration"}
    members = {m.member_number: m for m in services.all_members(db)}
    assert sorted(members) == [7, 8, 9, 10, 11]  # 12 übersprungen
    status = {number: m.status(TODAY) for number, m in members.items()}
    assert status == {7: MEMBER, 8: EXITED, 9: MEMBER, 10: EXITED, 11: REJECTED}
    ledger = get_ledger(db)
    account = ledger.account_of(members[7].subject)
    assert account is not None and account.number == 7  # Kontonummer = Mitgliedsnummer
    assert [(ledger.balance(n), ledger.shares(n)) for n in (7, 8, 9, 10, 9999)] == [
        (10000, 2),
        (0, 0),
        (15000, 3),
        (0, 0),
        (-25000, -5),
    ]
    assert [row.member_number for row in search_members(db.projections.conn, "musterverein", TODAY)] == [10]


def test_history_and_notes_are_migrated(db, legacy_dir):
    run.save(db, build(db, legacy_dir))
    members = {m.member_number: m for m in services.all_members(db)}

    erika = db.store.read_stream(members[7].subject)
    moved = [e for e in erika if e.type == "member.address-changed"]
    assert [e.data["valid_from"] for e in moved] == ["2024-06-30"]
    assert members[7].address.city == "Musterstadt"
    assert members[11].notes == "Altsystem 2014-11-09: Spende 50 EUR (50,00 €, 1 Anteile)"


def test_build_alone_writes_nothing(db, legacy_dir):
    before = event_count(db)

    built = build(db, legacy_dir)

    assert built.event_count() > 0
    assert event_count(db) == before


def test_build_refuses_when_members_exist(db, legacy_dir):
    run.save(db, build(db, legacy_dir))

    with pytest.raises(DomainError, match="schon Mitglieder"):
        build(db, legacy_dir)


def test_build_refuses_without_cooperative_account(tmp_path, legacy_dir):
    prepare(tmp_path / "leer", PROJECTORS, SCHEMAS)
    db = Database(tmp_path / "leer", PROJECTORS)
    try:
        with pytest.raises(DomainError, match="Genossenschaftskonto fehlt"):
            build(db, legacy_dir)
    finally:
        db.close()


def test_error_in_member_method_is_reported_with_context(db, legacy_dir):
    people = [person(7, "Erika", Telefon1="ruf mal an"), *PEOPLE[1:]]
    write_csv(legacy_dir / "mitglieder.csv", PERSON_COLUMNS, people)

    built = build(db, legacy_dir)

    assert built.errors == ["Person 7: Die Telefonnummer darf nur Ziffern, Leerzeichen und + ( ) / - enthalten."]


def test_compare_finds_no_difference(db, legacy_dir):
    legacy, _ = load(legacy_dir)

    assert check.compare(legacy, build(db, legacy_dir).ledger) == []


def test_compare_finds_difference(db, legacy_dir):
    built = build(db, legacy_dir)
    write_csv(legacy_dir / "buchungen.csv", BOOKING_COLUMNS, [*BOOKINGS, booking(8, 9999, 7, 1, "2016-01-01")])
    legacy, _ = load(legacy_dir)

    assert check.compare(legacy, built.ledger) == [
        "Konto 7: alt 150,00 € / 3 Anteile, neu 100,00 € / 2 Anteile",
        "Konto 9999: alt -300,00 € / -6 Anteile, neu -250,00 € / -5 Anteile",
    ]


def run_migrate(monkeypatch, data_dir: Path, legacy_dir: Path, *options: str) -> None:
    monkeypatch.setenv("CM_DATA_DIR", str(data_dir))
    args = ["coop-manager", "migrate", str(legacy_dir), str(legacy_dir / "migration.toml"), *options]
    monkeypatch.setattr(sys, "argv", args)
    cli.main()


def test_cli_dry_run_reports_and_writes_nothing(monkeypatch, capsys, db, data_dir, legacy_dir):
    before = event_count(db)

    run_migrate(monkeypatch, data_dir, legacy_dir, "--dry-run")

    out = capsys.readouterr().out
    assert "Personen: 5 übernommen, 1 übersprungen" in out
    assert "Bestand: 5 Anteile, 250,00 €" in out
    assert "  7: Testbuchung" in out
    assert "Probelauf: nichts geschrieben." in out
    assert event_count(db) == before


def test_cli_saves(monkeypatch, capsys, db, data_dir, legacy_dir):
    run_migrate(monkeypatch, data_dir, legacy_dir)

    assert "Migration gespeichert:" in capsys.readouterr().out
    assert len(services.all_members(db)) == 5


def test_cli_stops_on_problems(monkeypatch, db, data_dir, legacy_dir):
    (legacy_dir / "migration.toml").write_text("skip_persons = [12]\n", encoding="utf-8")
    before = event_count(db)

    with pytest.raises(SystemExit, match="Probleme im Migrationsplan"):
        run_migrate(monkeypatch, data_dir, legacy_dir)
    assert event_count(db) == before
