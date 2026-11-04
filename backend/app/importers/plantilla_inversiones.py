"""Plantilla propia de Caudal para cargar el historial de inversiones (DISENO §7.4).

Columnas: fecha; identificador; nombre; tipo_producto; tipo_movimiento; unidades; importe;
moneda; comision; nota. Se aceptan .xlsx (hoja "Operaciones", o la primera) y .csv (con ; , o
tabulador; en UTF-8 o en la codificación de Excel en Windows).

Este módulo solo lee y escribe el archivo; no toca la BD (eso es app/investments/importer.py).
`nombre`, `tipo_producto` y `nota` son de ayuda para quien rellena la plantilla: no se guardan.
"""

import codecs
import csv
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from app.importers.base import (
    ImportFormatError,
    Row,
    RowError,
    UnreadableValueError,
    data_rows,
    header_map,
    normalize_text,
    open_workbook,
    parse_date,
    require_headers,
    row_error,
    show,
)

COLUMNS = [
    "fecha",
    "identificador",
    "nombre",
    "tipo_producto",
    "tipo_movimiento",
    "unidades",
    "importe",
    "moneda",
    "comision",
    "nota",
]
REQUIRED = ["fecha", "identificador", "tipo_movimiento", "importe"]
SHEET = "Operaciones"
MAX_ROWS = 5000

KINDS = {
    "COMPRA": "buy",
    "VENTA": "sell",
    "DIVIDENDO": "dividend",
    "COMISION": "fee",
    "BUY": "buy",
    "SELL": "sell",
    "DIVIDEND": "dividend",
    "FEE": "fee",
}

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
# 1.234,56 · 1234,56 · 1234.56 · 0,00000012 (sin signo: todo va en positivo)
_NUMBER = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:[.,](\d+))?$")


@dataclass(frozen=True)
class TemplateOperation:
    row: int
    date: date
    identifier: str
    kind: str
    shares: Decimal
    amount_eur: Decimal
    fee_eur: Decimal | None


@dataclass
class TemplateResult:
    operations: list[TemplateOperation] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)


# ---------- Leer valores ----------


def parse_number(value: Any, decimals: int) -> Decimal:
    """Número en positivo, con coma o punto decimal, y como mucho `decimals` decimales."""
    if isinstance(value, bool):
        raise UnreadableValueError("no es un número")
    if isinstance(value, int | float | Decimal):
        number = Decimal(str(value))
    elif isinstance(value, str):
        text = "".join(value.split()).removesuffix("€")
        if "," in text and "." in text:  # 1.234,56: el punto es de miles
            text = text.replace(".", "")
        match = _NUMBER.match(text)
        if not match:
            raise UnreadableValueError("no es un número (usa, por ejemplo, 1234,56)")
        integer, fraction = match.groups()
        number = Decimal(f"{integer.replace('.', '')}.{fraction or '0'}")
    else:
        raise UnreadableValueError("no es un número")
    try:
        quantized = number.quantize(Decimal(1).scaleb(-decimals))
    except InvalidOperation:
        raise UnreadableValueError("es demasiado grande") from None
    if quantized != number:
        raise UnreadableValueError(f"tiene más de {decimals} decimales")
    if quantized < 0:
        raise UnreadableValueError("va en positivo: el tipo de movimiento dice si entra o sale")
    return quantized


def parse_template_date(value: Any) -> date:
    if isinstance(value, str) and (match := _ISO_DATE.match(value.strip())):
        try:
            return date(*(int(g) for g in match.groups()))
        except ValueError:
            pass
    return parse_date(value)  # dd/mm/aaaa o fecha de Excel


# ---------- Abrir el archivo ----------


