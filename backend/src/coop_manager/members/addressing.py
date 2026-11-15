"""Adresszeilen, Briefanrede und Listenname: reine Funktionen aus den Personendaten (siehe Plan)."""

from .values import ADDRESS_LINE_COUNT, FEMALE, LEGAL_ENTITY, MALE, Address, PersonName, is_germany

MAX_LINE_LENGTH = 35  # Anschriftzone nach DIN 5008
DEAR_ALL = "Sehr geehrte Damen und Herren"


def _join(*parts: str) -> str:
    """Verbindet die nicht leeren Teile mit Leerzeichen."""
    return " ".join(part for part in parts if part)


def address_lines(person_type: str, name: PersonName, address: Address) -> tuple[str, ...]:
    """Die sechs Adresszeilen; leere Zeilen rücken nach oben, unten wird aufgefüllt."""
    person = _join(name.title, name.first_names, name.last_name)
    form = {MALE: "Herrn", FEMALE: "Frau"}.get(name.gender, "")
    if person_type == LEGAL_ENTITY:
        first = name.company_name
        second = _join("z. H.", form, person) if person else ""
    else:
        first = form
        second = person
    lines = [
        first,
        second,
        _join(address.street, address.house_number),
        _join(address.postal_code, address.city),
        "" if is_germany(address.country) else address.country.upper(),
    ]
    filled = [line for line in lines if line]
    return tuple(filled + [""] * (ADDRESS_LINE_COUNT - len(filled)))


def long_address_lines(lines: tuple[str, ...]) -> list[int]:
    """Nummern (ab 1) der Zeilen, die länger als 35 Zeichen sind; Anlass für eine Warnung."""
    return [number for number, line in enumerate(lines, start=1) if len(line) > MAX_LINE_LENGTH]


def salutation(person_type: str, name: PersonName, override: str = "", deceased: bool = False) -> str:
    """Die Briefanrede, wie sie in den Seriendruck kommt."""
    if deceased:
        return DEAR_ALL
    if override:
        return override
    if person_type == LEGAL_ENTITY:
        return DEAR_ALL
    person = _join(name.title, name.last_name)
    if name.gender == MALE:
        return f"Sehr geehrter Herr {person}"
    if name.gender == FEMALE:
        return f"Sehr geehrte Frau {person}"
    return "Liebes Mitglied"


def list_name(person_type: str, name: PersonName) -> str:
    """Name in Listen: „Nachname, Vornamen“ bzw. der Firmenname."""
    if person_type == LEGAL_ENTITY:
        return name.company_name
    return f"{name.last_name}, {name.first_names}"
