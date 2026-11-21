import unicodedata
import uuid
from collections.abc import Collection
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Self

from ..core import DomainError
from ..eventsource import Aggregate, Event, on
from .addressing import address_lines
from .status import (
    DECEASED,
    EXPELLED,
    MEMBER,
    NOTICE_GIVEN,
    MembershipDates,
    effective_exit_date,
    entry_date,
    status_on,
)
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

NOTICE = "notice"  # Kündigung der Mitgliedschaft (§ 65 GenG): alle Anteile
PARTIAL_NOTICE = "partial_notice"  # Teilkündigung einzelner Anteile (§ 67b GenG)


@dataclass(frozen=True)
class Notice:
    """Eine Kündigung; jede hat eine eigene ID, damit sie sich gezielt zurücknehmen lässt."""

    id: str
    kind: str  # NOTICE oder PARTIAL_NOTICE
    notice_date: date  # Eingang der Kündigung
    exit_date: date  # Ausscheiden zum 31.12.
    shares: int | None = None  # nur bei der Teilkündigung; die Kündigung umfasst alle Anteile


@dataclass(frozen=True)
class AdditionalSubscription:
    """Zeichnung weiterer Anteile durch ein Mitglied (§ 15b GenG), zugelassen vom Vorstand."""

    id: str
    shares: int
    decision_date: date  # Zulassung durch den Vorstand


@dataclass(frozen=True)
class PersonData:
    """Alle Personendaten, die sich mit der Zeit ändern können; eine Version aus dem Altsystem.

    Nur für die Migration (siehe Plan): `Member.migrate` legt mit der ältesten Version an,
    `Member.migrate_version` übernimmt jede spätere.
    """

    name: PersonName
    address: Address
    contact: Contact = field(default_factory=Contact)
    address_lines: tuple[str, ...] = ("",) * ADDRESS_LINE_COUNT
    salutation: str = ""  # abweichende Briefanrede, leer = erzeugen
    no_mail: bool = False
    notes: str = ""


# Gründe für ein Ausscheiden zum 31.12.; die Texte macht das Frontend.
EXIT_REASON_DEATH = "deceased"
EXIT_REASON_EXPULSION = "expelled"
EXIT_REASON_DONATION = "donated"  # Spende des Anteils genau am 31.12.


