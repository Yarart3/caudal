"""Lectura de extractos (Fase 1b, parte 1.1): sin BD, con los ejemplos de samples/ y con
archivos pequeños creados aquí para los casos que los ejemplos no cubren."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.importers import check_format, detect_format
from app.importers.base import (
    ImportFormatError,
    UnreadableValueError,
    normalize_text,
    open_workbook,
    parse_date,
    parse_es_amount,
    to_money,
)

# En Docker, docker-compose.yml monta ./samples en /samples (= dos niveles por encima de tests/)
SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN_HEADERS = ["Concepto", "Fecha", "Importe", "Saldo"]
WISE_HEADERS = [
    "Documento de identidad",
    "Fecha",
    "Fecha y hora",
    "Cantidad",
    "Divisa",
    "Descripción",
    "Referencia del pago",
    "Saldo corriente",
    "Cambiar desde",
    "Cambiar a",
    "Comercio",
    "Nombre del pagador",
    "Nombre del beneficiario",
    "Tipo de transacción",
    "Tipo de detalles de transacción",
]


def _sample(name: str):
    path = SAMPLES / name
    assert path.is_file(), f"No se encuentra {path}: ¿está montado samples/ en docker-compose.yml?"
    return open_workbook(path.read_bytes())


def _xlsx(headers: list[str], rows: list[list[object]], title: str | None = None):
    """Excel pequeño en memoria con las cabeceras en la fila 1, como los de los bancos."""
    wb = Workbook()
    ws = wb.active
    if title:
        ws.title = title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return open_workbook(buffer.getvalue())


def _wise_row(**values: object) -> list[object]:
    """Fila de Wise con '' en las celdas vacías (así vienen en el extracto real)."""
    return [values.get(h, "") for h in WISE_HEADERS]


# ---------- Normalización ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("-14,50EUR", "-14.50"),
        ("-69,73EUR", "-69.73"),
        ("2,00EUR", "2.00"),
        ("-23EUR", "-23.00"),  # imagin siempre da 2 decimales; esto es por robustez
        ("-0,5EUR", "-0.50"),  # ídem
        ("1.234,56EUR", "1234.56"),
        ("-12.345.678,90EUR", "-12345678.90"),
        ("-23 EUR", "-23.00"),
        ("-7,10 €", "-7.10"),
    ],
)
def test_parse_es_amount(text: str, expected: str) -> None:
    assert parse_es_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["abc", "", "-23,4,5EUR", "1,234.56EUR", "12,00USD", "1.23EUR"])
def test_parse_es_amount_rejects(text: str) -> None:
    with pytest.raises(UnreadableValueError):
        parse_es_amount(text)


def test_to_money_from_excel_numbers() -> None:
    assert to_money(-14.55) == Decimal("-14.55")
    assert to_money(664.35) == Decimal("664.35")
    assert to_money(-7) == Decimal("-7.00")
    with pytest.raises(UnreadableValueError):
        to_money(0.1 + 0.2)  # 0.30000000000000004: no es un importe en euros
    with pytest.raises(UnreadableValueError):
        to_money(None)


def test_parse_date() -> None:
    assert parse_date("29/09/2026") == date(2026, 9, 29)
    assert parse_date("1/10/2026") == date(2026, 10, 1)
    assert parse_date(datetime(2026, 9, 27)) == date(2026, 9, 27)  # noqa: DTZ001
    assert parse_date(46294) == date(2026, 9, 29)  # número de serie de Excel
    for bad in ["31/02/2026", "2026-09-29", "", None, True]:
        with pytest.raises(UnreadableValueError):
            parse_date(bad)


def test_normalize_text() -> None:
    assert normalize_text("  enviament   de dine ") == "ENVIAMENT DE DINE"
    assert normalize_text("Cafè Ñandú") == "CAFE NANDU"


# ---------- Ejemplos de samples/ ----------


def test_imagin_sample() -> None:
    wb = _sample("imagin_ejemplo.xlsx")
    result = check_format(wb, "imagin").parse(wb)

    assert result.errors == []
    assert result.warnings == []  # el saldo cuadra fila a fila
    assert len(result.transactions) == 8
    first = result.transactions[0]
    assert (first.row, first.date, first.description, first.amount, first.balance) == (
        2,
        date(2026, 9, 29),
        "WWW.AMAZON",
        Decimal("-69.73"),
        Decimal("67.23"),
    )
    by_row = {t.row: t for t in result.transactions}
    assert by_row[4].description == "enviament de dine"  # se guarda tal cual, en minúsculas
    assert by_row[4].amount == Decimal("-50.00")  # la pareja del +50 de Wise del 27/09
    # Dos compras iguales el mismo día: solo las distingue el saldo
    assert (by_row[5].description, by_row[5].amount) == (by_row[6].description, by_row[6].amount)
    assert by_row[5].balance != by_row[6].balance
    assert by_row[7].amount == Decimal("2.00")  # BIZUM REBUT: ingreso
    assert (by_row[9].description, by_row[9].amount) == ("TRANSFER IMMEDIATA", Decimal("150.00"))
    assert all(t.external_id is None for t in result.transactions)
    assert (result.closing_balance, result.closing_date) == (Decimal("67.23"), date(2026, 9, 29))


def test_wise_sample() -> None:
    wb = _sample("wise_ejemplo.xlsx")
    result = check_format(wb, "wise").parse(wb)

    assert result.errors == []
    assert result.warnings == []  # su saldo corriente cuadra fila a fila
    assert len(result.transactions) == 4
    card, deposit, restaurant, _ = result.transactions
    assert card.description == "Tienda Ejemplo CIUDAD"  # Comercio, no la Descripción larga
    assert card.amount == Decimal("-7.00")
    assert card.external_id == "CARD-1000000004"
    # Ingreso desde imagin: sin comercio, el concepto es el pagador y lleva la pista de imagin
    assert deposit.amount == Decimal("50.00")
    assert deposit.description == "Nombre Ejemplo"
    assert deposit.transfer_hint == "imagin"
    # Pago que vende participaciones del fondo en la misma fila: gasto normal
    assert restaurant.amount == Decimal("-12.40")
    assert restaurant.transfer_hint is None
    assert (result.closing_balance, result.closing_date) == (Decimal("147.45"), date(2026, 9, 30))


def test_detect_and_wrong_bank() -> None:
    imagin = _sample("imagin_ejemplo.xlsx")
    wise = _sample("wise_ejemplo.xlsx")
    assert detect_format(imagin).name == "imagin"
    assert detect_format(wise).name == "wise"
    with pytest.raises(ImportFormatError, match="parece de Wise, pero has elegido una cuenta de"):
        check_format(wise, "imagin")
    with pytest.raises(ImportFormatError, match="parece de imagin"):
        check_format(imagin, "wise")


# ---------- Casos que no están en los ejemplos ----------


def test_not_an_excel() -> None:
    with pytest.raises(ImportFormatError, match="no es un Excel"):
        open_workbook(b"Concepto;Fecha;Importe\n")


def test_unknown_file() -> None:
    wb = _xlsx(["Date", "Amount"], [["2026-09-29", -1]])
    assert detect_format(wb) is None
    with pytest.raises(ImportFormatError, match="no tiene el formato del extracto de imagin"):
        check_format(wb, "imagin")


def test_imagin_missing_column() -> None:
    wb = _xlsx(["Concepto", "Fecha", "Saldo"], [["BON AREA", "26/09/2026", "63,16EUR"]])
    with pytest.raises(ImportFormatError, match="No se encuentra la columna «Importe»"):
        check_format(wb, "imagin").parse(wb)


def test_imagin_unreadable_row_does_not_abort() -> None:
    wb = _xlsx(
        IMAGIN_HEADERS,
        [
            ["BON AREA", "26/09/2026", "-1,94EUR", "63,16EUR"],
            ["MERCADONA", "26/09/2026", "-23,x0EUR", "40,16EUR"],
            ["", None, None, None],  # fila vacía: se salta sin error
            ["BIZUM REBUT", "32/09/2026", "2,00EUR", "65,10EUR"],
            ["WWW.AMAZON", "25/09/2026", "-5,00EUR", "63,10EUR"],
        ],
    )
    result = check_format(wb, "imagin").parse(wb)

    assert [t.row for t in result.transactions] == [2, 6]
    assert [(e.row, e.field, e.value) for e in result.errors] == [
        (3, "Importe", "-23,x0EUR"),
        (5, "Fecha", "32/09/2026"),
    ]
    assert result.errors[0].message.startswith(
        "Fila 3: no se ha podido leer el importe «-23,x0EUR»"
    )


def test_imagin_identical_purchases_are_both_read() -> None:
    """Dos compras iguales el mismo día: las dos se leen y solo las distingue el saldo."""
    wb = _xlsx(
        IMAGIN_HEADERS,
        [
            ["MERCADONA", "27/09/2026", "-2,45EUR", "37,71EUR"],
            ["MERCADONA", "27/09/2026", "-2,45EUR", "40,16EUR"],
            ["BON AREA", "26/09/2026", "-1,94EUR", "42,61EUR"],
        ],
    )
    result = check_format(wb, "imagin").parse(wb)

    assert result.errors == []
    assert result.warnings == []  # este extracto sí cuadra
    first, second, _ = result.transactions
    assert (first.date, first.description, first.amount) == (
        second.date,
        second.description,
        second.amount,
    )
    assert first.balance != second.balance
    assert result.closing_balance == Decimal("37.71")


def test_imagin_balance_gap_warns() -> None:
    wb = _xlsx(
        IMAGIN_HEADERS,
        [
            ["MERCADONA", "27/09/2026", "-2,45EUR", "37,71EUR"],
            # aquí falta un movimiento de -10,00
            ["BON AREA", "26/09/2026", "-1,94EUR", "50,16EUR"],
            ["BIZUM REBUT", "25/09/2026", "2,00EUR", "52,10EUR"],
        ],
    )
    result = check_format(wb, "imagin").parse(wb)

    assert len(result.transactions) == 3
    assert result.warnings == [
        "El saldo de imagin no cuadra entre la fila 3 y la fila 2: tendría que ser 47,71 € "
        "y el extracto dice 37,71 €. Puede faltar algún movimiento."
    ]


def test_imagin_oldest_first_also_checks() -> None:
    wb = _xlsx(
        IMAGIN_HEADERS,
        [
            ["BIZUM REBUT", "25/09/2026", "2,00EUR", "52,10EUR"],
            ["BON AREA", "26/09/2026", "-1,94EUR", "50,16EUR"],
            ["MERCADONA", "27/09/2026", "-2,45EUR", "47,71EUR"],
        ],
    )
    result = check_format(wb, "imagin").parse(wb)
    assert result.warnings == []
    assert (result.closing_balance, result.closing_date) == (Decimal("47.71"), date(2026, 9, 27))


def test_wise_rows() -> None:
    day = datetime(2026, 10, 1)  # noqa: DTZ001
    common = {"Fecha": day, "Divisa": "EUR", "Tipo de detalles de transacción": "CARD"}
    wb = _xlsx(
        WISE_HEADERS,
        [
            _wise_row(
                **common,
                **{
                    "Documento de identidad": "CARD-1",
                    "Cantidad": -3.5,
                    "Descripción": "Transacción con tarjeta de 3,50 EUR emitida por Bar Ejemplo",
                    "Tipo de transacción": "DEBIT",
                },
            ),
            _wise_row(
                **common,
                **{
                    "Documento de identidad": "CARD-1",  # ID repetido en el mismo archivo
                    "Cantidad": -1,
                    "Comercio": "Kiosco Ejemplo",
                    "Tipo de transacción": "DEBIT",
                },
            ),
            _wise_row(
                **{
                    "Documento de identidad": "TRANSFER-2",
                    "Fecha": day,
                    "Divisa": "EUR",
                    "Cantidad": -20,
                    "Descripción": "Enviado",
                    "Nombre del beneficiario": "Persona Ejemplo",
                    "Tipo de transacción": "DEBIT",
                    "Tipo de detalles de transacción": "TRANSFER",
                }
            ),
            _wise_row(
                **{
                    "Documento de identidad": "BALANCE-3",
                    "Fecha": day,
                    "Divisa": "EUR",
                    "Cantidad": -10,
                    "Descripción": "Conversión",
                    "Cambiar desde": "EUR",
                    "Cambiar a": "USD",
                    "Tipo de transacción": "DEBIT",
                }
            ),
            _wise_row(
                **{
                    "Documento de identidad": "CARD-4",
                    "Fecha": day,
                    "Divisa": "USD",
                    "Cantidad": -5,
                    "Descripción": "En dólares",
                }
            ),
            _wise_row(
                **{
                    "Documento de identidad": "CARD-5",
                    "Fecha": day,
                    "Divisa": "EUR",
                    "Cantidad": 5,
                    "Descripción": "Signo raro",
                    "Tipo de transacción": "DEBIT",
                }
            ),
            _wise_row(
                **{
                    "Documento de identidad": "CARD-6",
                    "Fecha": day,
                    "Divisa": "EUR",
                    "Cantidad": "",
                    "Descripción": "Sin importe",
                }
            ),
        ],
        title="All transactions",
    )
    result = check_format(wb, "wise").parse(wb)

    bar, kiosk, transfer, conversion = result.transactions
    assert bar.description.startswith("Transacción con tarjeta")  # sin comercio ni nombres
    assert bar.amount == Decimal("-3.50")
    assert (bar.external_id, kiosk.external_id) == ("CARD-1", "CARD-1#2")
    assert kiosk.description == "Kiosco Ejemplo"
    assert transfer.description == "Persona Ejemplo"  # gasto: el beneficiario
    assert transfer.transfer_hint is None
    assert conversion.transfer_hint == "conversion"
    assert all(t.balance is None for t in result.transactions)  # sin saldo corriente
    assert [(e.row, e.field) for e in result.errors] == [
        (6, "Divisa"),
        (7, "Cantidad"),
        (8, "Cantidad"),
    ]
    assert result.errors[2].message == "Fila 8: no se ha podido leer el importe (está vacío)"


def test_wise_missing_sheet() -> None:
    wb = _xlsx(["Documento de identidad", "Fecha", "Cantidad", "Divisa"], [], title="Hoja1")
    with pytest.raises(ImportFormatError, match="no tiene el formato del extracto de Wise"):
        check_format(wb, "wise")


def test_wise_missing_description_column() -> None:
    headers = ["Documento de identidad", "Fecha", "Cantidad", "Divisa"]
    wb = _xlsx(headers, [["CARD-1", "01/10/2026", -1, "EUR"]], title="All transactions")
    with pytest.raises(ImportFormatError, match="No se encuentra la columna «Descripción»"):
        check_format(wb, "wise").parse(wb)
