"""Wertobjekte der Personendaten, ihre Konstanten und Prüfungen."""

import re
import unicodedata
from dataclasses import dataclass

from ..core import DomainError

NATURAL_PERSON = "natural_person"
LEGAL_ENTITY = "legal_entity"
PERSON_TYPES = {NATURAL_PERSON: "natürliche Person", LEGAL_ENTITY: "juristische Person"}

MALE = "m"
FEMALE = "w"
DIVERSE = "d"
GENDERS = {MALE: "männlich", FEMALE: "weiblich", DIVERSE: "divers", "": "keine Angabe"}

ADDRESS_LINE_COUNT = 6

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"[0-9+()/ -]*")
_GERMAN_POSTAL_CODE = re.compile(r"\d{5}")
_GERMANY = {"", "deutschland", "germany", "de"}


def clean(raw: str) -> str:
    """Einheitliche Unicode-Form (NFC) und einfache Leerzeichen, wie beim Benutzernamen."""
    return " ".join(unicodedata.normalize("NFC", raw).split())


def is_germany(country: str) -> bool:
    """Leeres Land heißt Deutschland."""
    return country.casefold() in _GERMANY


@dataclass(frozen=True)
class PersonName:
    """Name einer natürlichen Person bzw. Firma mit Ansprechpartner.

    Bei juristischen Personen beschreiben Titel, Vornamen, Nachname und Geschlecht den
    Ansprechpartner (alle optional).
    """

    company_name: str = ""
    title: str = ""
    first_names: str = ""
    last_name: str = ""
    gender: str = ""

    def cleaned(self) -> PersonName:
        """Dieselben Angaben bereinigt (siehe `clean`), das Geschlecht klein geschrieben."""
        return PersonName(
            company_name=clean(self.company_name),
            title=clean(self.title),
            first_names=clean(self.first_names),
            last_name=clean(self.last_name),
            gender=clean(self.gender).lower(),
        )


@dataclass(frozen=True)
class Address:
    """Postanschrift; Straße, Postleitzahl und Ort sind Pflicht."""

    street: str
    house_number: str
    postal_code: str
    city: str
    country: str = ""  # leer = Deutschland

    def cleaned(self) -> Address:
        """Dieselbe Anschrift bereinigt (siehe `clean`)."""
        return Address(
            street=clean(self.street),
            house_number=clean(self.house_number),
            postal_code=clean(self.postal_code),
            city=clean(self.city),
            country=clean(self.country),
        )


@dataclass(frozen=True)
class Contact:
    """Telefon und E-Mail, beide optional."""

    phone: str = ""
    email: str = ""

    def cleaned(self) -> Contact:
        """Dieselben Angaben bereinigt, die E-Mail-Adresse klein geschrieben."""
        return Contact(phone=clean(self.phone), email=clean(self.email).lower())


def validate_person_type(person_type: str) -> None:
    """Nur natürliche oder juristische Person."""
    if person_type not in PERSON_TYPES:
        raise DomainError(f"Die Art der Person '{person_type}' ist nicht zulässig.")


def validate_name(person_type: str, name: PersonName) -> None:
    """Prüft Geschlecht und Längen und die Pflichtfelder, die von der Art der Person abhängen."""
    if name.gender not in GENDERS:
        raise DomainError("Das Geschlecht muss m, w, d oder leer sein.")
    for label, value, limit in (
        ("Firmenname", name.company_name, 100),
        ("Titel", name.title, 30),
        ("Vornamen", name.first_names, 100),
        ("Nachname", name.last_name, 100),
    ):
        if len(value) > limit:
            raise DomainError(f"{label}: höchstens {limit} Zeichen.")
    if person_type == NATURAL_PERSON:
        if not (name.first_names and name.last_name):
            raise DomainError("Vornamen und Nachname sind Pflicht.")
        if name.company_name:
            raise DomainError("Eine natürliche Person hat keinen Firmennamen.")
    elif not name.company_name:
        raise DomainError("Der Firmenname ist Pflicht.")


def validate_address(address: Address, required: bool = True) -> None:
    """Prüft Pflichtfelder und Längen; eine deutsche Postleitzahl muss fünf Ziffern haben.

    `required=False` nur für die Migration: Dann dürfen Straße, Postleitzahl und Ort fehlen (siehe
    Plan). Was da ist, wird trotzdem geprüft.
    """
    if required and not (address.street and address.postal_code and address.city):
        raise DomainError("Straße, Postleitzahl und Ort sind Pflicht.")
    for label, value, limit in (
        ("Straße", address.street, 100),
        ("Hausnummer", address.house_number, 20),
        ("Postleitzahl", address.postal_code, 20),
        ("Ort", address.city, 100),
        ("Land", address.country, 50),
    ):
        if len(value) > limit:
            raise DomainError(f"{label}: höchstens {limit} Zeichen.")
    if address.postal_code and is_germany(address.country) and not _GERMAN_POSTAL_CODE.fullmatch(address.postal_code):
        raise DomainError("Eine deutsche Postleitzahl hat fünf Ziffern.")


def validate_contact(contact: Contact) -> None:
    """Telefonnummer nur aus erlaubten Zeichen, E-Mail-Adresse in der Form name@domain.tld."""
    if not _PHONE.fullmatch(contact.phone) or len(contact.phone) > 30:
        raise DomainError("Die Telefonnummer darf nur Ziffern, Leerzeichen und + ( ) / - enthalten.")
    if contact.email and (not _EMAIL.fullmatch(contact.email) or len(contact.email) > 100):
        raise DomainError("Die E-Mail-Adresse ist ungültig.")


def clean_address_lines(lines: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Genau sechs Zeilen; Leerzeichen am Rand fallen weg, Zeilenumbrüche sind nicht erlaubt."""
    if len(lines) != ADDRESS_LINE_COUNT:
        raise DomainError(f"Es müssen genau {ADDRESS_LINE_COUNT} Adresszeilen sein.")
    cleaned = tuple(clean(line) for line in lines)
    if any(len(line) > 100 for line in cleaned):
        raise DomainError("Eine Adresszeile hat höchstens 100 Zeichen.")
    return cleaned
