"""Fase 3, parte 3.3c: lectura y escritura de la plantilla de inversiones (sin BD)."""

import codecs
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from app.importers import plantilla_inversiones as plantilla
from app.importers.base import ImportFormatError, UnreadableValueError
from app.importers.plantilla_inversiones import (
    COLUMNS,
    build_template,
    parse_number,
    parse_template_date,
    read_template,
)

HEADER = (
    "fecha;identificador;nombre;tipo_producto;tipo_movimiento;unidades;importe;moneda;comision;nota"
)


def csv_file(*lines: str, header: str = HEADER, encoding: str = "utf-8") -> bytes:
    return "\r\n".join([header, *lines]).encode(encoding)


# ---------------------------------------------------------------- valores


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [
        ("1.234,56", 2, "1234.56"),
        ("1234,56", 2, "1234.56"),
        ("1234.56", 2, "1234.56"),
        ("150,00 €", 2, "150.00"),
        (" 7 ", 2, "7.00"),
        ("0,00000012", 8, "0.00000012"),
        ("1,234", 8, "1.23400000"),
        (12, 2, "12.00"),
        (0.25, 8, "0.25000000"),
        (Decimal("3.1"), 2, "3.10"),
    ],
)
def test_numbers_are_read(value, decimals: int, expected: str) -> None:
    assert parse_number(value, decimals) == Decimal(expected)


@pytest.mark.parametrize(
    ("value", "decimals", "message"),
    [
        ("-10,00", 2, "no es un número"),
        ("1,234", 2, "más de 2 decimales"),
        ("0,123456789", 8, "más de 8 decimales"),
        ("abc", 2, "no es un número"),
        ("1,5,3", 2, "no es un número"),
        (-1, 2, "va en positivo"),
        (True, 2, "no es un número"),
    ],
)
def test_bad_numbers(value, decimals: int, message: str) -> None:
    with pytest.raises(UnreadableValueError, match=message):
        parse_number(value, decimals)


def test_dates_in_three_forms() -> None:
    assert parse_template_date("2025-03-03") == date(2025, 3, 3)
    assert parse_template_date("03/03/2025") == date(2025, 3, 3)
    assert parse_template_date(datetime(2025, 3, 3, 0, 0)) == date(2025, 3, 3)  # noqa: DTZ001
    with pytest.raises(UnreadableValueError):
        parse_template_date("2025-02-30")


# ---------------------------------------------------------------- CSV


def test_csv_with_semicolons() -> None:
    result = read_template(
        csv_file(
            "03/03/2025;sxr8.de;Mi ETF;etf;compra;0,25;150,00;EUR;1,00;primera",
            "15/06/2025;IE00B5BMR087;;;Dividendo;;0,80;;;",
        )
    )
    assert result.errors == []
    first, second = result.operations
    assert (first.row, first.date, first.identifier, first.kind) == (
        2,
        date(2025, 3, 3),
        "SXR8.DE",
        "buy",
    )
    assert (first.shares, first.amount_eur, first.fee_eur) == (
        Decimal("0.25000000"),
        Decimal("150.00"),
        Decimal("1.00"),
    )
    assert (second.kind, second.shares, second.fee_eur) == ("dividend", Decimal(0), None)


def test_csv_with_commas_bom_and_blank_lines() -> None:
    header = HEADER.replace(";", ",")
    text = "\r\n".join([header, "", '2025-03-03,X.DE,,,venta,1,"1.000,50",EUR,,', ""])
    result = read_template(codecs.BOM_UTF8 + text.encode("utf-8"))
    assert result.errors == []
    assert [(o.kind, o.amount_eur) for o in result.operations] == [("sell", Decimal("1000.50"))]


def test_csv_from_excel_on_windows() -> None:
    data = csv_file("03/03/2025;X.DE;;;Comisión;;1,00;;;cuota de gestión", encoding="cp1252")
    assert [o.kind for o in read_template(data).operations] == ["fee"]


def test_columns_by_name_in_any_order() -> None:
    data = "Importe;Tipo_Movimiento;Identificador;Fecha;Unidades\n10;compra;X.DE;01/02/2025;1\n"
    operations = read_template(data.encode()).operations
    assert [(o.identifier, o.amount_eur) for o in operations] == [("X.DE", Decimal("10.00"))]


