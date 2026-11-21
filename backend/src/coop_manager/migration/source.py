"""Liest die Altdaten (CSV aus `mdb-export`) und die Einzelfälle (`migration.toml`).

Die CSV-Dateien entstehen so, je Tabelle `mitglieder`, `mitglieder_hist` und `buchungen`:

    mdb-export -T '%Y-%m-%d %H:%M:%S' DLS-MitgliederDB.accdb mitglieder > mitglieder.csv

Ohne `-T` kämen Datumswerte im US-Format. Hier wird nur eingelesen und umgewandelt; was mit den
Daten geschieht, entscheidet `plan.py`.
"""

import csv
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Datumswert 0 in Access; im Altsystem steht er für „kein Datum“.
ACCESS_ZERO_DATE = date(1899, 12, 30)


@dataclass(frozen=True)
class Decisions:
    """Die Einzelfälle aus `migration.toml` (siehe Plan)."""

    skip_persons: frozenset[int] = frozenset()  # nicht übernehmen
    rejected: frozenset[int] = frozenset()  # als „abgelehnt“ (Rücknahme) übernehmen
    skip_bookings: dict[int, str] = field(default_factory=dict)  # Buchungs-ID → Grund
    corrections: dict[int, dict[str, str]] = field(default_factory=dict)  # Nummer → Spalte → neuer Wert


@dataclass(frozen=True)
class LegacyPerson:
    """Eine Zeile aus `mitglieder` (aktueller Stand) oder `mitglieder_hist` (eine Version).

    Nur die Spalten, die die Migration braucht; Text ist ohne Leerraum am Rand.
    """

    number: int  # persnr
    company: str  # firma
    gender: str  # geschlecht
    last_name: str  # name
    first_names: str  # vorname
    title: str  # titel
    country: str  # land
    postal_code: str  # plz
    city: str  # ort
    street: str  # strasse
    house_number: str  # hausnr
    phone: str  # telefon1
    email: str
    salutation: str  # briefanrede
    address_lines: tuple[str, ...]  # adrzeile1 bis adrzeile6
    entry: date | None  # eintritt
    notice: date | None  # kündigung
    exit: date | None  # austritt
    death: date | None  # verstorben
    no_mail: bool  # keinepost
    notes: str  # hinweise
    last_update: datetime | None = None  # nur in der Historie


@dataclass(frozen=True)
class LegacyBooking:
    """Eine Zeile aus `buchungen`: Betrag und Anteile gehen vom Soll- auf das Habenkonto."""

    id: int
    debit: int  # kto_soll
    credit: int  # kto_haben
    shares: int  # anz_anteil
    amount: int  # betrag_anteil in Cent
    day: date  # datum
    text: str  # buchtext


@dataclass(frozen=True)
class LegacyData:
    """Alle Altdaten; die Historie je Person nach `last_update` sortiert."""

    people: dict[int, LegacyPerson]
    history: dict[int, list[LegacyPerson]]
    bookings: list[LegacyBooking]


def load_decisions(path: Path) -> Decisions:
    """Liest `migration.toml`; Nummern stehen in TOML als Schlüssel immer als Text."""
    with path.open("rb") as file:
        raw = tomllib.load(file)
    return Decisions(
        skip_persons=frozenset(raw.get("skip_persons", [])),
        rejected=frozenset(raw.get("rejected", [])),
        skip_bookings={int(key): reason for key, reason in raw.get("skip_bookings", {}).items()},
        corrections={int(key): dict(values) for key, values in raw.get("corrections", {}).items()},
    )


def load_legacy(csv_dir: Path, corrections: dict[int, dict[str, str]] | None = None) -> LegacyData:
    """Liest die drei CSV-Dateien.

    Korrekturen überschreiben Spalten (Namen klein geschrieben wie im Export), und zwar im
    aktuellen Stand und in allen Versionen der Historie, damit sie dort nicht als Änderung
    erscheinen.
    """
    corrections = corrections or {}

    def person(row: dict[str, str]) -> LegacyPerson:
        row = row | corrections.get(int(row["persnr"]), {})
        return _person(row)

    people = {p.number: p for p in map(person, read_csv(csv_dir / "mitglieder.csv"))}
    history: dict[int, list[LegacyPerson]] = {}
    for version in map(person, read_csv(csv_dir / "mitglieder_hist.csv")):
        history.setdefault(version.number, []).append(version)
    for versions in history.values():
        versions.sort(key=lambda v: v.last_update or datetime.min)
    bookings = [_booking(row) for row in read_csv(csv_dir / "buchungen.csv")]
    return LegacyData(people, history, bookings)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Liest eine CSV-Datei aus `mdb-export`; Spaltennamen klein geschrieben."""
    with path.open(encoding="utf-8", newline="") as file:
        return [{key.lower(): value for key, value in row.items()} for row in csv.DictReader(file)]


def _person(row: dict[str, str]) -> LegacyPerson:
    text = {key: value.strip() for key, value in row.items()}
    return LegacyPerson(
        number=int(text["persnr"]),
        company=text["firma"],
        gender=text["geschlecht"],
        last_name=text["name"],
        first_names=text["vorname"],
        title=text["titel"],
        country=text["land"],
        postal_code=text["plz"],
        city=text["ort"],
        street=text["strasse"],
        house_number=text["hausnr"],
        phone=text["telefon1"],
        email=text["email"],
        salutation=text["briefanrede"],
        address_lines=tuple(text[f"adrzeile{i}"] for i in range(1, 7)),
        entry=_date(text["eintritt"]),
        notice=_date(text["kündigung"]),
        exit=_date(text["austritt"]),
        death=_date(text["verstorben"]),
        no_mail=text["keinepost"] == "1",
        notes=text["hinweise"],
        last_update=_timestamp(text["last_update"]) if "last_update" in text else None,
    )


def _booking(row: dict[str, str]) -> LegacyBooking:
    day = _date(row["datum"])
    if day is None:
        raise ValueError(f"Buchung {row['id']} hat kein Datum.")
    return LegacyBooking(
        id=int(row["id"]),
        debit=int(row["kto_soll"]),
        credit=int(row["kto_haben"]),
        shares=int(row["anz_anteil"]),
        amount=int(Decimal(row["betrag_anteil"] or "0") * 100),
        day=day,
        text=row["buchtext"].strip(),
    )


def _timestamp(value: str) -> datetime | None:
    """Zeitstempel aus `mdb-export -T` („2014-11-01 00:00:00“) oder Datum aus einer Korrektur
    („2026-05-18“); leer bleibt leer."""
    return datetime.fromisoformat(value) if value else None


def _date(value: str) -> date | None:
    """Nur der Tag; leer und der Access-Nullwert 1899-12-30 werden zu None."""
    stamp = _timestamp(value.strip())
    if stamp is None or stamp.date() == ACCESS_ZERO_DATE:
        return None
    return stamp.date()
