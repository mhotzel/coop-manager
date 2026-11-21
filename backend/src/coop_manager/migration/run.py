"""Setzt den Migrationsplan mit den normalen Methoden um und speichert ihn (siehe Plan).

Erst wird alles im Speicher aufgebaut (`build`), dann geprüft (`check.py`), und nur wenn alles
stimmt, in einer Transaktion gespeichert (`save`). Ein Probelauf lässt nur das Speichern weg.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from ..accounts.domain import ADDITIONAL_SHARES, Ledger
from ..accounts.services import get_ledger
from ..core import DomainError
from ..db import Database
from ..members.domain import Member
from ..members.numbers import SUBJECT as NUMBERS_SUBJECT
from ..members.numbers import MemberNumbers
from .plan import BookingPlan, MigrationPlan, PersonPlan

ACTOR = "migration"  # Auslöser aller Events der Migration (siehe Plan)


@dataclass
class Built:
    """Alles, was die Migration schreiben würde, noch nicht gespeichert."""

    numbers: MemberNumbers
    ledger: Ledger
    members: dict[int, Member] = field(default_factory=dict)  # Mitgliedsnummer → Mitglied
    errors: list[str] = field(default_factory=list)  # Ablehnungen der Methoden, mit Kontext

    def event_count(self) -> int:
        """Zahl der noch nicht gespeicherten Events."""
        aggregates = [self.numbers, self.ledger, *self.members.values()]
        return sum(len(a.uncommitted_events) for a in aggregates)


def build(db: Database, plan: MigrationPlan, today: date) -> Built:
    """Baut Nummernregister, Hauptbuch und Mitglieder im Speicher auf.

    Voraussetzungen: Das Genossenschaftskonto gibt es schon, Mitglieder noch nicht; sonst
    `DomainError`. Lehnt eine Methode etwas ab, steht das in `errors`, und es geht nicht weiter
    zum nächsten Abschnitt (Personen, Buchungen, Ausscheiden).
    """
    numbers = MemberNumbers.from_events(NUMBERS_SUBJECT, db.store.read_stream(NUMBERS_SUBJECT))
    ledger = get_ledger(db)
    if ledger.cooperative_account() is None:
        raise DomainError("Das Genossenschaftskonto fehlt; zuerst `coop-manager create-cooperative-account`.")
    if numbers.assigned:
        raise DomainError("Es gibt schon Mitglieder; die Migration läuft nur auf einen Bestand ohne Mitglieder.")

    built = Built(numbers, ledger)
    for person in plan.persons:
        _attempt(built, f"Person {person.number}", _add_person, built, person, today)
    if built.errors:
        return built
    for booking in plan.bookings:
        _attempt(built, f"Buchung {booking.legacy_id}", _post, built, booking, today)
    if built.errors:
        return built
    for person in plan.persons:
        _attempt(built, f"Person {person.number}", _exit, built, person, today)
    return built


def save(db: Database, built: Built) -> int:
    """Speichert alles in einer Transaktion mit dem Akteur `migration`; liefert die Zahl der Events.

    Reihenfolge wie beim Antrag in der App: Nummern, Mitglieder, Hauptbuch.
    """
    count = built.event_count()
    db.save_all([built.numbers, *built.members.values(), built.ledger], ACTOR)
    return count


def _attempt(built: Built, where: str, action: Callable[..., None], *args: object) -> None:
    """Ruft `action(*args)` auf; einen `DomainError` merkt es sich mit Ort, statt abzubrechen."""
    try:
        action(*args)
    except DomainError as exc:
        built.errors.append(f"{where}: {exc}")


def _add_person(built: Built, p: PersonPlan, today: date) -> None:
    """Person anlegen, Nummer und Konto vergeben, Historie, Mitgliedschaft, Kündigung und Tod."""
    member = Member.migrate(p.number, p.person_type, p.first, p.application_date, p.shares_subscribed)
    built.numbers.assign(p.number, member.subject)
    built.ledger.open_member_account(p.number, member.subject)
    for valid_from, version in p.versions:
        member.migrate_version(version, valid_from)
    if p.entry_date is not None:
        member.admit(p.entry_date, today)
        member.record_payment(p.entry_date, today)
    if p.withdrawal_date is not None:
        member.withdraw(p.withdrawal_date, today)
    if p.notice is not None:
        member.give_notice(*p.notice, today)
    if p.date_of_death is not None:
        member.record_death(p.date_of_death, today)
    built.members[p.number] = member


def _post(built: Built, b: BookingPlan, today: date) -> None:
    """Bucht; vor „Weitere Anteile“ wird die Zeichnung am Buchungstag erfasst."""
    if b.kind == ADDITIONAL_SHARES:
        built.members[b.credit].subscribe_additional_shares(b.shares, b.value_date, today)
    built.ledger.post_booking(b.kind, b.debit, b.credit, b.amount, b.shares, b.text, b.value_date, today)


def _exit(built: Built, p: PersonPlan, today: date) -> None:
    """Ausscheiden durch Spende oder Umbuchung aller Anteile; nach der Kündigung, weil danach keine mehr geht."""
    member = built.members[p.number]
    if p.donation_date is not None:
        member.donate_shares(p.donation_date, today)
    if p.transfer_date is not None:
        member.transfer_all_shares(p.transfer_date, today)
