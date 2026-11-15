import unicodedata
import uuid
from dataclasses import asdict
from datetime import date
from typing import Self

from ..core import DomainError
from ..eventsource import Aggregate, Event, on
from .addressing import address_lines
from .values import (
    ADDRESS_LINE_COUNT,
    Address,
    Contact,
    PersonName,
    clean,
    clean_address_lines,
    validate_address,
    validate_contact,
    validate_name,
    validate_person_type,
)


class Member(Aggregate):
    """Eine Person von der Beitrittserklärung an; ob sie Mitglied ist, ergibt sich aus Fakten.

    Die Mitgliedsnummer vergibt der Service vor dem Anlegen (siehe Plan: MemberNumbers).
    """

    def __init__(self, subject: str) -> None:
        """Leeres Mitglied ohne Events; den Zustand setzen erst die Events."""
        super().__init__(subject)
        self.member_number = 0
        self.person_type = ""
        self.name = PersonName()
        self.address = Address("", "", "", "")
        self.contact = Contact()
        self.address_lines: tuple[str, ...] = ("",) * ADDRESS_LINE_COUNT
        self.salutation = ""  # abweichende Briefanrede, leer = erzeugen
        self.no_mail = False
        self.notes = ""
        self.application_date: date | None = None
        self.shares_subscribed = 0

    @classmethod
    def apply(
        cls,
        member_number: int,
        person_type: str,
        name: PersonName,
        address: Address,
        application_date: date,
        shares_subscribed: int,
        contact: Contact | None = None,
    ) -> Self:
        """Erfasst die Beitrittserklärung („Antrag“). Die Adresszeilen werden dabei erzeugt."""
        name, address = name.cleaned(), address.cleaned()
        contact = (contact or Contact()).cleaned()
        validate_person_type(person_type)
        validate_name(person_type, name)
        validate_address(address)
        validate_contact(contact)
        if member_number < 1:
            raise DomainError("Die Mitgliedsnummer muss positiv sein.")
        if shares_subscribed < 1:
            raise DomainError("Es muss mindestens ein Anteil gezeichnet werden.")
        member = cls(f"member-{uuid.uuid7()}")
        member._record(
            "member.applied",
            member_number=member_number,
            person_type=person_type,
            name=asdict(name),
            address=asdict(address),
            contact=asdict(contact),
            address_lines=list(address_lines(person_type, name, address)),
            application_date=application_date.isoformat(),
            shares_subscribed=shares_subscribed,
        )
        return member

    def change_name(self, name: PersonName) -> None:
        """Ändert den Namen (z. B. nach Heirat); die Adresszeilen bleiben, wie sie sind."""
        name = name.cleaned()
        validate_name(self.person_type, name)
        if name != self.name:
            self._record("member.name-changed", name=asdict(name))

    def change_address(self, address: Address) -> None:
        """Ändert die Anschrift (z. B. nach Umzug); die Adresszeilen bleiben, wie sie sind."""
        address = address.cleaned()
        validate_address(address)
        if address != self.address:
            self._record("member.address-changed", address=asdict(address))

    def change_contact(self, contact: Contact) -> None:
        """Ändert Telefon und E-Mail."""
        contact = contact.cleaned()
        validate_contact(contact)
        if contact != self.contact:
            self._record("member.contact-changed", contact=asdict(contact))

    def change_address_lines(self, lines: list[str] | tuple[str, ...]) -> None:
        """Setzt die sechs Adresszeilen, von Hand gepflegt oder neu erzeugt."""
        lines = clean_address_lines(lines)
        if lines != self.address_lines:
            self._record("member.address-lines-changed", address_lines=list(lines))

    def change_salutation(self, salutation: str) -> None:
        """Abweichende Briefanrede; leer = wieder aus den Personendaten erzeugen."""
        salutation = clean(salutation)
        if len(salutation) > 100:
            raise DomainError("Die Briefanrede hat höchstens 100 Zeichen.")
        if salutation != self.salutation:
            self._record("member.salutation-changed", salutation=salutation)

    def change_mail_preference(self, no_mail: bool) -> None:
        """Setzt „keine Post“: Das Mitglied bekommt keine Einladungen per Seriendruck."""
        if no_mail != self.no_mail:
            self._record("member.mail-preference-changed", no_mail=no_mail)

    def change_notes(self, notes: str) -> None:
        """Hinweise sind mehrzeilig; nur Leerraum am Anfang und Ende fällt weg."""
        notes = unicodedata.normalize("NFC", notes).strip()
        if len(notes) > 5000:
            raise DomainError("Die Hinweise haben höchstens 5000 Zeichen.")
        if notes != self.notes:
            self._record("member.notes-changed", notes=notes)

    @on("member.applied")
    def _applied(self, event: Event) -> None:
        self.member_number = event.data["member_number"]
        self.person_type = event.data["person_type"]
        self.name = PersonName(**event.data["name"])
        self.address = Address(**event.data["address"])
        self.contact = Contact(**event.data["contact"])
        self.address_lines = tuple(event.data["address_lines"])
        self.application_date = date.fromisoformat(event.data["application_date"])
        self.shares_subscribed = event.data["shares_subscribed"]

    @on("member.name-changed")
    def _name_changed(self, event: Event) -> None:
        self.name = PersonName(**event.data["name"])

    @on("member.address-changed")
    def _address_changed(self, event: Event) -> None:
        self.address = Address(**event.data["address"])

    @on("member.contact-changed")
    def _contact_changed(self, event: Event) -> None:
        self.contact = Contact(**event.data["contact"])

    @on("member.address-lines-changed")
    def _address_lines_changed(self, event: Event) -> None:
        self.address_lines = tuple(event.data["address_lines"])

    @on("member.salutation-changed")
    def _salutation_changed(self, event: Event) -> None:
        self.salutation = event.data["salutation"]

    @on("member.mail-preference-changed")
    def _mail_preference_changed(self, event: Event) -> None:
        self.no_mail = event.data["no_mail"]

    @on("member.notes-changed")
    def _notes_changed(self, event: Event) -> None:
        self.notes = event.data["notes"]
