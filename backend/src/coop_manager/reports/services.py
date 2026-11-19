"""Abfragen für die Reports: wer zum Stichtag in einer Liste steht, mit welchen Anteilen.

Wie `accounts/claims.py` geht das über alle Mitglieder und das Hauptbuch. Bei einigen hundert
Mitgliedern ist das schnell genug; eine eigene Projektion wäre mehr Aufwand.
"""

from dataclasses import dataclass
from datetime import date

from ..accounts.domain import (
    ADDITIONAL_SHARES,
    EXIT,
    LIMITATION_WRITEOFF,
    LOSS_DEDUCTION,
    PAYOUT,
    REFUND,
    SHARE_DONATION,
    SUBSCRIPTION,
    TRANSFER,
    Booking,
    Ledger,
)
from ..accounts.exits import exits_due
from ..accounts.services import get_ledger
from ..db import Database
from ..members.addressing import list_name, salutation
from ..members.domain import NOTICE, Member
from ..members.services import all_members
from ..members.status import DECEASED, EXPELLED, MEMBER, NOTICE_GIVEN
from ..system_settings.services import get_system_settings

# Wer eingetreten und zum Stichtag noch nicht ausgeschieden ist (siehe Plan: Reports).
LISTED_STATUSES = {MEMBER, NOTICE_GIVEN, DECEASED, EXPELLED}
# Wer an der Generalversammlung abstimmen darf: Gekündigte bis zum Ausscheiden, für Verstorbene
# die Erben. Ausgeschlossene nicht mehr ab dem Beschluss (§ 68 GenG; siehe Plan).
VOTING_STATUSES = {MEMBER, NOTICE_GIVEN, DECEASED}


@dataclass(frozen=True)
class GengRow:
    """Eine Zeile der Mitgliederliste nach GenG."""

    member_number: int
    name: str  # „Nachname, Vornamen“ bzw. Firma
    address: str  # einzeilig: „Straße Hausnummer, PLZ Ort“
    entry_date: date
    amount: int  # Anteile × Anteilspreis in Cent
    shares: int


@dataclass(frozen=True)
class AssemblyRow:
    """Eine Zeile der Liste zur Generalversammlung; „Vertreten durch“ und Unterschrift von Hand."""

    member_number: int
    name: str
    address: str


@dataclass(frozen=True)
class MailingRow:
    """Eine Zeile der Seriendruck-Liste; die Felder heißen in Excel wie im Altsystem."""

    member_number: int
    name: str
    country: str  # leer = Deutschland
    postal_code: str
    city: str
    street: str
    house_number: str
    salutation: str
    address_lines: tuple[str, ...]  # sechs Zeilen
    exit_date: date | None  # wirksames Ausscheiden, sobald gekündigt, verstorben oder ausgeschlossen
    amount: int  # Anteile × Anteilspreis in Cent
    shares: int
    date_of_death: date | None


# Bezeichnung jeder Buchungsart in der Spalte „Vorgang“; Stornos kommen nicht in die Liste.
BOOKING_LABELS = {
    SUBSCRIPTION: "Eintritt",
    ADDITIONAL_SHARES: "Weitere Anteile",
    REFUND: "Rückzahlung",
    TRANSFER: "Umbuchung",
    EXIT: "Ausscheiden",
    LOSS_DEDUCTION: "Kürzung Verlustvortrag",
    PAYOUT: "Auszahlung",
    LIMITATION_WRITEOFF: "Ausbuchung Verjährung",
    SHARE_DONATION: "Spende des Anteils",
}


@dataclass(frozen=True)
class EventRow:
    """Eine Zeile der Auswertung eines Geschäftsjahres: ein Vorgang bei einem Mitglied.

    Anteile und Betrag zählen aus Sicht des Mitgliedskontos: Zugänge positiv, Abgänge negativ.
    """

    event: str  # „Eintritt“, „Kündigung“, …
    member_number: int
    name: str
    day: date  # Wertstellung, Eingang der Kündigung, Sterbedatum oder Beschluss
    shares: int | None  # leer bei Kündigung, Todesfall und Ausschluss
    amount: int | None  # in Cent; leer, wenn es keine Buchung gibt
    counter_account: int | None  # Kontonummer der Gegenseite; leer, wenn es keine Buchung gibt