def test_missing_column_rejects_the_file() -> None:
    with pytest.raises(ImportFormatError, match="«importe».*plantilla de inversiones"):
        read_template(b"fecha;identificador;tipo_movimiento\n01/01/2025;X;compra\n")


def test_too_many_rows(monkeypatch) -> None:
    monkeypatch.setattr(plantilla, "MAX_ROWS", 2)
    lines = ["01/01/2025;X;;;compra;1;10;;;"] * 3
    with pytest.raises(ImportFormatError, match="más de 2 filas"):
        read_template(csv_file(*lines))


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("31/02/2025;X;;;compra;1;10;;;", "Fila 2: no se ha podido leer la fecha «31/02/2025»"),
        (";X;;;compra;1;10;;;", "Fila 2: no se ha podido leer la fecha (está vacío)"),
        ("01/01/2025;X;;;regalo;1;10;;;", "usa compra, venta, dividendo o comision"),
        ("01/01/2025;X;;;compra;1;10;USD;;", "el importe va en euros"),
        ("01/01/2025;X;;;compra;1;-10;;;", "Fila 2: no se ha podido leer el importe «-10»"),
        ("01/01/2025;X;;;compra;1;;;;", "el importe (está vacío)"),
        ("01/01/2025;X;;;compra;uno;10;;;", "las unidades «uno»"),
        ("01/01/2025;X;;;compra;1;10;;0,001;", "la comisión «0,001»"),
    ],
)
def test_row_errors_do_not_stop_the_rest(line: str, message: str) -> None:
    result = read_template(csv_file(line, "02/01/2025;X;;;compra;1;10;;;"))
    assert len(result.errors) == 1
    assert message in result.errors[0].message
    assert [o.row for o in result.operations] == [3]


# ---------------------------------------------------------------- Excel


def test_xlsx_template_has_three_sheets_and_empty_operations() -> None:
    workbook = load_workbook(BytesIO(build_template("xlsx")))
    assert workbook.sheetnames == ["Operaciones", "Instrucciones", "Ejemplo (no se importa)"]
    rows = list(workbook["Operaciones"].iter_rows(values_only=True))
    assert rows == [tuple(COLUMNS)]
    example = list(workbook["Ejemplo (no se importa)"].iter_rows(values_only=True))
    assert len(example) == 4
    assert all(row[1] == "XX0000000001" for row in example[1:])  # ISIN inventado


def test_filled_xlsx_template_is_read_from_its_sheet() -> None:
    workbook = load_workbook(BytesIO(build_template("xlsx")))
    sheet = workbook["Operaciones"]
    excel_date = datetime(2025, 3, 3)  # noqa: DTZ001 (Excel guarda las fechas sin zona horaria)
    sheet.append([excel_date, "X.DE", "ETF", "etf", "compra", 0.25, 150, "EUR", 1, None])
    sheet.append([None] * 10)
    sheet.append(["01/04/2025", "X.DE", None, None, "venta", "0,1", "70,5", None, None, None])
    out = BytesIO()
    workbook.save(out)
    result = read_template(out.getvalue())
    assert result.errors == []
    assert [(o.row, o.kind, o.shares, o.amount_eur) for o in result.operations] == [
        (2, "buy", Decimal("0.25000000"), Decimal("150.00")),
        (4, "sell", Decimal("0.10000000"), Decimal("70.50")),
    ]


def test_xlsx_without_operations_sheet_uses_the_first() -> None:
    workbook = Workbook()
    workbook.active.append(COLUMNS)
    workbook.active.append(["01/04/2025", "X.DE", None, None, "compra", 1, 10, None, None, None])
    out = BytesIO()
    workbook.save(out)
    assert len(read_template(out.getvalue()).operations) == 1


def test_broken_xlsx() -> None:
    with pytest.raises(ImportFormatError, match="no es un Excel"):
        read_template(b"PK\x03\x04 esto no es un zip")


def test_csv_template_is_only_the_header_with_bom() -> None:
    data = build_template("csv")
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8-sig") == HEADER + "\r\n"
    assert read_template(data).operations == []