@dataclass(frozen=True)
class ExitDue:
    """Was zu einem 31.12. ausscheidet: alle Anteile (`full`) und/oder Anteile aus Teilkündigungen."""

    full: bool
    partial_shares: int  # Anteile aus Teilkündigungen zu diesem Termin; bei `full` ohne Bedeutung
    reasons: tuple[str, ...]  # NOTICE, PARTIAL_NOTICE, EXIT_REASON_DEATH, EXIT_REASON_EXPULSION


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
        self.payment_date: date | None = None  # Geldeingang, erfasst vom Buchungsservice
        self.notices: list[Notice] = []  # laufende Kündigungen, zurückgenommene fallen heraus
        self.date_of_death: date | None = None
        self.expulsion_date: date | None = None  # Beschluss des Vorstands
        self.donation_date: date | None = None  # Ausscheiden mit Spende des Anteils
        self.transfer_date: date | None = None  # Ausscheiden durch Übertragung aller Anteile
        self.additional_subscriptions: list[AdditionalSubscription] = []  # weitere Anteile (5i)

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

    @classmethod
    def migrate(
        cls,
        member_number: int,
        person_type: str,
        data: PersonData,
        application_date: date,
        shares_subscribed: int,
    ) -> Self:
        """Legt eine Person aus dem Altsystem an; nur für die Migration (siehe Plan).

        Wie `apply`, aber mit den übernommenen Adresszeilen statt erzeugter, und die Anschrift darf
        fehlen. Briefanrede, „keine Post“ und Hinweise folgen als eigene Events, weil
        `member.applied` dafür keine Felder hat. Zulassung, Zahlung, Tod usw. erfasst die Migration
        danach mit den normalen Methoden.
        """
        validate_person_type(person_type)
        data = _clean_person_data(person_type, data)
        if member_number < 1:
            raise DomainError("Die Mitgliedsnummer muss positiv sein.")
        if shares_subscribed < 1:
            raise DomainError("Es muss mindestens ein Anteil gezeichnet werden.")
        member = cls(f"member-{uuid.uuid7()}")
        member._record(
            "member.applied",
            member_number=member_number,
            person_type=person_type,
            name=asdict(data.name),
            address=asdict(data.address),
            contact=asdict(data.contact),
            address_lines=list(data.address_lines),
            application_date=application_date.isoformat(),
            shares_subscribed=shares_subscribed,
        )
        member._record_changes(data)
        return member

    def migrate_version(self, data: PersonData, valid_from: date) -> None:
        """Übernimmt eine spätere Version der Personendaten aus der Historie des Altsystems.

        Für jeden geänderten Teil entsteht das normale Änderungsevent, zusätzlich mit `valid_from`:
        dem Tag, ab dem die Version im Altsystem galt. Ist nichts geändert, entsteht kein Event.
        """
        self._record_changes(_clean_person_data(self.person_type, data), valid_from)

    def _record_changes(self, data: PersonData, valid_from: date | None = None) -> None:
        """Schreibt für jeden Teil von `data`, der vom aktuellen Stand abweicht, sein Änderungsevent.

        `data` ist schon bereinigt und geprüft. Mit `valid_from` bekommt jedes Event das Feld
        zusätzlich; die Handler lesen es nicht, die spätere Ansicht „Verlauf“ schon (siehe Plan).
        """
        extra = {} if valid_from is None else {"valid_from": valid_from.isoformat()}
        if data.name != self.name:
            self._record("member.name-changed", name=asdict(data.name), **extra)
        if data.address != self.address:
            self._record("member.address-changed", address=asdict(data.address), **extra)
        if data.contact != self.contact:
            self._record("member.contact-changed", contact=asdict(data.contact), **extra)
        if data.address_lines != self.address_lines:
            self._record("member.address-lines-changed", address_lines=list(data.address_lines), **extra)
        if data.salutation != self.salutation:
            self._record("member.salutation-changed", salutation=data.salutation, **extra)
        if data.no_mail != self.no_mail:
            self._record("member.mail-preference-changed", no_mail=data.no_mail, **extra)
        if data.notes != self.notes:
            self._record("member.notes-changed", notes=data.notes, **extra)

    def status(self, day: date) -> str | None:
        """Der Status am Tag `day` (siehe status.py)."""
        return status_on(self._dates(), day)

    def entry_date(self) -> date | None:
        """Eintrittsdatum: das spätere von Zulassung und Geldeingang; None, solange eines fehlt."""
        return entry_date(self._dates())

    def exit_date(self) -> date | None:
        """Das wirksame Ausscheiden (31.12.): nach einem Tod das des Todesjahres, sonst aus der Kündigung."""
        return effective_exit_date(self._dates())

    def additional_shares_subscribed(self) -> int:
        """Alle weiteren Anteile, die nach dem Antrag gezeichnet und zugelassen wurden."""
        return sum(s.shares for s in self.additional_subscriptions)

    def total_shares_subscribed(self) -> int:
        """Gezeichnete Anteile insgesamt: Antrag plus weitere Zeichnungen."""
        return self.shares_subscribed + self.additional_shares_subscribed()

    def full_notice(self) -> Notice | None:
        """Die Kündigung der Mitgliedschaft; None, solange es keine gibt."""
        return next((n for n in self.notices if n.kind == NOTICE), None)

    def has_partial_notice(self, day: date) -> bool:
        """Läuft am Tag `day` eine Teilkündigung, deren Ausscheiden (31.12.) noch nicht vorbei ist?

        Nach der Spende oder der Übertragung aller Anteile ist die Person ausgeschieden;
        Teilkündigungen sind dann gegenstandslos.
        """
        for ended in (self.donation_date, self.transfer_date):
            if ended is not None and day > ended:
                return False
        return any(n.kind == PARTIAL_NOTICE and day <= n.exit_date for n in self.notices)

    def partially_noticed_shares(self, booked_exit_dates: Collection[date] = ()) -> int:
        """Anteile in Teilkündigungen, deren Ausscheiden noch nicht gebucht ist.

        Ist es gebucht (`booked_exit_dates` aus dem Hauptbuch), sind die Anteile schon vom Konto
        weg und dürfen nicht noch einmal abgezogen werden.
        """
        return sum(
            n.shares or 0 for n in self.notices if n.kind == PARTIAL_NOTICE and n.exit_date not in booked_exit_dates
        )

    def exit_due(self, day: date) -> ExitDue | None:
        """Was zum 31.12. `day` ausscheidet; None, wenn nichts.

        Voll scheidet aus, wessen wirksames Ausscheiden genau dieser Tag ist (Kündigung, Tod oder
        Ausschluss). Dazu kommen Teilkündigungen mit diesem Termin. Wer schon früher ausgeschieden
        ist, hat keine Teilkündigungen mehr, die noch greifen könnten.
        """
        exit_date = self.exit_date()
        if exit_date is not None and exit_date < day:
            return None
        full = exit_date == day
        partial = [n for n in self.notices if n.kind == PARTIAL_NOTICE and n.exit_date == day]
        if not full and not partial:
            return None
        reasons: list[str] = []
        if full:
            reasons.append(self._full_exit_reason(day))
        if partial:
            reasons.append(PARTIAL_NOTICE)
        return ExitDue(full, sum(n.shares or 0 for n in partial), tuple(reasons))

    def _full_exit_reason(self, day: date) -> str:
        """Warum die Mitgliedschaft zu `day` endet; Spende, dann Tod, dann Ausschluss, sonst Kündigung."""
        if self.donation_date == day:
            return EXIT_REASON_DONATION
        if self.date_of_death is not None and self.date_of_death.year == day.year:
            return EXIT_REASON_DEATH
        if self.expulsion_date is not None and self.expulsion_date.year == day.year:
            return EXIT_REASON_EXPULSION
        return NOTICE

    def _dates(self) -> MembershipDates:
        assert self.application_date is not None  # gesetzt durch member.applied
        full = self.full_notice()
        return MembershipDates(
            self.application_date,
            self.admission_date,
            self.rejection_date,
            self.payment_date,
            notice_date=full.notice_date if full else None,
            exit_date=full.exit_date if full else None,
            date_of_death=self.date_of_death,
            expulsion_date=self.expulsion_date,
            donation_date=self.donation_date,
            transfer_date=self.transfer_date,
        )

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
        if self.entry_date() is not None:
            raise DomainError("Die Person ist bereits Mitglied.")
        self._record("member.withdrawn", withdrawal_date=withdrawal_date.isoformat())

    def record_payment(self, payment_date: date, today: date) -> None:
        """Hält den Geldeingang fest: Die gezeichneten Anteile sind voll eingezahlt.

        Ob Betrag und Anteile passen, prüft der Buchungsservice; er ruft das mit der Wertstellung
        auf (siehe Plan: Variante A). Mit Zulassung und Geldeingang ist die Person Mitglied.
        """
        self._ensure_open_application(payment_date, today)
        if self.payment_date is not None:
            raise DomainError("Die Zahlung ist bereits erfasst.")
        self._record("member.paid-in", payment_date=payment_date.isoformat())

    def revoke_payment(self) -> None:
        """Nimmt den Geldeingang zurück, weil ein Storno die Einzahlung aufgehoben hat.

        Damit entfallen Eintrittsdatum und Status „Mitglied“. Der Buchungsservice ruft das auf und
        gibt eine Warnung aus; der Mitarbeiter klärt den Vorgang (siehe Plan: Buchungen und Storno).
        """
        if self.payment_date is None:
            raise DomainError("Es ist kein Geldeingang erfasst.")
        self._record("member.paid-in-revoked")

    def give_notice(self, notice_date: date, exit_date: date, today: date) -> None:
        """Kündigung der Mitgliedschaft: alle Anteile, die Person scheidet zum `exit_date` aus."""
        self._ensure_notice_possible(notice_date, exit_date, today)
        self._record(
            "member.notice-given",
            notice_id=str(uuid.uuid7()),
            notice_date=notice_date.isoformat(),
            exit_date=exit_date.isoformat(),
        )

    def give_partial_notice(
        self,
        shares: int,
        notice_date: date,
        exit_date: date,
        today: date,
        held: int,
        booked_exit_dates: Collection[date] = (),
    ) -> None:
        """Teilkündigung einzelner Anteile; mindestens einer bleibt, die Person bleibt Mitglied.

        `held` sind die Anteile auf dem Konto, `booked_exit_dates` die Termine, zu denen das
        Ausscheiden schon gebucht ist; beides kennt nur das Hauptbuch, deshalb gibt es der Service
        mit. Anteile aus laufenden Teilkündigungen lassen sich nicht noch einmal kündigen.
        """
        self._ensure_notice_possible(notice_date, exit_date, today)
        available = held - self.partially_noticed_shares(booked_exit_dates)
        if shares < 1:
            raise DomainError("Es muss mindestens ein Anteil gekündigt werden.")
        if shares >= available:
            raise DomainError(
                f"Es können höchstens {available - 1} von {available} Anteilen teilweise gekündigt werden, "
                "einer muss bleiben. Für alle Anteile die Mitgliedschaft kündigen."
            )
        self._record(
            "member.partial-notice-given",
            notice_id=str(uuid.uuid7()),
            notice_date=notice_date.isoformat(),
            exit_date=exit_date.isoformat(),
            shares=shares,
        )

    def withdraw_notice(self, notice_id: str, today: date) -> None:
        """Nimmt eine Kündigung zurück, solange das Ausscheiden noch nicht vorbei ist."""
        notice = next((n for n in self.notices if n.id == notice_id), None)
        if notice is None:
            raise DomainError("Die Kündigung gibt es nicht.")
        if today > notice.exit_date:
            raise DomainError("Das Ausscheiden ist bereits vorbei.")
        self._record("member.notice-withdrawn", notice_id=notice_id)

    def record_death(self, date_of_death: date, today: date) -> None:
        """Tod erfassen: Status „verstorben“, Ausscheiden zum 31.12. des Todesjahres (§ 77 GenG).

        Nur bei Mitgliedern, auch gekündigten. Stirbt ein Antragsteller, wird der Antrag
        zurückgenommen (siehe Plan). Erfährt man erst nach dem 31.12. davon, gilt das Ausscheiden
        trotzdem rückwirkend, denn der Status wird aus den Daten berechnet.
        """
        if date_of_death > today:
            raise DomainError("Das Sterbedatum darf nicht in der Zukunft liegen.")
        if self.date_of_death is not None:
            raise DomainError("Der Tod ist bereits erfasst.")
        if self.status(date_of_death) not in (MEMBER, NOTICE_GIVEN, EXPELLED):
            raise DomainError("Den Tod erfasst man nur bei Mitgliedern; bei Antragstellern den Antrag zurücknehmen.")
        self._record("member.died", date_of_death=date_of_death.isoformat())

    def revoke_death(self) -> None:
        """Nimmt eine falsche Erfassung des Todes zurück (falsches Mitglied oder falsches Datum)."""
        if self.date_of_death is None:
            raise DomainError("Es ist kein Tod erfasst.")
        self._record("member.death-revoked")

    def expel(self, decision_date: date, today: date) -> None:
        """Ausschluss durch Beschluss des Vorstands (Satzung 6.2–6.4); Ausscheiden zum 31.12.

        Nur bei Mitgliedern, auch gekündigten. Den Widerspruch beim Aufsichtsrat (binnen sechs
        Wochen) überwacht die App nicht; gibt er ihm statt, wird der Ausschluss aufgehoben.
        """
        if decision_date > today:
            raise DomainError("Das Datum darf nicht in der Zukunft liegen.")
        if self.expulsion_date is not None:
            raise DomainError("Der Ausschluss ist bereits erfasst.")
        if self.status(decision_date) not in (MEMBER, NOTICE_GIVEN):
            raise DomainError("Ausschließen kann man nur, wer am Tag des Beschlusses Mitglied ist.")
        self._record("member.expelled", decision_date=decision_date.isoformat())

    def lift_expulsion(self, decision_date: date, today: date) -> None:
        """Hebt den Ausschluss auf: Widerspruch erfolgreich oder Fehlerfassung.

        Das Datum (z. B. der Beschluss des Aufsichtsrats) hält das Event fest; der Ausschluss gilt
        danach als nie geschehen, auch wenn das Jahresende schon vorbei ist.
        """
        if self.expulsion_date is None:
            raise DomainError("Es ist kein Ausschluss erfasst.")
        if decision_date > today:
            raise DomainError("Das Datum darf nicht in der Zukunft liegen.")
        if decision_date < self.expulsion_date:
            raise DomainError("Das Datum darf nicht vor dem Ausschluss liegen.")
        self._record("member.expulsion-lifted", decision_date=decision_date.isoformat())

    def donate_shares(self, donation_date: date, today: date) -> None:
        """Ausscheiden mit Spende des Anteils: ohne Kündigungsfrist, am Tag der Spende.

        Bewusst so entschieden, obwohl rechtlich umstritten (siehe Plan). Nur bei Mitgliedern, auch
        gekündigten; laufende Kündigungen werden damit gegenstandslos. Ab dem Folgetag ist die
        Person ausgeschieden. Die Buchung des ganzen Guthabens an die Genossenschaft macht der
        Buchungsservice, der das hier mit der Wertstellung aufruft.
        """
        if donation_date > today:
            raise DomainError("Das Datum der Spende darf nicht in der Zukunft liegen.")
        if self.donation_date is not None:
            raise DomainError("Die Spende ist bereits erfasst.")
        if self.status(donation_date) not in (MEMBER, NOTICE_GIVEN):
            raise DomainError("Mit Spende ausscheiden kann nur, wer an diesem Tag Mitglied ist.")
        self._record("member.shares-donated", donation_date=donation_date.isoformat())

    def revoke_donation(self) -> None:
        """Nimmt das Ausscheiden mit Spende zurück, weil die Spendenbuchung storniert wurde."""
        if self.donation_date is None:
            raise DomainError("Es ist keine Spende erfasst.")
        self._record("member.donation-revoked")

    def subscribe_additional_shares(self, shares: int, decision_date: date, today: date) -> None:
        """Weitere Anteile zeichnen, mit dem Datum der Zulassung durch den Vorstand (siehe Plan).

        Nur bei Mitgliedern, nicht gekündigt. Eingezahlt wird mit der Buchung „Weitere Anteile“.
        """
        if shares < 1:
            raise DomainError("Es muss mindestens ein Anteil gezeichnet werden.")
        if decision_date > today:
            raise DomainError("Das Datum darf nicht in der Zukunft liegen.")
        if self.status(decision_date) != MEMBER:
            raise DomainError("Weitere Anteile zeichnen kann nur, wer an diesem Tag Mitglied ist.")
        self._record(
            "member.additional-shares-subscribed",
            subscription_id=str(uuid.uuid7()),
            shares=shares,
            decision_date=decision_date.isoformat(),
        )

    def revoke_additional_shares(self, subscription_id: str, paid: int) -> None:
        """Nimmt eine falsch erfasste Zeichnung zurück, solange ihre Anteile nicht eingezahlt sind.

        `paid` sind die als „Weitere Anteile“ gebuchten Anteile; die kennt nur das Hauptbuch.
        """
        subscription = next((s for s in self.additional_subscriptions if s.id == subscription_id), None)
        if subscription is None:
            raise DomainError("Die Zeichnung gibt es nicht.")
        if paid > self.additional_shares_subscribed() - subscription.shares:
            raise DomainError("Die Anteile sind schon eingezahlt; zuerst die Buchung stornieren.")
        self._record("member.additional-shares-revoked", subscription_id=subscription_id)

    def ensure_can_give_shares(self, day: date) -> None:
        """Darf die Person am Tag `day` Anteile per Umbuchung abgeben? (siehe Plan: Umbuchung)

        Mitglieder, auch gekündigte, und Verstorbene. Bei Verstorbenen auch nach dem 31.12. des
        Todesjahres, wenn der Tod erst später bekannt wird; dann ist die Person rechnerisch schon
        ausgeschieden, die Umbuchung auf Erben bleibt aber erlaubt.
        """
        if self.date_of_death is not None and day >= self.date_of_death:
            return
        if self.status(day) not in (MEMBER, NOTICE_GIVEN, DECEASED):
            raise DomainError("Anteile abgeben kann nur, wer an diesem Tag Mitglied ist.")

    def ensure_can_receive_shares(self, day: date) -> None:
        """Darf die Person am Tag `day` Anteile per Umbuchung empfangen?

        Mitglieder und zugelassene Antragsteller, die noch nicht eingezahlt haben (z. B. Erben).
        Bei Antragstellern zählt die Umbuchung wie die Einzahlung; das gleicht der Buchungsservice ab.
        """
        if self.status(day) == MEMBER:
            return
        if self.admission_date is not None and self.payment_date is None and self.rejection_date is None:
            return
        raise DomainError("Empfangen kann nur ein Mitglied oder ein zugelassener Antragsteller.")

    def transfer_all_shares(self, transfer_date: date, today: date) -> None:
        """Hält fest, dass die Person alle Anteile übertragen hat; ab dem Folgetag ist sie ausgeschieden.

        Die Umbuchung selbst macht der Buchungsservice; er ruft das nur auf, wenn danach keine
        Anteile mehr auf dem Konto sind. Laufende Kündigungen werden damit gegenstandslos.
        """
        if transfer_date > today:
            raise DomainError("Das Datum darf nicht in der Zukunft liegen.")
        if self.transfer_date is not None:
            raise DomainError("Die Übertragung aller Anteile ist bereits erfasst.")
        self.ensure_can_give_shares(transfer_date)
        self._record("member.all-shares-transferred", transfer_date=transfer_date.isoformat())

    def revoke_transfer(self) -> None:
        """Nimmt das Ausscheiden durch Übertragung zurück, weil ein Storno wieder Anteile gebracht hat."""
        if self.transfer_date is None:
            raise DomainError("Es ist keine Übertragung aller Anteile erfasst.")
        self._record("member.transfer-revoked")

    def _ensure_notice_possible(self, notice_date: date, exit_date: date, today: date) -> None:
        """Gemeinsame Prüfungen für Kündigung und Teilkündigung.

        Am Eingangstag muss die Person Mitglied sein (nicht Antragsteller, nicht schon gekündigt).
        Das Ausscheiden darf von der Frist abweichen, muss aber ein 31.12. nach dem Eingang sein.
        """
        if notice_date > today:
            raise DomainError("Der Eingang der Kündigung darf nicht in der Zukunft liegen.")
        if self.full_notice() is not None:
            raise DomainError("Die Mitgliedschaft ist bereits gekündigt.")
        if self.donation_date is not None:
            raise DomainError("Die Person ist mit Spende des Anteils ausgeschieden.")
        if self.transfer_date is not None:
            raise DomainError("Die Person hat alle Anteile übertragen und ist ausgeschieden.")
        if self.status(notice_date) != MEMBER:
            raise DomainError("Kündigen kann nur, wer am Tag des Eingangs Mitglied ist.")
        if (exit_date.month, exit_date.day) != (12, 31):
            raise DomainError("Das Ausscheiden ist immer zum 31.12.")
        if exit_date <= notice_date:
            raise DomainError("Das Ausscheiden muss nach dem Eingang der Kündigung liegen.")

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
        salutation = _clean_salutation(salutation)
        if salutation != self.salutation:
            self._record("member.salutation-changed", salutation=salutation)

    def change_mail_preference(self, no_mail: bool) -> None:
        """Setzt „keine Post“: Das Mitglied bekommt keine Einladungen per Seriendruck."""
        if no_mail != self.no_mail:
            self._record("member.mail-preference-changed", no_mail=no_mail)

    def change_notes(self, notes: str) -> None:
        """Hinweise sind mehrzeilig; nur Leerraum am Anfang und Ende fällt weg."""
        notes = _clean_notes(notes)
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

    @on("member.paid-in")
    def _paid_in(self, event: Event) -> None:
        self.payment_date = date.fromisoformat(event.data["payment_date"])

    @on("member.paid-in-revoked")
    def _paid_in_revoked(self, event: Event) -> None:
        self.payment_date = None

    @on("member.notice-given")
    def _notice_given(self, event: Event) -> None:
        self.notices.append(_notice(NOTICE, event))

    @on("member.partial-notice-given")
    def _partial_notice_given(self, event: Event) -> None:
        self.notices.append(_notice(PARTIAL_NOTICE, event))

    @on("member.notice-withdrawn")
    def _notice_withdrawn(self, event: Event) -> None:
        self.notices = [n for n in self.notices if n.id != event.data["notice_id"]]

    @on("member.died")
    def _died(self, event: Event) -> None:
        self.date_of_death = date.fromisoformat(event.data["date_of_death"])

    @on("member.death-revoked")
    def _death_revoked(self, event: Event) -> None:
        self.date_of_death = None

    @on("member.expelled")
    def _expelled(self, event: Event) -> None:
        self.expulsion_date = date.fromisoformat(event.data["decision_date"])

    @on("member.expulsion-lifted")
    def _expulsion_lifted(self, event: Event) -> None:
        self.expulsion_date = None

    @on("member.shares-donated")
    def _shares_donated(self, event: Event) -> None:
        self.donation_date = date.fromisoformat(event.data["donation_date"])

    @on("member.donation-revoked")
    def _donation_revoked(self, event: Event) -> None:
        self.donation_date = None

    @on("member.all-shares-transferred")
    def _all_shares_transferred(self, event: Event) -> None:
        self.transfer_date = date.fromisoformat(event.data["transfer_date"])

    @on("member.transfer-revoked")
    def _transfer_revoked(self, event: Event) -> None:
        self.transfer_date = None

    @on("member.additional-shares-subscribed")
    def _additional_shares_subscribed(self, event: Event) -> None:
        self.additional_subscriptions.append(
            AdditionalSubscription(
                id=event.data["subscription_id"],
                shares=event.data["shares"],
                decision_date=date.fromisoformat(event.data["decision_date"]),
            )
        )

    @on("member.additional-shares-revoked")
    def _additional_shares_revoked(self, event: Event) -> None:
        self.additional_subscriptions = [
            s for s in self.additional_subscriptions if s.id != event.data["subscription_id"]
        ]

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


