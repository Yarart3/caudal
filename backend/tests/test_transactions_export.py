"""Fase 5, parte 5.3: exportar los movimientos a Excel (GET /api/transactions/export)."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _account(client: TestClient, name: str, import_format: str | None = None) -> int:
    body = {"name": name, "kind": "spending", "import_format": import_format}
    res = client.post("/api/accounts", json=body)
    assert res.status_code == 201
    return res.json()["id"]


def _tx(client: TestClient, account: int, description: str, amount: str, **extra) -> dict:
    body = {
        "account_id": account,
        "date": "2026-09-26",
        "description": description,
        "amount": amount,
        **extra,
    }
    res = client.post("/api/transactions", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _export(client: TestClient, **params):
    res = client.get("/api/transactions/export", params=params)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == XLSX
    return res, load_workbook(BytesIO(res.content))


def _rows(workbook) -> list[tuple]:
    return list(workbook["Movimientos"].iter_rows(min_row=2, values_only=True))


def _summary(workbook) -> dict:
    return {row[0]: row[1] for row in workbook["Resumen"].iter_rows(min_row=2, values_only=True)}


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/transactions/export").status_code == 401


def test_columns_and_values(gerard: TestClient) -> None:
    cash = _account(gerard, "Efectivo")
    _tx(gerard, cash, "MERCADONA", "-12.34", tags=["casa"], note="compra semanal")
    res, workbook = _export(gerard)

    assert 'filename="caudal_movimientos_todos_' in res.headers["content-disposition"]
    sheet = workbook["Movimientos"]
    header = [cell.value for cell in sheet[1]]
    assert header == [
        "Fecha",
        "Cuenta",
        "Concepto",
        "Categoría",
        "Importe",
        "Tipo",
        "Estado",
        "Etiquetas",
        "Nota",
    ]
    (row,) = _rows(workbook)
    # Fecha de Excel, no texto (openpyxl la lee como datetime sin zona)
    assert isinstance(row[0], datetime)
    assert row[0].date() == date(2026, 9, 26)
    assert row[1:4] == ("Efectivo", "MERCADONA", "Supermercado")
    assert Decimal(str(row[4])) == Decimal("-12.34")  # número, para poder sumar en Excel
    assert row[5:] == ("Gasto", "Automática", "casa", "compra semanal")
    assert sheet["E2"].number_format.startswith("#,##0.00")


def test_filters_and_summary_without_internal(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    wise = _account(gerard, "Wise", "wise")
    for account, data in ((wise, WISE), (imagin, IMAGIN)):
        res = gerard.post(
            "/api/imports",
            data={"account_id": str(account)},
            files={"file": ("x.xlsx", data, XLSX)},
        )
        assert res.status_code == 200

    listed = gerard.get("/api/transactions", params={"limit": 1000}).json()["items"]
    _, workbook = _export(gerard)
    assert len(_rows(workbook)) == len(listed)
    # Mismo orden que la lista: del más reciente al más antiguo
    assert [r[2] for r in _rows(workbook)] == [t["description"] for t in listed]

    counted = [Decimal(t["amount"]) for t in listed if not t["is_internal_transfer"]]
    summary = _summary(workbook)
    assert summary["Movimientos"] == len(listed)
    assert summary["Transferencias internas (no cuentan)"] == 2
    assert Decimal(str(summary["Ingresos"])) == sum(a for a in counted if a > 0)
    assert Decimal(str(summary["Gastos"])) == -sum(a for a in counted if a < 0)
    assert summary["Filtros"].startswith("Ninguno")

    _, only_wise = _export(gerard, account=wise, status="internal", month="2026-09")
    assert {r[1] for r in _rows(only_wise)} == {"Wise"}
    assert {r[6] for r in _rows(only_wise)} == {"Transferencia interna"}
    filters = _summary(only_wise)["Filtros"]
    assert "Mes: 2026-09" in filters and "Cuenta: Wise" in filters


def test_filter_by_tag_and_month_in_filename(gerard: TestClient) -> None:
    cash = _account(gerard, "Efectivo")
    _tx(gerard, cash, "HOTEL", "-80.00", tags=["viaje"])
    _tx(gerard, cash, "PAN", "-1.00")
    res, workbook = _export(gerard, tag="viaje", month="2026-09")
    assert [r[2] for r in _rows(workbook)] == ["HOTEL"]
    assert 'filename="caudal_movimientos_2026-09_' in res.headers["content-disposition"]


def test_text_is_never_a_formula(gerard: TestClient) -> None:
    cash = _account(gerard, "Efectivo")
    _tx(gerard, cash, '=HYPERLINK("http://x")', "-1.00", note="=1+1")
    _, workbook = _export(gerard)
    sheet = workbook["Movimientos"]
    assert sheet["C2"].data_type == "s"
    assert sheet["C2"].value == '=HYPERLINK("http://x")'
    assert sheet["I2"].data_type == "s"


def test_bad_month(gerard: TestClient) -> None:
    assert gerard.get("/api/transactions/export", params={"month": "2026-13"}).status_code == 422


def test_isolation(gerard: TestClient, padres: TestClient) -> None:
    cash = _account(gerard, "Efectivo")
    _tx(gerard, cash, "SECRETO", "-5.00")
    _, workbook = _export(padres)
    assert _rows(workbook) == []
    # Filtrar por una cuenta de otro no da nada ni revela su nombre
    _, workbook = _export(padres, account=cash)
    assert _rows(workbook) == []
    assert "Efectivo" not in _summary(workbook)["Filtros"]