def shares_on(ledger: Ledger, number: int, day: date) -> int:
    """Die Anteile des Kontos am Ende des Tages `day` (siehe Plan: Reports).

    Es zählen die Buchungen mit Wertstellung bis zum Stichtag. Stornierte Buchungen und ihre
    Stornos fallen ganz heraus; zusammen ergäben sie ohnehin 0. Ausnahme: Die Ausscheidensbuchung
    zum 31.12. wirkt erst ab dem 01.01., denn bis einschließlich 31.12. zählt die Person noch mit
    ihren Anteilen.
    """
    total = 0
    for booking in ledger.bookings_of(number):
        if booking.reverses is not None or ledger.reversal_of(booking.id) is not None:
            continue
        if booking.value_date > day or (booking.kind == EXIT and booking.value_date == day):
            continue
        total += booking.shares if booking.credit == number else -booking.shares
    return total


def warnings(db: Database, day: date) -> list[str]:
    """Hinweise zum Stichtag: ob das Ausscheiden zum letzten 31.12. davor schon gebucht ist.

    Wer ganz ausscheidet, fehlt ab dem 01.01. ohnehin, das ergibt sich aus dem Status. Eine nicht
    gebuchte Teilkündigung aber ließe Anteile und Betrag zu hoch erscheinen. Geprüft wird nur der
    letzte 31.12.; ältere Jahre sind normalerweise längst gebucht (siehe Plan).
    """
    year = day.year - 1
    count = sum(1 for entry in exits_due(db, year) if not entry.booked)
    if count == 0:
        return []
    verb = "ist" if count == 1 else "sind"
    text = f"Zum 31.12.{year} {verb} {count} Ausscheiden noch nicht gebucht (Seite Jahresende)."
    return [f"{text} Anteile und Beträge können deshalb zu hoch sein."]


def members_geng(db: Database, day: date) -> list[GengRow]:
    """Mitgliederliste nach GenG zum Stichtag, nach Mitgliedsnummer."""
    share_price = get_system_settings(db).share_price or 0
    return [
        GengRow(
            member_number=member.member_number,
            name=list_name(member.person_type, member.name),
            address=one_line_address(member),
            entry_date=entry_date,
            amount=shares * share_price,
            shares=shares,
        )
        for member, entry_date, shares in _holders(db, day, LISTED_STATUSES)
    ]


def members_assembly(db: Database, day: date) -> list[AssemblyRow]:
    """Liste zur Generalversammlung: wer zum Stichtag abstimmen darf, nach Namen sortiert.

    Am Eingang sucht man nach dem Namen, deshalb alphabetisch statt nach Nummer.
    """
    rows = [
        AssemblyRow(
            member_number=member.member_number,
            name=list_name(member.person_type, member.name),
            address=one_line_address(member),
        )
        for member, _, _ in _holders(db, day, VOTING_STATUSES)
    ]
    return sorted(rows, key=lambda row: sort_key(row.name))


def members_mailing(db: Database, day: date) -> list[MailingRow]:
    """Seriendruck-Liste zum Stichtag, nach Mitgliedsnummer: wer eingeladen wird, ohne „keine Post“.

    Dieselben Personen wie in der Liste zur Generalversammlung. Verstorbene bekommen einen Eintrag
    an die Adresszeilen, mit der Anrede „Sehr geehrte Damen und Herren“ (siehe Plan).
    """
    share_price = get_system_settings(db).share_price or 0
    rows: list[MailingRow] = []
    for member, _, shares in _holders(db, day, VOTING_STATUSES):
        if member.no_mail:
            continue
        status = member.status(day)
        deceased = status == DECEASED
        address = member.address
        rows.append(
            MailingRow(
                member_number=member.member_number,
                name=list_name(member.person_type, member.name),
                country=address.country,
                postal_code=address.postal_code,
                city=address.city,
                street=address.street,
                house_number=address.house_number,
                salutation=salutation(member.person_type, member.name, member.salutation, deceased),
                address_lines=member.address_lines,
                # Zum Stichtag: Ein später erfasster Tod oder eine spätere Kündigung zählt noch nicht.
                exit_date=member.exit_date() if status != MEMBER else None,
                amount=shares * share_price,
                shares=shares,
                date_of_death=member.date_of_death if deceased else None,
            )
        )
    return rows


