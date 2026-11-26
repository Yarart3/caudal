"""Exportar a Excel (Fase 5): los movimientos de la lista, con sus filtros.

Dos hojas:
- **Movimientos:** fecha (fecha de Excel), cuenta, concepto, categoría, importe (número con
  formato de euros, para poder sumar), tipo, estado, etiquetas y nota.
- **Resumen:** cuándo se exportó, los filtros, cuántos movimientos hay y los ingresos y gastos
  sin las transferencias internas (como los totales de la app, DISENO 9.1).

Seguridad: todos los textos se guardan como texto. openpyxl toma por fórmula cualquier texto
que empiece por «=», y un concepto del banco podría empezar así.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Font
from openpyxl.worksheet.worksheet import Worksheet

from app.models import Transaction

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TZ = ZoneInfo("Europe/Madrid")
EUR_FORMAT = '#,##0.00 "€";-#,##0.00 "€"'
DATE_FORMAT = "DD/MM/YYYY"
STATUS_LABELS = {
    "auto": "Automática",
    "manual": "Puesta a mano",
    "review": "Por revisar",
    "internal": "Transferencia interna",
}
COLUMNS = (
    ("Fecha", 12),
    ("Cuenta", 16),
    ("Concepto", 40),
    ("Categoría", 22),
    ("Importe", 14),
    ("Tipo", 12),
    ("Estado", 20),
    ("Etiquetas", 24),
    ("Nota", 40),
)


@dataclass(frozen=True)
class ExportRow:
    tx: Transaction
    account_name: str
    category_name: str | None


def _put_text(cell: Cell, value: str) -> None:
    """Texto que nunca se interpreta como fórmula."""
    cell.value = value
    cell.data_type = "s"


def _kind(tx: Transaction) -> str:
    if tx.is_internal_transfer:
        return "Interna"
    return "Ingreso" if tx.amount > 0 else "Gasto"


def _header(sheet: Worksheet, names: list[str]) -> None:
    sheet.append(names)
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True)


def _movements_sheet(sheet: Worksheet, rows: list[ExportRow]) -> None:
    sheet.title = "Movimientos"
    _header(sheet, [name for name, _ in COLUMNS])
    for index, (_, width) in enumerate(COLUMNS, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    sheet.freeze_panes = "A2"
    for number, row in enumerate(rows, start=2):
        tx = row.tx
        status = "internal" if tx.is_internal_transfer else tx.category_status
        date_cell = sheet.cell(row=number, column=1, value=tx.date)
        date_cell.number_format = DATE_FORMAT
        _put_text(sheet.cell(row=number, column=2), row.account_name)
        _put_text(sheet.cell(row=number, column=3), tx.description)
        _put_text(sheet.cell(row=number, column=4), row.category_name or "")
        amount = sheet.cell(row=number, column=5, value=tx.amount)
        amount.number_format = EUR_FORMAT
        _put_text(sheet.cell(row=number, column=6), _kind(tx))
        _put_text(sheet.cell(row=number, column=7), STATUS_LABELS[status])
        _put_text(sheet.cell(row=number, column=8), ", ".join(tx.tags))
        _put_text(sheet.cell(row=number, column=9), tx.note or "")


def _summary_sheet(sheet: Worksheet, rows: list[ExportRow], filters: list[str]) -> None:
    counted = [r.tx.amount for r in rows if not r.tx.is_internal_transfer]
    income = sum((a for a in counted if a > 0), Decimal("0"))
    expenses = sum((-a for a in counted if a < 0), Decimal("0"))
    internal = sum(1 for r in rows if r.tx.is_internal_transfer)

    _header(sheet, ["Caudal · exportación de movimientos", ""])
    lines: list[tuple[str, object]] = [
        ("Exportado el", datetime.now(TZ).strftime("%d/%m/%Y %H:%M")),
        ("Filtros", "; ".join(filters) if filters else "Ninguno (todos los movimientos)"),
        ("Movimientos", len(rows)),
        ("Transferencias internas (no cuentan)", internal),
        ("Ingresos", income),
        ("Gastos", expenses),
        ("Ingresos − gastos", income - expenses),
    ]
    for label, value in lines:
        sheet.append([label])
        cell = sheet.cell(row=sheet.max_row, column=2)
        if isinstance(value, str):
            _put_text(cell, value)
        else:
            cell.value = value
            if isinstance(value, Decimal):
                cell.number_format = EUR_FORMAT
    sheet.column_dimensions["A"].width = 36
    sheet.column_dimensions["B"].width = 48


def build_transactions_xlsx(rows: list[ExportRow], filters: list[str]) -> bytes:
    workbook = Workbook()
    _movements_sheet(workbook.active, rows)
    _summary_sheet(workbook.create_sheet("Resumen"), rows, filters)
    out = BytesIO()
    workbook.save(out)
    return out.getvalue()
