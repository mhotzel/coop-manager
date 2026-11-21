"""Rechnet aus den Altdaten den Migrationsplan aus: reine Funktionen, ohne Datenbank (siehe Plan).

Der Plan ist streng: Jede Person und jede Buchung wird zugeordnet oder steht in `migration.toml`
als übersprungen. Alles andere landet in `problems`; dann schreibt die Migration nichts. Die
Probleme werden gesammelt, damit ein Probelauf alle auf einmal zeigt.
"""

from dataclasses import dataclass, field, replace
from datetime import date

from ..accounts.domain import (
    ADDITIONAL_SHARES,
    COOPERATIVE_ACCOUNT_NUMBER,
    SHARE_DONATION,
    SUBSCRIPTION,
    TRANSFER,
)
from ..core import DomainError
from ..core.money import format_euro
from ..members.addressing import salutation as generated_salutation
from ..members.domain import PersonData
from ..members.status import default_exit_date
from ..members.values import LEGAL_ENTITY, NATURAL_PERSON, Address, Contact, PersonName, clean, validate_contact
from .source import Decisions, LegacyBooking, LegacyData, LegacyPerson

COOP = COOPERATIVE_ACCOUNT_NUMBER


@dataclass(frozen=True)
class BookingPlan:
    """Eine Buchung, wie sie ins Hauptbuch kommt; Wertstellung und Text aus dem Altsystem."""

    legacy_id: int
    kind: str
    debit: int
    credit: int
    amount: int  # Cent
    shares: int
    text: str
    value_date: date


@dataclass(frozen=True)
class PersonPlan:
    """Alles, was die Migration für eine Person schreibt (siehe Plan: „Je Person“)."""

    number: int
    person_type: str
    first: PersonData  # älteste Version, für `Member.migrate`
    versions: list[tuple[date | None, PersonData]]  # spätere Versionen mit „gültig ab“
    application_date: date
    shares_subscribed: int
    entry_date: date | None = None  # Mitglied: Zulassung und Zahlung an diesem Tag
    withdrawal_date: date | None = None  # „abgelehnt“: Rücknahme an diesem Tag
    notice: tuple[date, date] | None = None  # Kündigung: (Eingang, Ausscheiden)
    date_of_death: date | None = None
    additional_shares: list[tuple[date, int]] = field(default_factory=list)  # (Zulassung, Anteile)
    donation_date: date | None = None  # Ausscheiden mit Spende
    transfer_date: date | None = None  # Ausscheiden durch Umbuchung aller Anteile


@dataclass(frozen=True)
class MigrationPlan:
    """Das Ergebnis von `make_plan`; geschrieben wird nur, wenn `problems` leer ist."""

    persons: list[PersonPlan]
    bookings: list[BookingPlan]  # in der Reihenfolge, in der gebucht wird
    skipped_persons: list[int]
    skipped_bookings: list[tuple[int, str]]  # (alte ID, Grund)
    problems: list[str]


@dataclass
class _Ledger:
    """Was die Buchungen über die Personen verraten; entsteht beim Durchgehen der Buchungen."""

    held: dict[int, int] = field(default_factory=dict)  # Anteile je Konto
    first_in: dict[int, int] = field(default_factory=dict)  # Anteile der ersten Einzahlung/Umbuchung
    additional: dict[int, list[tuple[date, int]]] = field(default_factory=dict)
    donation: dict[int, date] = field(default_factory=dict)
    transfer: dict[int, date] = field(default_factory=dict)


def make_plan(data: LegacyData, decisions: Decisions) -> MigrationPlan:
    """Der ganze Migrationsplan; `problems` ist leer, wenn alles zugeordnet ist."""
    problems = _check_decisions(data, decisions)
    numbers = sorted(n for n in data.people if n != COOP and n not in decisions.skip_persons)
    members = set(numbers) - decisions.rejected

    skipped: list[tuple[int, str]] = []
    kept: list[LegacyBooking] = []
    for booking in sorted(data.bookings, key=lambda b: (b.day, b.id)):
        reason = decisions.skip_bookings.get(booking.id)
        if reason is None:
            kept.append(booking)
        else:
            skipped.append((booking.id, reason))

    ledger = _Ledger()
    bookings = [plan for b in kept if (plan := _booking(b, members, ledger, problems)) is not None]
    persons = [plan for number in numbers if (plan := _person(number, data, decisions, ledger, problems)) is not None]
    return MigrationPlan(
        persons=persons,
        bookings=bookings,
        skipped_persons=sorted(decisions.skip_persons & data.people.keys()),
        skipped_bookings=skipped,
        problems=problems,
    )


