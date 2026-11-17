"""Geldbeträge: intern immer ganze Cent (int), nach außen Euro mit Komma."""

import re

from .errors import DomainError

# Ganze Euro, optional mit Komma oder Punkt und ein bis zwei Nachkommastellen: 50 / 50,5 / 50.00
_EURO = re.compile(r"(\d+)(?:[,.](\d{1,2}))?")


def parse_euro(text: str) -> int:
    """Wandelt eine Euro-Eingabe wie „50“ oder „50,00“ in Cent um.

    Ohne Umweg über float: 0,1 + 0,2 ist als float nicht genau 0,3, ganze Cent sind immer genau.
    """
    match = _EURO.fullmatch(text.strip())
    if match is None:
        raise DomainError(f"„{text}“ ist kein gültiger Euro-Betrag (z. B. 50 oder 50,00).")
    euros, cents = match.groups()
    # „50,5“ meint 50 Euro und 50 Cent, deshalb rechts mit 0 auffüllen.
    return int(euros) * 100 + int((cents or "0").ljust(2, "0"))


def format_euro(cents: int) -> str:
    """Zeigt Cent als Euro an, z. B. 5000 → „50,00 €“."""
    sign = "-" if cents < 0 else ""
    euros, rest = divmod(abs(cents), 100)
    return f"{sign}{euros},{rest:02d} €"
