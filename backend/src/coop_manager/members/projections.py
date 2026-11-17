import sqlite3
from dataclasses import dataclass
from datetime import date

from ..eventsource import Event, Projector, on
from .addressing import list_name
from .status import MembershipDates, status_on
from .values import PersonName


@dataclass(frozen=True, slots=True)
class MemberRow:
    """Ein Mitglied, wie es in Liste und Suche erscheint."""

    id: str
    member_number: int
    person_type: str
    list_name: str
    street: str
    postal_code: str
    city: str
    status: str | None  # zum Tag der Abfrage


class MemberList(Projector):
    """Alle erfassten Personen; Grundlage für Suche und Listen.

    `search_text` enthält die durchsuchbaren Angaben klein geschrieben (`casefold`). SQLite
    vergleicht bei LIKE nur ASCII-Buchstaben ohne Rücksicht auf Groß/klein, „Ü“ und „ü“ wären
    sonst verschieden.
    """

    schema = """
    CREATE TABLE IF NOT EXISTS members (
        member_id        TEXT PRIMARY KEY,
        member_number    INTEGER NOT NULL,
        person_type      TEXT NOT NULL,
        company_name     TEXT NOT NULL,
        title            TEXT NOT NULL,
        first_names      TEXT NOT NULL,
        last_name        TEXT NOT NULL,
        gender           TEXT NOT NULL,
        street           TEXT NOT NULL,
        house_number     TEXT NOT NULL,
        postal_code      TEXT NOT NULL,
        city             TEXT NOT NULL,
        application_date TEXT NOT NULL,
        admission_date   TEXT,
        rejection_date   TEXT,
        payment_date     TEXT,
        search_text      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_members_number ON members (member_number);
    """
    tables = ("members",)

    @on("member.applied")
    def _applied(self, conn: sqlite3.Connection, event: Event) -> None:
        name, address = event.data["name"], event.data["address"]
        conn.execute(
            "INSERT INTO members (member_id, member_number, person_type, company_name, title, first_names,"
            " last_name, gender, street, house_number, postal_code, city, application_date, search_text)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')",
            (
                event.subject,
                event.data["member_number"],
                event.data["person_type"],
                name["company_name"],
                name["title"],
                name["first_names"],
                name["last_name"],
                name["gender"],
                address["street"],
                address["house_number"],
                address["postal_code"],
                address["city"],
                event.data["application_date"],
            ),
        )
        _refresh_search_text(conn, event.subject)

    @on("member.name-changed")
    def _name_changed(self, conn: sqlite3.Connection, event: Event) -> None:
        name = event.data["name"]
        conn.execute(
            "UPDATE members SET company_name = ?, title = ?, first_names = ?, last_name = ?, gender = ?"
            " WHERE member_id = ?",
            (
                name["company_name"],
                name["title"],
                name["first_names"],
                name["last_name"],
                name["gender"],
                event.subject,
            ),
        )
        _refresh_search_text(conn, event.subject)

    @on("member.address-changed")
    def _address_changed(self, conn: sqlite3.Connection, event: Event) -> None:
        address = event.data["address"]
        conn.execute(
            "UPDATE members SET street = ?, house_number = ?, postal_code = ?, city = ? WHERE member_id = ?",
            (address["street"], address["house_number"], address["postal_code"], address["city"], event.subject),
        )
        _refresh_search_text(conn, event.subject)

    @on("member.admitted")
    def _admitted(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute(
            "UPDATE members SET admission_date = ? WHERE member_id = ?", (event.data["decision_date"], event.subject)
        )

    @on("member.rejected")
    def _rejected(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute(
            "UPDATE members SET rejection_date = ? WHERE member_id = ?", (event.data["decision_date"], event.subject)
        )

    @on("member.withdrawn")
    def _withdrawn(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute(
            "UPDATE members SET rejection_date = ? WHERE member_id = ?", (event.data["withdrawal_date"], event.subject)
        )

    @on("member.paid-in")
    def _paid_in(self, conn: sqlite3.Connection, event: Event) -> None:
        conn.execute(
            "UPDATE members SET payment_date = ? WHERE member_id = ?", (event.data["payment_date"], event.subject)
        )


def _refresh_search_text(conn: sqlite3.Connection, member_id: str) -> None:
    """Setzt `search_text` aus den aktuellen Spalten neu zusammen."""
    row = conn.execute("SELECT * FROM members WHERE member_id = ?", (member_id,)).fetchone()
    parts = [
        row["company_name"],
        row["title"],
        row["first_names"],
        row["last_name"],
        row["street"],
        row["postal_code"],
        row["city"],
    ]
    text = " ".join(part for part in parts if part).casefold()
    conn.execute("UPDATE members SET search_text = ? WHERE member_id = ?", (text, member_id))


def search_members(conn: sqlite3.Connection, query: str, today: date, limit: int = 50) -> list[MemberRow]:
    """Mitglieder, auf die jedes Suchwort passt (z. B. „muster haupt“), nach Nummer sortiert.

    Ein Wort nur aus Ziffern trifft die Mitgliedsnummer genau oder den Anfang der Postleitzahl
    („42“ findet Mitglied 42, nicht jede PLZ mit einer 42 darin). Alle anderen Wörter dürfen
    irgendwo in Namen, Firma, Straße oder Ort stehen. Eine leere Suche liefert die ersten
    `limit` Mitglieder.
    """
    conditions: list[str] = []
    params: list[str | int] = []
    for word in query.casefold().split():
        if word.isdigit():
            conditions.append("(member_number = ? OR postal_code LIKE ?)")
            params += [int(word), f"{word}%"]
        else:
            # % und _ haben in LIKE eine Sonderbedeutung und werden deshalb maskiert.
            conditions.append("search_text LIKE ? ESCAPE '\\'")
            params.append(f"%{_escape_like(word)}%")
    where = " AND ".join(conditions) or "1 = 1"
    rows = conn.execute(f"SELECT * FROM members WHERE {where} ORDER BY member_number LIMIT ?", (*params, limit))
    return [_to_row(row, today) for row in rows]


def _escape_like(word: str) -> str:
    """Maskiert die Platzhalter von LIKE, damit sie als normale Zeichen gesucht werden."""
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _to_row(row: sqlite3.Row, today: date) -> MemberRow:
    """Macht aus einer Tabellenzeile eine `MemberRow` mit dem Status von heute."""
    name = PersonName(
        company_name=row["company_name"],
        title=row["title"],
        first_names=row["first_names"],
        last_name=row["last_name"],
        gender=row["gender"],
    )
    dates = MembershipDates(
        application_date=date.fromisoformat(row["application_date"]),
        admission_date=date.fromisoformat(row["admission_date"]) if row["admission_date"] else None,
        rejection_date=date.fromisoformat(row["rejection_date"]) if row["rejection_date"] else None,
        payment_date=date.fromisoformat(row["payment_date"]) if row["payment_date"] else None,
    )
    return MemberRow(
        id=row["member_id"],
        member_number=row["member_number"],
        person_type=row["person_type"],
        list_name=list_name(row["person_type"], name),
        street=" ".join(part for part in (row["street"], row["house_number"]) if part),
        postal_code=row["postal_code"],
        city=row["city"],
        status=status_on(dates, today),
    )
