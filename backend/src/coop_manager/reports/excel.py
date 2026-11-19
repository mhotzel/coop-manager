"""Excel-Dateien der Reports, nach dem Vorbild von `purchase-prices` (costcontrol/report.py)."""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .services import GengRow

GENG_COLUMNS = (
    # (Überschrift, Breite, Zahlenformat)
    ("Nr.", 8, "0"),
    ("Name", 35, "@"),
    ("Anschrift", 50, "@"),
    ("Eintritt", 12, "DD.MM.YYYY"),
    ("Betrag", 14, '#,##0.00 "€"'),
    ("Anteile", 10, "0"),
)


def members_geng(rows: list[GengRow], day: date) -> bytes:
    """Mitgliederliste nach GenG als .xlsx: Titel, Stichtag, Kopfzeile, eine Zeile je Mitglied."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None  # eine neue Arbeitsmappe hat immer ein Blatt
    sheet.title = "Mitgliederliste"
    sheet["A1"] = "Mitgliederliste nach § 30 GenG"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A2"] = f"Stichtag: {day:%d.%m.%Y}"
    # Zeile 3 bleibt leer, Zeile 4 ist die Kopfzeile.
    sheet.append([])
    sheet.append([header for header, _, _ in GENG_COLUMNS])
    for cell in sheet[4]:
        cell.font = Font(bold=True)
    for index, (_, width, _) in enumerate(GENG_COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width

    for row in rows:
        # Betrag in Euro: Excel rechnet mit Kommazahlen, die App mit Cent.
        sheet.append([row.member_number, row.name, row.address, row.entry_date, row.amount / 100, row.shares])
        for cell, (_, _, number_format) in zip(sheet[sheet.max_row], GENG_COLUMNS, strict=True):
            cell.number_format = number_format

    sheet.freeze_panes = "A5"  # Titel und Kopfzeile bleiben beim Blättern stehen
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
