"""Status der Mitgliedschaft: wird aus gespeicherten Fakten zu einem Stichtag berechnet, nie gespeichert."""

from dataclasses import dataclass
from datetime import date

APPLICANT = "applicant"
REJECTED = "rejected"
STATUSES = {APPLICANT: "Antragsteller", REJECTED: "abgelehnt"}


@dataclass(frozen=True)
class MembershipDates:
    """Die Daten, aus denen sich der Status ergibt; Schritt 5 ergänzt Eintritt, Kündigung usw."""

    application_date: date
    admission_date: date | None = None
    rejection_date: date | None = None  # Ablehnung durch den Vorstand oder Rücknahme


def status_on(dates: MembershipDates, day: date) -> str | None:
    """Der Status am Tag `day`; None, wenn es den Antrag an diesem Tag noch nicht gab."""
    if day < dates.application_date:
        return None
    if dates.rejection_date is not None and day >= dates.rejection_date:
        return REJECTED
    return APPLICANT