def _csv_rows(data: bytes) -> tuple[dict[str, int], list[Row]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    first_line = text.splitlines()[0] if text.strip() else ""
    delimiter = max(";,\t", key=first_line.count)
    lines = list(csv.reader(StringIO(text), delimiter=delimiter))
    if not lines:
        raise ImportFormatError("El archivo está vacío")
    headers = {" ".join(h.split()).casefold(): i for i, h in enumerate(lines[0]) if h.strip()}
    rows = [Row(n, tuple(values), headers) for n, values in enumerate(lines[1:], start=2)]
    return headers, [row for row in rows if not row.is_blank()]


def _xlsx_rows(data: bytes) -> tuple[dict[str, int], list[Row]]:
    workbook = open_workbook(data)
    sheet = workbook[SHEET] if SHEET in workbook.sheetnames else workbook.worksheets[0]
    headers = header_map(sheet)
    return headers, data_rows(sheet, headers)


def read_template(data: bytes) -> TemplateResult:
    """Lee la plantilla. Lanza ImportFormatError si el archivo entero no vale."""
    is_xlsx = data[:4] == b"PK\x03\x04"  # un .xlsx es un zip
    headers, rows = _xlsx_rows(data) if is_xlsx else _csv_rows(data)
    try:
        require_headers(headers, REQUIRED)
    except ImportFormatError as error:
        raise ImportFormatError(f"{error}: ¿es la plantilla de inversiones de Caudal?") from None
    if len(rows) > MAX_ROWS:
        raise ImportFormatError(f"La plantilla tiene más de {MAX_ROWS} filas: divídela en dos")
    result = TemplateResult()
    for row in rows:
        operation = _parse_row(row, result.errors)
        if operation is not None:
            result.operations.append(operation)
    return result


def _parse_row(row: Row, errors: list[RowError]) -> TemplateOperation | None:
    def read(column: str, what: str, parse, *, optional: bool = False):
        value = row.get(column)
        if value is None and optional:
            return None
        try:
            if value is None:
                raise UnreadableValueError("está vacío")
            return parse(value)
        except UnreadableValueError as problem:
            errors.append(row_error(row.number, column, value, what, problem))
            raise

    def kind(value: Any) -> str:
        found = KINDS.get(normalize_text(show(value)))
        if found is None:
            raise UnreadableValueError("usa compra, venta, dividendo o comision")
        return found

    def currency(value: Any) -> str:
        if normalize_text(show(value)) not in ("EUR", "€"):
            raise UnreadableValueError("el importe va en euros: escribe EUR o déjalo vacío")
        return "EUR"

    try:
        day = read("fecha", "la fecha", parse_template_date)
        identifier = read("identificador", "el identificador", lambda v: show(v).strip().upper())
        movement = read("tipo_movimiento", "el tipo de movimiento", kind)
        shares = read("unidades", "las unidades", lambda v: parse_number(v, 8), optional=True)
        amount = read("importe", "el importe", lambda v: parse_number(v, 2))
        read("moneda", "la moneda", currency, optional=True)
        fee = read("comision", "la comisión", lambda v: parse_number(v, 2), optional=True)
    except UnreadableValueError:
        return None
    return TemplateOperation(
        row=row.number,
        date=day,
        identifier=identifier,
        kind=movement,
        shares=shares if shares is not None else Decimal(0),
        amount_eur=amount,
        fee_eur=fee,
    )


# ---------- Escribir la plantilla vacía ----------

INSTRUCTIONS = [
    ["Cómo rellenar la plantilla de inversiones de Caudal"],
    [],
    ["1. Crea antes los productos en Caudal (Inversiones → Productos)."],
    ["2. Rellena la hoja «Operaciones»: una fila por compra, venta, dividendo o comisión."],
    ["3. Importa el archivo en Caudal eligiendo la cuenta (Trade Republic, Scalable…)."],
    [],
    ["Columna", "Qué poner"],
    ["fecha", "dd/mm/aaaa (o una fecha de Excel)"],
    ["identificador", "ISIN, símbolo de Yahoo (SXR8.DE) o ticker de un producto que ya tengas"],
    ["nombre", "Opcional, solo para que te aclares: no se guarda"],
    ["tipo_producto", "Opcional, solo de ayuda: no se guarda"],
    ["tipo_movimiento", "compra, venta, dividendo o comision"],
    ["unidades", "Participaciones (en compras y ventas). Hasta 8 decimales"],
    ["importe", "Total en euros, en positivo: en una compra, lo que pagaste con comisiones"],
    ["moneda", "EUR (o vacío)"],
    ["comision", "Opcional: la parte del importe que fue comisión"],
    ["nota", "Opcional: no se guarda"],
    [],
    ["Si importas el mismo archivo dos veces, las filas repetidas no se duplican."],
]

# Datos inventados (ISIN de ejemplo que no existe): enseñan el formato
EXAMPLE = [
    [
        "03/03/2025",
        "XX0000000001",
        "ETF de ejemplo",
        "etf",
        "compra",
        "0,25",
        "150,00",
        "EUR",
        "1,00",
        "Inventado",
    ],
    [
        "01/04/2025",
        "XX0000000001",
        "ETF de ejemplo",
        "etf",
        "compra",
        "0,26",
        "150,00",
        "EUR",
        "1,00",
        "",
    ],
    ["15/06/2025", "XX0000000001", "ETF de ejemplo", "etf", "dividendo", "", "0,80", "EUR", "", ""],
]


def build_template(kind: str) -> bytes:
    """Plantilla vacía: "xlsx" (con instrucciones y un ejemplo inventado) o "csv" (cabeceras)."""
    if kind == "csv":
        out = StringIO()
        csv.writer(out, delimiter=";", lineterminator="\r\n").writerow(COLUMNS)
        return codecs.BOM_UTF8 + out.getvalue().encode("utf-8")  # con BOM: Excel lo abre en UTF-8
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET
    sheet.append(COLUMNS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    instructions = workbook.create_sheet("Instrucciones")
    for line in INSTRUCTIONS:
        instructions.append(line)
    instructions["A1"].font = Font(bold=True)
    example = workbook.create_sheet("Ejemplo (no se importa)")
    example.append(COLUMNS)
    for line in EXAMPLE:
        example.append(line)
    out = BytesIO()
    workbook.save(out)
    return out.getvalue()
