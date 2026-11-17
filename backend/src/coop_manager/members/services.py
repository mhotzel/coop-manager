import logging
from collections.abc import Callable
from datetime import date

from ..accounts.services import get_ledger
from ..core import NotFoundError
from ..db import Database
from ..eventsource import ConcurrencyError
from .domain import Member
from .numbers import SUBJECT, MemberNumbers
from .values import Address, Contact, PersonName

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def apply_for_membership(
    db: Database,
    person_type: str,
    name: PersonName,
    address: Address,
    application_date: date,
    shares_subscribed: int,
    contact: Contact | None,
    actor: str,
) -> Member:
    """Erfasst eine Beitrittserklärung mit der nächsten freien Nummer und eröffnet das Konto.

    Mitglieds- und Kontonummer sind dieselbe. Nummernregister, Mitglied und Hauptbuch werden
    zusammen gespeichert, alle oder keines; ein Mitglied ohne Konto kann es also nicht geben. Hat
    jemand anderes in der Zwischenzeit eine Nummer vergeben oder gebucht, scheitert das Speichern
    an der Versionsprüfung, und es geht mit der dann nächsten freien Nummer von vorn los.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        numbers = _load_numbers(db)
        ledger = get_ledger(db)
        number = numbers.next_number(ledger.member_account_numbers())
        member = Member.apply(number, person_type, name, address, application_date, shares_subscribed, contact)
        numbers.assign(number, member.subject)
        ledger.open_member_account(number, member.subject)
        try:
            db.save_all([numbers, member, ledger], actor)
        except ConcurrencyError:
            log.warning("member number taken concurrently", extra={"number": number, "attempt": attempt})
            if attempt == MAX_ATTEMPTS:
                raise
            continue
        log.info("member applied", extra={"member": member.subject, "number": number, "actor": actor})
        return member
    raise AssertionError("unreachable")  # die Schleife endet immer mit return oder raise


def admit(db: Database, member_id: str, decision_date: date, today: date, actor: str) -> Member:
    """Zulassung durch den Vorstand mit Beschlussdatum."""
    return _change(db, member_id, actor, lambda member: member.admit(decision_date, today))


def reject(db: Database, member_id: str, decision_date: date, today: date, actor: str) -> Member:
    """Ablehnung durch den Vorstand mit Beschlussdatum."""
    return _change(db, member_id, actor, lambda member: member.reject(decision_date, today))


def withdraw(db: Database, member_id: str, withdrawal_date: date, today: date, actor: str) -> Member:
    """Rücknahme des Antrags durch die Person."""
    return _change(db, member_id, actor, lambda member: member.withdraw(withdrawal_date, today))


def change_name(db: Database, member_id: str, name: PersonName, actor: str) -> Member:
    """Name ändern, z. B. nach Heirat."""
    return _change(db, member_id, actor, lambda member: member.change_name(name))


def change_address(db: Database, member_id: str, address: Address, actor: str) -> Member:
    """Anschrift ändern, z. B. nach Umzug."""
    return _change(db, member_id, actor, lambda member: member.change_address(address))


def change_contact(db: Database, member_id: str, contact: Contact, actor: str) -> Member:
    """Telefon und E-Mail ändern."""
    return _change(db, member_id, actor, lambda member: member.change_contact(contact))


def change_address_lines(db: Database, member_id: str, lines: list[str], actor: str) -> Member:
    """Die sechs Adresszeilen setzen, von Hand gepflegt oder neu erzeugt."""
    return _change(db, member_id, actor, lambda member: member.change_address_lines(lines))


def change_salutation(db: Database, member_id: str, salutation: str, actor: str) -> Member:
    """Abweichende Briefanrede setzen; leer = wieder erzeugen."""
    return _change(db, member_id, actor, lambda member: member.change_salutation(salutation))


def change_mail_preference(db: Database, member_id: str, no_mail: bool, actor: str) -> Member:
    """„Keine Post“ setzen oder aufheben."""
    return _change(db, member_id, actor, lambda member: member.change_mail_preference(no_mail))


def change_notes(db: Database, member_id: str, notes: str, actor: str) -> Member:
    """Hinweise ändern."""
    return _change(db, member_id, actor, lambda member: member.change_notes(notes))


def get_member(db: Database, member_id: str) -> Member:
    """Das Mitglied mit allen Daten, aus seinen Events; NotFoundError, wenn es keines gibt."""
    member = db.store.load(Member, member_id)
    if member is None:
        raise NotFoundError("Das Mitglied wurde nicht gefunden.")
    return member


def _load_numbers(db: Database) -> MemberNumbers:
    """Das Nummernregister mit allen bisher vergebenen Nummern."""
    return MemberNumbers.from_events(SUBJECT, db.store.read_stream(SUBJECT))


def _change(db: Database, member_id: str, actor: str, action: Callable[[Member], None]) -> Member:
    """Lädt das Mitglied, führt die Änderung aus und speichert die neuen Events."""
    member = get_member(db, member_id)
    action(member)
    db.save(member, actor)
    log.info("member changed", extra={"member": member_id, "actor": actor, "version": member.version})
    return member
