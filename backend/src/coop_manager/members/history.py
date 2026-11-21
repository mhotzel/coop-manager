"""Verlauf der Personendaten eines Mitglieds, aus seinen Events (siehe Plan: Verlauf, Schritt 11).

Keine eigene Projektion: Der Verlauf entsteht beim Abruf, indem die Events der Person der Reihe
nach durchgegangen werden. Bei einigen Dutzend Events je Person ist das schnell genug.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ..core import NotFoundError
from ..db import Database
from ..users.projections import get_user
from .addressing import list_name
from .values import GENDERS, LEGAL_ENTITY, Address, PersonName, is_germany

# Eventtyp → (Teil der Personendaten, Feld im Event). `member.applied` enthält die ersten vier.
PARTS = {
    "member.name-changed": ("Name", "name"),
    "member.address-changed": ("Anschrift", "address"),
    "member.contact-changed": ("Kontakt", "contact"),
    "member.address-lines-changed": ("Adresszeilen", "address_lines"),
    "member.salutation-changed": ("Briefanrede", "salutation"),
    "member.mail-preference-changed": ("Keine Post", "no_mail"),
    "member.notes-changed": ("Hinweise", "notes"),
}
# Wie die Teile vor der ersten Änderung aussehen, die `member.applied` nicht enthält.
INITIAL = {"Briefanrede": "(erzeugt)", "Keine Post": "nein", "Hinweise": ""}
# Akteure ohne Benutzerkonto (siehe Plan: Auslöser jedes Events).
ACTOR_NAMES = {"migration": "Migration", "cli": "Kommandozeile"}


@dataclass(frozen=True)
class HistoryEntry:
    """Eine Änderung an einem Teil der Personendaten; Vorher und Nachher als lesbarer Text."""

    recorded_at: datetime  # wann gespeichert (Zeit des Events, UTC)
    valid_from: date | None  # ab wann gültig: Antragsdatum, aus dem Altsystem; None = ab Speichern
    actor: str  # wer gespeichert hat, als Name
    part: str  # z. B. „Anschrift“
    before: str
    after: str


def member_history(db: Database, member_id: str) -> list[HistoryEntry]:
    """Alle Änderungen an den Personendaten, die neueste zuerst; zuunterst der Stand beim Antrag."""
    events = db.store.read_stream(member_id)
    if not events or events[0].type != "member.applied":
        raise NotFoundError("Das Mitglied wurde nicht gefunden.")
    person_type = events[0].data["person_type"]
    actors: dict[str | None, str] = {}  # schon nachgeschlagene Namen
    current = dict(INITIAL)  # Teil → Text des aktuellen Stands
    entries: list[HistoryEntry] = []
    for event in events:
        if event.type == "member.applied":
            changes = [(part, key) for part, key in PARTS.values() if key in event.data]
            valid_from: date | None = date.fromisoformat(event.data["application_date"])
        elif event.type in PARTS:
            changes = [PARTS[event.type]]
            raw = event.data.get("valid_from")  # nur bei der Historie aus dem Altsystem
            valid_from = date.fromisoformat(raw) if raw else None
        else:
            continue  # Status, Kündigung usw. gehören nicht zu den Personendaten
        if event.actor not in actors:
            actors[event.actor] = _actor_name(db, event.actor)
        for part, key in changes:
            text = _text(key, event.data[key], person_type)
            entries.append(HistoryEntry(event.time, valid_from, actors[event.actor], part, current.get(part, ""), text))
            current[part] = text
    return entries[::-1]  # [::-1]: umgekehrte Reihenfolge, die neueste Änderung zuerst


def _actor_name(db: Database, actor: str | None) -> str:
    """Name des Benutzers; feste Namen für Migration und Kommandozeile."""
    if actor is None:
        return "unbekannt"
    if actor in ACTOR_NAMES:
        return ACTOR_NAMES[actor]
    user = get_user(db.projections.conn, actor)
    return user.full_name if user else "gelöschter Benutzer"


def _text(key: str, value: Any, person_type: str) -> str:
    """Ein Teil der Personendaten als lesbarer Text, so wie er im Event steht."""
    if key == "name":
        name = PersonName(**value)
        text = list_name(person_type, name)
        if person_type == LEGAL_ENTITY:
            contact = " ".join(p for p in (name.title, name.first_names, name.last_name) if p)
            text += f", Ansprechpartner {contact}" if contact else ""
        elif name.title:
            text += f", {name.title}"
        return text + (f" ({GENDERS[name.gender]})" if name.gender else "")
    if key == "address":
        address = Address(**value)
        text = f"{address.street} {address.house_number}, {address.postal_code} {address.city}".strip(" ,")
        return text if is_germany(address.country) else f"{text}, {address.country}"
    if key == "contact":
        parts = []
        if value["phone"]:
            parts.append(f"Telefon {value['phone']}")
        if value["email"]:
            parts.append(f"E-Mail {value['email']}")
        return "; ".join(parts)
    if key == "address_lines":
        return " / ".join(line for line in value if line)
    if key == "salutation":
        return value or "(erzeugt)"
    if key == "no_mail":
        return "ja" if value else "nein"
    return value  # Hinweise
