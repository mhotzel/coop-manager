"""Ein- und Ausgabe der Mitglieder-API.

Für Name, Anschrift und Kontakt dienen die Dataclasses aus `values.py` direkt als Feldtypen:
Pydantic prüft dann Typen und Pflichtfelder, die fachlichen Regeln (Längen, Postleitzahl usw.)
prüft wie immer das Aggregat.
"""

from datetime import date

from pydantic import BaseModel, Field

from .addressing import address_lines, address_warnings, salutation
from .domain import Member
from .values import Address, Contact, PersonName

MemberId = Field(max_length=100)


class SearchRequest(BaseModel):
    """Abfrage: Suche per POST, damit die Namen nicht im Access-Log stehen."""

    query: str = Field(max_length=200)


class MemberDetail(BaseModel):
    """Die Detailansicht: gespeicherte Daten und daraus berechnete Angaben."""

    id: str
    member_number: int
    person_type: str
    name: PersonName
    address: Address
    contact: Contact
    address_lines: list[str]
    salutation_override: str  # abweichende Briefanrede, leer = erzeugt
    no_mail: bool
    notes: str
    application_date: date
    shares_subscribed: int
    admission_date: date | None
    rejection_date: date | None  # Ablehnung oder Rücknahme
    withdrawn: bool  # True: Rücknahme durch die Person
    payment_date: date | None  # Geldeingang: gezeichnete Anteile voll eingezahlt
    # Berechnet, nicht gespeichert:
    status: str | None  # zum Tag der Abfrage
    entry_date: date | None  # Eintrittsdatum: das spätere von Zulassung und Geldeingang
    salutation: str  # die Briefanrede, wie sie in den Seriendruck kommt
    generated_address_lines: list[str]
    warnings: list[str]

    @classmethod
    def from_member(cls, member: Member, today: date) -> MemberDetail:
        """Baut die Detailansicht aus dem Aggregat und berechnet Status, Anrede und Warnungen."""
        assert member.application_date is not None  # gesetzt durch member.applied
        generated = address_lines(member.person_type, member.name, member.address)
        return cls(
            id=member.subject,
            member_number=member.member_number,
            person_type=member.person_type,
            name=member.name,
            address=member.address,
            contact=member.contact,
            address_lines=list(member.address_lines),
            salutation_override=member.salutation,
            no_mail=member.no_mail,
            notes=member.notes,
            application_date=member.application_date,
            shares_subscribed=member.shares_subscribed,
            admission_date=member.admission_date,
            rejection_date=member.rejection_date,
            withdrawn=member.withdrawn,
            payment_date=member.payment_date,
            status=member.status(today),
            entry_date=member.entry_date(),
            salutation=salutation(member.person_type, member.name, member.salutation),
            generated_address_lines=list(generated),
            warnings=address_warnings(member.address_lines, generated),
        )


# --- Befehle: je einer pro fachlicher Aktion, alle Daten im Body ---


class ApplyForMembership(BaseModel):
    """Befehl: Beitrittserklärung erfassen; die Mitgliedsnummer vergibt das System."""

    person_type: str = Field(max_length=50)
    name: PersonName
    address: Address
    contact: Contact = Contact()
    application_date: date
    shares_subscribed: int


class MemberCommand(BaseModel):
    """Grundform aller Befehle an ein bestehendes Mitglied."""

    member_id: str = MemberId


class Decision(MemberCommand):
    """Befehl: Zulassung oder Ablehnung durch den Vorstand, mit Beschlussdatum."""

    decision_date: date


class Withdraw(MemberCommand):
    """Befehl: Die Person nimmt ihren Antrag zurück."""

    withdrawal_date: date


class ChangeName(MemberCommand):
    """Befehl: Name ändern."""

    name: PersonName


class ChangeAddress(MemberCommand):
    """Befehl: Anschrift ändern."""

    address: Address


class ChangeContact(MemberCommand):
    """Befehl: Telefon und E-Mail ändern."""

    contact: Contact


class ChangeAddressLines(MemberCommand):
    """Befehl: die sechs Adresszeilen setzen."""

    address_lines: list[str] = Field(max_length=10)


class ChangeSalutation(MemberCommand):
    """Befehl: abweichende Briefanrede setzen; leer = wieder erzeugen."""

    salutation: str = Field(max_length=500)


class ChangeMailPreference(MemberCommand):
    """Befehl: „keine Post“ setzen oder aufheben."""

    no_mail: bool


class ChangeNotes(MemberCommand):
    """Befehl: Hinweise ändern."""

    notes: str = Field(max_length=10000)
