import unicodedata
import uuid
from dataclasses import asdict
from datetime import date
from typing import Self

from ..core import DomainError
from ..eventsource import Aggregate, Event, on
from .addressing import address_lines
from .status import MembershipDates, status_on
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
        self.admission_date: date | None = None
        self.rejection_date: date | None = None  # Ablehnung oder Rücknahme
        self.withdrawn = False  # True: Rücknahme durch die Person, nicht Ablehnung durch den Vorstand

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

    def status(self, day: date) -> str | None:
        """Der Status am Tag `day` (siehe status.py)."""
        assert self.application_date is not None  # gesetzt durch member.applied
        dates = MembershipDates(self.application_date, self.admission_date, self.rejection_date)
        return status_on(dates, day)

    def admit(self, decision_date: date, today: date) -> None:
        """Der Vorstand lässt zu (§ 15 GenG). Mitglied wird man erst mit dem Geldeingang (Schritt 5)."""
        self._ensure_open_application(decision_date, today)
        if self.admission_date is not None:
            raise DomainError("Der Antrag ist bereits zugelassen.")
        self._record("member.admitted", decision_date=decision_date.isoformat())

    def reject(self, decision_date: date, today: date) -> None:
        """Der Vorstand lehnt den Antrag ab; nach seiner eigenen Zulassung geht das nicht mehr."""
        self._ensure_open_application(decision_date, today)
        if self.admission_date is not None:
            raise DomainError("Ein zugelassener Antrag kann nicht mehr abgelehnt werden.")
        self._record("member.rejected", decision_date=decision_date.isoformat())

    def withdraw(self, withdrawal_date: date, today: date) -> None:
        """Die Person nimmt ihren Antrag zurück, auch nach der Zulassung, solange sie nicht Mitglied ist."""
        self._ensure_open_application(withdrawal_date, today)
        self._record("member.withdrawn", withdrawal_date=withdrawal_date.isoformat())

    def _ensure_open_application(self, day: date, today: date) -> None:
        """Der Antrag darf noch nicht abgelehnt oder zurückgenommen sein.

        Das Datum muss zwischen Antrag und heute liegen: Eine Entscheidung wird erfasst, wenn sie
        gefallen ist. `today` kommt von außen, damit die Tests nicht vom echten Datum abhängen.
        """
        if self.rejection_date is not None:
            raise DomainError("Der Antrag ist bereits abgelehnt oder zurückgenommen.")
        if self.application_date is not None and day < self.application_date:
            raise DomainError("Das Datum darf nicht vor dem Antrag liegen.")
        if day > today:
            raise DomainError("Das Datum darf nicht in der Zukunft liegen.")

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

    @on("member.admitted")
    def _admitted(self, event: Event) -> None:
        self.admission_date = date.fromisoformat(event.data["decision_date"])

    @on("member.rejected")
    def _rejected(self, event: Event) -> None:
        self.rejection_date = date.fromisoformat(event.data["decision_date"])

    @on("member.withdrawn")
    def _withdrawn(self, event: Event) -> None:
        self.rejection_date = date.fromisoformat(event.data["withdrawal_date"])
        self.withdrawn = True

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