def _clean_salutation(salutation: str) -> str:
    """Bereinigte Briefanrede; höchstens 100 Zeichen."""
    salutation = clean(salutation)
    if len(salutation) > 100:
        raise DomainError("Die Briefanrede hat höchstens 100 Zeichen.")
    return salutation


def _clean_notes(notes: str) -> str:
    """Hinweise sind mehrzeilig; nur Leerraum am Anfang und Ende fällt weg. Höchstens 5000 Zeichen."""
    notes = unicodedata.normalize("NFC", notes).strip()
    if len(notes) > 5000:
        raise DomainError("Die Hinweise haben höchstens 5000 Zeichen.")
    return notes


def _clean_person_data(person_type: str, data: PersonData) -> PersonData:
    """Bereinigt und prüft eine Version der Personendaten wie die einzelnen Änderungen.

    Einzige Ausnahme für die Migration: Die Anschrift darf fehlen (`required=False`).
    """
    name, address, contact = data.name.cleaned(), data.address.cleaned(), data.contact.cleaned()
    validate_name(person_type, name)
    validate_address(address, required=False)
    validate_contact(contact)
    return PersonData(
        name=name,
        address=address,
        contact=contact,
        address_lines=clean_address_lines(data.address_lines),
        salutation=_clean_salutation(data.salutation),
        no_mail=data.no_mail,
        notes=_clean_notes(data.notes),
    )


def _notice(kind: str, event: Event) -> Notice:
    """Baut eine `Notice` aus den Daten eines Kündigungs-Events."""
    return Notice(
        id=event.data["notice_id"],
        kind=kind,
        notice_date=date.fromisoformat(event.data["notice_date"]),
        exit_date=date.fromisoformat(event.data["exit_date"]),
        shares=event.data.get("shares"),
    )