def _check_decisions(data: LegacyData, decisions: Decisions) -> list[str]:
    """Nummern in `migration.toml`, die es nicht gibt oder die sich widersprechen."""
    problems = []
    for number in sorted(decisions.skip_persons | decisions.rejected | decisions.corrections.keys()):
        if number not in data.people:
            problems.append(f"Person {number} aus migration.toml gibt es nicht.")
    for number in sorted(decisions.skip_persons & decisions.rejected):
        problems.append(f"Person {number} steht in skip_persons und in rejected.")
    booking_ids = {b.id for b in data.bookings}
    for booking_id in sorted(decisions.skip_bookings.keys() - booking_ids):
        problems.append(f"Buchung {booking_id} aus migration.toml gibt es nicht.")
    return problems


def _booking(b: LegacyBooking, members: set[int], ledger: _Ledger, problems: list[str]) -> BookingPlan | None:
    """Ordnet eine Buchung einer Buchungsart zu und führt den Bestand der Konten nach.

    Die Buchungen kommen in der Reihenfolge Datum, alte ID, damit der Bestand bei Umbuchungen am
    selben Tag stimmt.
    """
    where = f"Buchung {b.id} ({b.day}, {b.debit} an {b.credit})"
    for account in (b.debit, b.credit):
        if account != COOP and account not in members:
            problems.append(f"{where}: Konto {account} ist kein übernommenes Mitglied.")
            return None
    if b.debit == b.credit:
        problems.append(f"{where}: Soll und Haben sind gleich.")
        return None
    if b.debit == COOP:  # Einzahlung; die erste ist der Eintritt, jede weitere „Weitere Anteile“
        if b.credit in ledger.first_in:
            kind = ADDITIONAL_SHARES
            ledger.additional.setdefault(b.credit, []).append((b.day, b.shares))
        else:
            kind = SUBSCRIPTION
            ledger.first_in[b.credit] = b.shares
    elif b.credit == COOP:
        kind = SHARE_DONATION
    else:
        kind = TRANSFER
        ledger.first_in.setdefault(b.credit, b.shares)  # z. B. Erben: die Umbuchung zählt als Einzahlung

    if b.debit != COOP:
        left = ledger.held.get(b.debit, 0) - b.shares
        if left < 0:
            problems.append(f"{where}: Konto {b.debit} hat nicht so viele Anteile.")
            return None
        ledger.held[b.debit] = left
        if kind == SHARE_DONATION:
            if left != 0:
                problems.append(f"{where}: Spende, aber es bleiben {left} Anteile; gespendet wird immer alles.")
                return None
            ledger.donation[b.debit] = b.day
        elif left == 0:
            ledger.transfer[b.debit] = b.day
    ledger.held[b.credit] = ledger.held.get(b.credit, 0) + b.shares
    return BookingPlan(b.id, kind, b.debit, b.credit, b.amount, b.shares, b.text, b.day)


