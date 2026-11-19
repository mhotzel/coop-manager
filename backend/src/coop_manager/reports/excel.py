"""Excel-Dateien der Reports, nach dem Vorbild von `purchase-prices` (costcontrol/report.py).

Jede Liste beschreibt ihre Spalten als Tabelle (Überschrift, Breite, Zahlenformat); den Aufbau
mit Titel, Stichtag und Kopfzeile übernimmt `_new_sheet`.
"""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .services import AssemblyRow, GengRow

Columns = tuple[tuple[str, int, str], ...]

HEADER_ROW = 4  # Zeile 1 Titel, Zeile 2 Stichtag, Zeile 3 leer

GENG_COLUMNS: Columns = (
    # (Überschrift, Breite, Zahlenformat)
    ("Nr.", 8, "0"),
    ("Name", 35, "@"),
    ("Anschrift", 50, "@"),
    ("Eintritt", 12, "DD.MM.YYYY"),
    ("Betrag", 14, '#,##0.00 "€"'),
    ("Anteile", 10, "0"),
)

ASSEMBLY_COLUMNS: Columns = (
    ("Nr.", 8, "0"),
    ("Mitglied", 35, "@"),
    ("Adresse", 45, "@"),
    ("Vertreten durch", 30, "@"),
    ("Unterschrift", 35, "@"),
)


def members_geng(rows: list[GengRow], day: date) -> bytes:
    """Mitgliederliste nach GenG als .xlsx, eine Zeile je Mitglied."""
    workbook, sheet = _new_sheet("Mitgliederliste", "Mitgliederliste nach § 30 GenG", day, GENG_COLUMNS)
    for row in rows:
        # Betrag in Euro: Excel rechnet mit Kommazahlen, die App mit Cent.
        _append(
            sheet,
            GENG_COLUMNS,
            [row.member_number, row.name, row.address, row.entry_date, row.amount / 100, row.shares],
        )
    return _save(workbook)


def members_assembly(rows: list[AssemblyRow], day: date) -> bytes:
    """Liste zur Generalversammlung als .xlsx, zum Ausdrucken und Unterschreiben."""
    workbook, sheet = _new_sheet("Generalversammlung", "Anwesenheitsliste Generalversammlung", day, ASSEMBLY_COLUMNS)
    for row in rows:
        _append(sheet, ASSEMBLY_COLUMNS, [row.member_number, row.name, row.address, "", ""])
        sheet.row_dimensions[sheet.max_row].height = 30  # Platz für die Unterschrift

    # Druck: quer auf A4, alle Spalten auf einer Seitenbreite, Gitterlinien als Kästchen,
    # die Kopfzeile auf jeder Seite.
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.sheet_properties.pageSetUpPr.fitToPage = True  # pyright: ignore[reportOptionalMemberAccess]
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0  # 0 = so viele Seiten hoch wie nötig
    sheet.print_options.gridLines = True
    sheet.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"
    return _save(workbook)


def _new_sheet(sheet_title: str, title: str, day: date, columns: Columns) -> tuple[Workbook, Worksheet]:
    """Neue Arbeitsmappe mit Titel, „Stichtag: TT.MM.JJJJ“ und fett gedruckter Kopfzeile."""
    workbook = Workbook()
    sheet = workbook.active
    assert isinstance(sheet, Worksheet)  # eine neue Arbeitsmappe hat immer ein Blatt
    sheet.title = sheet_title
    sheet["A1"] = title
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A2"] = f"Stichtag: {day:%d.%m.%Y}"
    for index, (header, width, _) in enumerate(columns, start=1):
        cell = sheet.cell(row=HEADER_ROW, column=index, value=header)
        cell.font = Font(bold=True)
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = f"A{HEADER_ROW + 1}"  # Titel und Kopfzeile bleiben beim Blättern stehen
    return workbook, sheet


def _append(sheet: Worksheet, columns: Columns, values: list[object]) -> None:
    """Hängt eine Zeile an und setzt das Zahlenformat jeder Zelle."""
    sheet.append(values)
    for cell, (_, _, number_format) in zip(sheet[sheet.max_row], columns, strict=True):
        cell.number_format = number_format


def _save(workbook: Workbook) -> bytes:
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
