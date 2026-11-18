"""Status der Mitgliedschaft: wird aus gespeicherten Fakten zu einem Stichtag berechnet, nie gespeichert."""

from dataclasses import dataclass
from datetime import date

APPLICANT = "applicant"
MEMBER = "member"
REJECTED = "rejected"
NOTICE_GIVEN = "notice_given"
DECEASED = "deceased"
EXPELLED = "expelled"
EXITED = "exited"
STATUSES = {
    APPLICANT: "Antragsteller",
    MEMBER: "Mitglied",
    REJECTED: "abgelehnt",
    NOTICE_GIVEN: "gekündigt",
    DECEASED: "verstorben",
    EXPELLED: "ausgeschlossen",
    EXITED: "ausgeschieden",
}


@dataclass(frozen=True)
class MembershipDates:
    """Die Daten, aus denen sich der Status ergibt; Schritt 5 ergänzt Eintritt, Kündigung usw."""

    application_date: date
    admission_date: date | None = None
    rejection_date: date | None = None  # Ablehnung durch den Vorstand oder Rücknahme
    payment_date: date | None = None  # Geldeingang: Wertstellung der Einzahlung
    # Nur aus der Kündigung der Mitgliedschaft; eine Teilkündigung ändert den Status nicht.
    notice_date: date | None = None  # Eingang der Kündigung
    exit_date: date | None = None  # Ausscheiden zum 31.12.; ab dem Folgetag „ausgeschieden“
    date_of_death: date | None = None  # Ausscheiden dann zum 31.12. des Todesjahres (§ 77 GenG)
    expulsion_date: date | None = None  # Beschluss des Vorstands; Ausscheiden zum 31.12. (§ 68 GenG)


def status_on(dates: MembershipDates, day: date) -> str | None:
    """Der Status am Tag `day`; None, wenn es den Antrag an diesem Tag noch nicht gab."""
    if day < dates.application_date:
        return None
    if dates.rejection_date is not None and day >= dates.rejection_date:
        return REJECTED
    entry = entry_date(dates)
    if entry is None or day < entry:
        return APPLICANT
    # Bis einschließlich 31.12. gekündigt bzw. verstorben, ab dem Folgetag ausgeschieden (siehe Plan).
    exit = effective_exit_date(dates)
    if exit is not None and day > exit:
        return EXITED
    if dates.date_of_death is not None and day >= dates.date_of_death:
        return DECEASED
    if dates.expulsion_date is not None and day >= dates.expulsion_date:
        return EXPELLED
    if dates.notice_date is not None and day >= dates.notice_date:
        return NOTICE_GIVEN
    return MEMBER


def entry_date(dates: MembershipDates) -> date | None:
    """Eintrittsdatum: das spätere von Zulassung und Geldeingang (siehe Plan); None, solange eines fehlt."""
    if dates.admission_date is None or dates.payment_date is None:
        return None
    return max(dates.admission_date, dates.payment_date)


def effective_exit_date(dates: MembershipDates) -> date | None:
    """Das wirksame Ausscheiden: der früheste Termin aus Kündigung, Tod und Ausschluss.

    Tod und Ausschluss führen zum 31.12. ihres Jahres. Sie können das Ausscheiden nur vorziehen:
    Erfasst werden sie nur, solange die Person noch Mitglied ist, ihr Ausscheiden also nicht vor
    diesem 31.12. liegt. Eine Kündigung mit späterem Termin wird damit gegenstandslos.
    """
    candidates = [dates.exit_date]
    for event_date in (dates.date_of_death, dates.expulsion_date):
        if event_date is not None:
            candidates.append(date(event_date.year, 12, 31))
    present = [d for d in candidates if d is not None]
    return min(present) if present else None


def default_exit_date(notice_date: date) -> date:
    """Ausscheiden nach der Kündigungsfrist (Satzung 6.1): zwei Jahre zum Ende des Geschäftsjahres.

    Der früheste 31.12., der mindestens zwei Jahre nach dem Eingang liegt, ist immer der 31.12.
    des übernächsten Jahres: Eingang 15.03.2026 → 31.12.2028, auch Eingang 31.12.2026 → 31.12.2028.
    """
    return date(notice_date.year + 2, 12, 31)