def _person(
    number: int, data: LegacyData, decisions: Decisions, ledger: _Ledger, problems: list[str]
) -> PersonPlan | None:
    """Der Plan für eine Person; None mit Problem, wenn sie sich nicht zuordnen lässt."""
    current = data.people[number]
    person_type = LEGAL_ENTITY if current.company else NATURAL_PERSON
    notes: list[str] = []  # Zusätze für die Hinweise des aktuellen Stands

    if number in decisions.rejected:
        own = sorted(
            (b for b in data.bookings if number in (b.debit, b.credit) and b.id in decisions.skip_bookings),
            key=lambda b: (b.day, b.id),
        )
        notes += [f"Altsystem {b.day}: {b.text} ({format_euro(b.amount)}, {b.shares} Anteile)" for b in own]
        application = current.entry or (own[0].day if own else None)
        if application is None:
            problems.append(f"Person {number}: abgelehnt, aber ohne Eintritt und ohne Buchung; kein Antragsdatum.")
            return None
        first, versions = _versions(number, data, person_type, notes)
        return PersonPlan(
            number=number,
            person_type=person_type,
            first=first,
            versions=versions,
            application_date=application,
            shares_subscribed=max((b.shares for b in own), default=1) or 1,
            withdrawal_date=max([application] + [b.day for b in own]),
        )

    if current.entry is None:
        problems.append(f"Person {number}: kein Eintritt und nicht in rejected.")
        return None
    if number not in ledger.first_in:
        problems.append(f"Person {number}: Eintritt, aber keine Einzahlung und keine empfangene Umbuchung.")
        return None

    exit_day = ledger.donation.get(number) or ledger.transfer.get(number)
    if current.exit is not None and current.exit != exit_day:
        notes.append(f"Altsystem: Austritt am {current.exit}")
    notice = None
    if current.notice is not None:
        gone = [day for day in (current.death, exit_day) if day is not None and day < current.notice]
        if gone:
            notes.append(f"Altsystem: Kündigung am {current.notice}, nicht übernommen (schon ausgeschieden)")
        else:
            notice = (current.notice, default_exit_date(current.notice))
    first, versions = _versions(number, data, person_type, notes)
    return PersonPlan(
        number=number,
        person_type=person_type,
        first=first,
        versions=versions,
        application_date=current.entry,
        shares_subscribed=ledger.first_in[number],
        entry_date=current.entry,
        notice=notice,
        date_of_death=current.death,
        additional_shares=ledger.additional.get(number, []),
        donation_date=ledger.donation.get(number),
        transfer_date=ledger.transfer.get(number),
    )


def _versions(
    number: int, data: LegacyData, person_type: str, notes: list[str]
) -> tuple[PersonData, list[tuple[date | None, PersonData]]]:
    """Älteste Version und spätere Versionen mit „gültig ab“ (siehe Plan: Historie).

    Aufeinanderfolgende gleiche Versionen fallen weg, z. B. wenn sich nur Statusdaten geändert
    haben. Weicht der aktuelle Stand von der letzten Version ab, folgt er ohne Datum. Die `notes`
    werden an die Hinweise der letzten Version angehängt.
    """
    history = data.history.get(number, [])
    states: list[tuple[date | None, PersonData]] = [
        (v.last_update.date() if v.last_update else None, _person_data(v, person_type)) for v in history
    ]
    states.append((None, _person_data(data.people[number], person_type)))
    unique = [states[0]]
    for valid_from, version in states[1:]:
        if version != unique[-1][1]:
            unique.append((valid_from, version))
    if notes:
        valid_from, last = unique[-1]
        added = "\n".join(notes)
        unique[-1] = (valid_from, replace(last, notes=f"{last.notes}\n{added}" if last.notes else added))
    return unique[0][1], unique[1:]


def _person_data(p: LegacyPerson, person_type: str) -> PersonData:
    """Die Personendaten einer Zeile (siehe Plan: Felder)."""
    name = PersonName(
        company_name=p.company,
        title=p.title,
        first_names=p.first_names,
        last_name=p.last_name,
        gender=p.gender.lower(),
    )
    generated = generated_salutation(person_type, name.cleaned())
    return PersonData(
        name=name,
        address=Address(
            street=p.street, house_number=p.house_number, postal_code=p.postal_code, city=p.city, country=p.country
        ),
        contact=Contact(phone=p.phone, email=_valid_email(p.email)),
        address_lines=p.address_lines,
        salutation="" if clean(p.salutation) in ("", generated) else p.salutation,
        no_mail=p.no_mail,
        notes=p.notes,
    )


def _valid_email(email: str) -> str:
    """Die E-Mail-Adresse, wenn die App sie annimmt; sonst leer (siehe Plan, ohne Notiz)."""
    try:
        validate_contact(Contact(email=clean(email).lower()))
    except DomainError:
        return ""
    return email
