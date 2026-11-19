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

from .services import AssemblyRow, EventRow, GengRow, MailingRow

Columns = tuple[tuple[str, int, str], ...]

HEADER_ROW = 4  # Zeile 1 Titel, Zeile 2 Stichtag, Zeile 3 Warnung oder leer

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

# Feldnamen wie im Altsystem, damit die Word-Vorlagen für den Seriendruck weiter passen.
MAILING_COLUMNS: Columns = (
    ("PersNr", 8, "0"),
    ("name_mitgl", 35, "@"),
    ("Land", 12, "@"),
    ("PLZ", 8, "@"),
    ("Ort", 20, "@"),
    ("Strasse", 25, "@"),
    ("HausNr", 8, "@"),
    ("BriefAnrede", 35, "@"),
    ("AdrZeile1", 30, "@"),
    ("AdrZeile2", 30, "@"),
    ("AdrZeile3", 30, "@"),
    ("AdrZeile4", 30, "@"),
    ("AdrZeile5", 30, "@"),
    ("AdrZeile6", 30, "@"),
    ("austritt", 12, "DD.MM.YYYY"),
    ("summe_anteile", 14, '#,##0.00 "€"'),
    ("anz_anteile", 10, "0"),
    ("jahr_report", 10, "0"),
    ("Verstorben", 12, "DD.MM.YYYY"),
)

EVENT_COLUMNS: Columns = (
    ("Vorgang", 24, "@"),
    ("Nr.", 8, "0"),
    ("Name", 35, "@"),
    ("Datum", 12, "DD.MM.YYYY"),
    ("Anteile", 10, "0"),
    ("Betrag", 14, '#,##0.00 "€"'),
    ("Gegenkonto", 12, "0"),
)


def members_geng(rows: list[GengRow], day: date, warnings: list[str]) -> bytes:
    """Mitgliederliste nach GenG als .xlsx, eine Zeile je Mitglied."""
    workbook, sheet = _new_sheet("Mitgliederliste", "Mitgliederliste nach § 30 GenG", day, warnings, GENG_COLUMNS)
    for row in rows:
        # Betrag in Euro: Excel rechnet mit Kommazahlen, die App mit Cent.
        _append(
            sheet,
            GENG_COLUMNS,
            [row.member_number, row.name, row.address, row.entry_date, row.amount / 100, row.shares],
        )
    return _save(workbook)


def members_assembly(rows: list[AssemblyRow], day: date, warnings: list[str]) -> bytes:
    """Liste zur Generalversammlung als .xlsx, zum Ausdrucken und Unterschreiben."""
    workbook, sheet = _new_sheet(
        "Generalversammlung", "Anwesenheitsliste Generalversammlung", day, warnings, ASSEMBLY_COLUMNS
    )
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


def members_mailing(rows: list[MailingRow], day: date) -> bytes:
    """Seriendruck-Liste als .xlsx.

    Anders als die anderen Listen ohne Titel, Stichtag und Warnung: Word liest beim Seriendruck die
    erste Zeile als Feldnamen. Das Jahr des Stichtags steht deshalb als Spalte `jahr_report` in jeder
    Zeile, Warnungen zeigt nur die Seite „Reports“.
    """
    workbook = Workbook()
    sheet = workbook.active
    assert isinstance(sheet, Worksheet)
    sheet.title = "Seriendruck"
    for index, (header, width, _) in enumerate(MAILING_COLUMNS, start=1):
        sheet.cell(row=1, column=index, value=header).font = Font(bold=True)
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row in rows:
        values: list[object] = [
            row.member_number,
            row.name,
            row.country,
            row.postal_code,
            row.city,
            row.street,
            row.house_number,
            row.salutation,
            *row.address_lines,
            row.exit_date,
            row.amount / 100,
            row.shares,
            day.year,
            row.date_of_death,
        ]
        _append(sheet, MAILING_COLUMNS, values)
    sheet.freeze_panes = "A2"
    return _save(workbook)


def fiscal_year_events(rows: list[EventRow], year: int) -> bytes:
    """Auswertung der Vorgänge eines Geschäftsjahres als .xlsx, mit Filter in der Kopfzeile."""
    workbook, sheet = _new_sheet("Vorgänge", f"Vorgänge im Geschäftsjahr {year}", None, [], EVENT_COLUMNS)
    sheet["A2"] = f"Zeitraum: 01.01.{year} bis 31.12.{year}"
    for row in rows:
        amount = row.amount / 100 if row.amount is not None else None
        values = [row.event, row.member_number, row.name, row.day, row.shares, amount, row.counter_account]
        _append(sheet, EVENT_COLUMNS, values)
    # Autofilter: In jeder Spalte der Kopfzeile erscheint in Excel ein Pfeil zum Filtern, z. B. nach Vorgang.
    last_column = get_column_letter(len(EVENT_COLUMNS))
    sheet.auto_filter.ref = f"A{HEADER_ROW}:{last_column}{max(sheet.max_row, HEADER_ROW)}"
    return _save(workbook)


def _new_sheet(
    sheet_title: str, title: str, day: date | None, warnings: list[str], columns: Columns
) -> tuple[Workbook, Worksheet]:
    """Neue Arbeitsmappe mit Titel, „Stichtag: TT.MM.JJJJ“ (ohne `day` leer), ggf. Warnung und Kopfzeile."""
    workbook = Workbook()
    sheet = workbook.active
    assert isinstance(sheet, Worksheet)  # eine neue Arbeitsmappe hat immer ein Blatt
    sheet.title = sheet_title
    sheet["A1"] = title
    sheet["A1"].font = Font(bold=True, size=14)
    if day is not None:
        sheet["A2"] = f"Stichtag: {day:%d.%m.%Y}"
    if warnings:
        # Auch auf dem Ausdruck soll zu sehen sein, dass die Liste unter Vorbehalt steht.
        sheet["A3"] = " ".join(warnings)
        sheet["A3"].font = Font(bold=True, color="C00000")  # dunkelrot
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