def fiscal_year_events(db: Database, year: int) -> list[EventRow]:
    """Alle Vorgänge des Geschäftsjahres (= Kalenderjahr), nach Datum und Mitgliedsnummer.

    Aus den Mitgliedsdaten kommen Kündigungen, Todesfälle und Ausschlüsse, aus dem Hauptbuch alle
    Buchungen. Zurückgenommenes fehlt: Die Mitgliedsdaten enthalten es nicht mehr, stornierte
    Buchungen und ihre Stornos lassen wir weg (siehe Plan).
    """
    ledger = get_ledger(db)
    share_price = get_system_settings(db).share_price or 0
    rows: list[EventRow] = []
    by_account: dict[int, Member] = {}  # Kontonummer → Mitglied, für die Buchungen
    for member in all_members(db):
        account = ledger.account_of(member.subject)
        if account is not None:
            by_account[account.number] = member
        rows.extend(_member_events(member, share_price))
    for booking in ledger.bookings:
        if booking.reverses is not None or ledger.reversal_of(booking.id) is not None:
            continue
        # Jede Seite, die ein Mitgliedskonto ist, bekommt eine Zeile; bei der Umbuchung also zwei.
        for number, counter, sign in ((booking.credit, booking.debit, 1), (booking.debit, booking.credit, -1)):
            member = by_account.get(number)
            if member is not None:
                rows.append(_booking_row(booking, member, counter, sign, share_price))
    rows = [row for row in rows if row.day.year == year]
    return sorted(rows, key=lambda row: (row.day, row.member_number))


def _member_events(member: Member, share_price: int) -> list[EventRow]:
    """Kündigungen, Todesfall und Ausschluss eines Mitglieds, mit ihrem maßgeblichen Datum.

    Nur die Teilkündigung hat Anteile und Betrag (gekündigte Anteile × Anteilspreis), bei den
    anderen bleiben beide leer (siehe Plan).
    """
    name = list_name(member.person_type, member.name)

    def row(event: str, day: date, shares: int | None = None) -> EventRow:
        amount = shares * share_price if shares is not None else None
        return EventRow(event, member.member_number, name, day, shares, amount, counter_account=None)

    rows = [
        row("Kündigung", n.notice_date) if n.kind == NOTICE else row("Teilkündigung", n.notice_date, n.shares)
        for n in member.notices
    ]
    if member.date_of_death is not None:
        rows.append(row("Todesfall", member.date_of_death))
    if member.expulsion_date is not None:
        rows.append(row("Ausschluss", member.expulsion_date))
    return rows


def _booking_row(booking: Booking, member: Member, counter: int, sign: int, share_price: int) -> EventRow:
    """Eine Buchung aus Sicht des Mitgliedskontos; `sign` ist +1 im Haben und -1 im Soll.

    Ausnahme Ausscheiden: Gebucht wird es mit Betrag 0, das Geld bleibt als Anspruch auf dem Konto.
    In der Auswertung sollen Anteile und Betrag aber zusammenpassen; deshalb steht hier der Wert der
    Anteile zum aktuellen Anteilspreis, nicht der Betrag aus dem Hauptbuch (siehe Plan).
    """
    amount = booking.shares * share_price if booking.kind == EXIT else booking.amount
    return EventRow(
        event=BOOKING_LABELS[booking.kind],
        member_number=member.member_number,
        name=list_name(member.person_type, member.name),
        day=booking.value_date,
        shares=sign * booking.shares,
        amount=sign * amount,
        counter_account=counter,
    )


def _holders(db: Database, day: date, statuses: set[str]) -> list[tuple[Member, date, int]]:
    """Wer zum Stichtag einen der Status hat und Anteile hält: Mitglied, Eintrittsdatum, Anteile.

    Ohne Anteile steht niemand in einer Liste, etwa am Tag einer Spende des Anteils (siehe Plan).
    """
    ledger = get_ledger(db)
    holders: list[tuple[Member, date, int]] = []
    for member in all_members(db):
        entry_date = member.entry_date()
        account = ledger.account_of(member.subject)
        if member.status(day) not in statuses or entry_date is None or account is None:
            continue
        shares = shares_on(ledger, account.number, day)
        if shares > 0:
            holders.append((member, entry_date, shares))
    return holders


def sort_key(name: str) -> str:
    """Sortierschlüssel wie im Telefonbuch (DIN 5007): „Ä“ wie „A“, „ß“ wie „ss“, ohne Groß/klein.

    Pythons `sorted` vergleicht sonst Zeichencodes, und „Ä“ landete hinter „Z“.
    """
    return name.casefold().replace("ä", "a").replace("ö", "o").replace("ü", "u")


def one_line_address(member: Member) -> str:
    """Anschrift in einer Zeile: „Straße Hausnummer, PLZ Ort“."""
    address = member.address
    return f"{address.street} {address.house_number}, {address.postal_code} {address.city}"
