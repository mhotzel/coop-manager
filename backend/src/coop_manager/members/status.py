"""Status der Mitgliedschaft: wird aus gespeicherten Fakten zu einem Stichtag berechnet, nie gespeichert."""

from dataclasses import dataclass
from datetime import date

APPLICANT = "applicant"
MEMBER = "member"
REJECTED = "rejected"
STATUSES = {APPLICANT: "Antragsteller", MEMBER: "Mitglied", REJECTED: "abgelehnt"}


@dataclass(frozen=True)
class MembershipDates:
    """Die Daten, aus denen sich der Status ergibt; Schritt 5 ergänzt Eintritt, Kündigung usw."""

    application_date: date
    admission_date: date | None = None
    rejection_date: date | None = None  # Ablehnung durch den Vorstand oder Rücknahme
    payment_date: date | None = None  # Geldeingang: Wertstellung der Einzahlung


def status_on(dates: MembershipDates, day: date) -> str | None:
    """Der Status am Tag `day`; None, wenn es den Antrag an diesem Tag noch nicht gab."""
    if day < dates.application_date:
        return None
    if dates.rejection_date is not None and day >= dates.rejection_date:
        return REJECTED
    entry = entry_date(dates)
    if entry is not None and day >= entry:
        return MEMBER
    return APPLICANT


def entry_date(dates: MembershipDates) -> date | None:
    """Eintrittsdatum: das spätere von Zulassung und Geldeingang (siehe Plan); None, solange eines fehlt."""
    if dates.admission_date is None or dates.payment_date is None:
        return None
    return max(dates.admission_date, dates.payment_date)
