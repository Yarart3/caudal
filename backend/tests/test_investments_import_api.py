"""Fase 3, parte 3.3c: GET /api/investments/template y POST /api/investments/import."""

from datetime import datetime, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select

from app.api import investments as investments_api
from app.db import SessionLocal
from app.investments.operations import TZ
from app.models import InvestmentOperation, Product, User

HEADER = (
    "fecha;identificador;nombre;tipo_producto;tipo_movimiento;unidades;importe;moneda;comision;nota"
)
OPS = "/api/investments/operations"


def csv_file(*lines: str) -> bytes:
    return "\r\n".join([HEADER, *lines]).encode("utf-8")


def add_product(username: str, name: str, isin: str | None, symbol: str, ticker: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        row = Product(
            user_id=user.id,
            name=name,
            isin=isin,
            ticker=ticker,
            kind="etf",
            price_source="yahoo",
            source_id=symbol,
        )
        db.add(row)
        db.commit()
        return row.id


@pytest.fixture
def gerard(login) -> dict:
    client = login("gerard")
    scalable = client.post("/api/accounts", json={"name": "Scalable", "kind": "investment"})
    add_product("gerard", "Core S&P 500", "XX0000000001", "SXR8.DE", "SXR8")
    add_product("gerard", "MSCI ACWI", "XX0000000002", "IUSQ.DE", "IUSQ")
    return {"client": client, "account": scalable.json()["id"]}


def upload(g: dict, data: bytes, confirm: bool = False, account: int | None = None, name="h.csv"):
    return g["client"].post(
        "/api/investments/import",
        data={"account_id": str(account or g["account"]), "confirm": str(confirm).lower()},
        files={"file": (name, data, "text/csv")},
    )


def saved_operations(g: dict) -> list[dict]:
    return g["client"].get(OPS).json()


# ---------------------------------------------------------------- plantilla


def test_template_needs_login(client: TestClient) -> None:
    assert client.get("/api/investments/template").status_code == 401


def test_download_xlsx_template(gerard: dict) -> None:
    res = gerard["client"].get("/api/investments/template")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert 'filename="plantilla_inversiones.xlsx"' in res.headers["content-disposition"]
    assert load_workbook(BytesIO(res.content)).sheetnames[0] == "Operaciones"


def test_download_csv_template(gerard: dict) -> None:
    res = gerard["client"].get("/api/investments/template", params={"format": "csv"})
    assert res.headers["content-type"].startswith("text/csv")
    assert res.content.decode("utf-8-sig").startswith("fecha;identificador")
    assert (
        gerard["client"].get("/api/investments/template", params={"format": "pdf"}).status_code
        == 422
    )


# ---------------------------------------------------------------- vista previa y confirmación


LINES = (
    "03/03/2025;XX0000000001;;;compra;0,25;150,00;EUR;1,00;",
    "01/04/2025;iusq.de;;;compra;1;100;;;",
    "15/06/2025;sxr8;;;dividendo;;0,80;;;",
)


def test_preview_saves_nothing(gerard: dict) -> None:
    body = upload(gerard, csv_file(*LINES)).json()
    assert (body["read"], body["new"], body["duplicates"], body["saved"]) == (3, 3, 0, False)
    assert body["errors"] == []
    assert [(o["row"], o["product_name"], o["kind"]) for o in body["operations"]] == [
        (2, "Core S&P 500", "buy"),
        (3, "MSCI ACWI", "buy"),
        (4, "Core S&P 500", "dividend"),
    ]
    assert body["operations"][0]["shares"] == "0.25000000"
    assert saved_operations(gerard) == []


def test_confirm_saves_everything(gerard: dict) -> None:
    body = upload(gerard, csv_file(*LINES), confirm=True).json()
    assert (body["new"], body["saved"]) == (3, True)
    rows = saved_operations(gerard)
    assert [(r["date"], r["kind"], r["amount_eur"]) for r in rows] == [
        ("2025-06-15", "dividend", "0.80"),
        ("2025-04-01", "buy", "100.00"),
        ("2025-03-03", "buy", "150.00"),
    ]


def test_importing_the_same_file_twice_does_not_duplicate(gerard: dict) -> None:
    upload(gerard, csv_file(*LINES), confirm=True)
    body = upload(gerard, csv_file(*LINES), confirm=True).json()
    assert (body["new"], body["duplicates"], body["saved"]) == (0, 3, False)
    assert len(saved_operations(gerard)) == 3


def test_identical_rows_in_one_file_are_both_kept(gerard: dict) -> None:
    line = "01/04/2025;SXR8.DE;;;compra;1;700;;;"
    body = upload(gerard, csv_file(line, line), confirm=True).json()
    assert body["new"] == 2
    again = upload(gerard, csv_file(line, line, line), confirm=True).json()
    assert (again["new"], again["duplicates"]) == (1, 2)  # solo la tercera es nueva


def test_one_bad_row_saves_nothing(gerard: dict) -> None:
    body = upload(gerard, csv_file(*LINES, "01/05/2025;NOEXISTE;;;compra;1;10;;;"), True).json()
    assert body["saved"] is False
    assert body["errors"] == [
        {
            "row": 5,
            "field": "identificador",
            "value": "NOEXISTE",
            "message": "Fila 5: no tienes ningún producto «NOEXISTE»: créalo antes en Productos",
        }
    ]
    assert saved_operations(gerard) == []


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("01/04/2025;SXR8.DE;;;dividendo;1;5;;;", "Fila 2: Un dividendo o una comisión no lleva"),
        ("01/04/2025;SXR8.DE;;;compra;;5;;;", "Fila 2: Indica cuántas participaciones"),
        ("01/04/2025;SXR8.DE;;;compra;1;5;;6;", "Fila 2: La comisión no puede ser mayor"),
        ("01/04/2025;SXR8.DE;;;compra;1;0;;;", "Fila 2: Datos no válidos: revisa amount_eur"),
    ],
)
def test_rows_follow_the_same_rules_as_the_form(gerard: dict, line: str, message: str) -> None:
    body = upload(gerard, csv_file(line), confirm=True).json()
    assert body["saved"] is False
    assert body["errors"][0]["message"].startswith(message)


def test_future_dates_are_rejected(gerard: dict) -> None:
    tomorrow = (datetime.now(TZ).date() + timedelta(days=1)).strftime("%d/%m/%Y")
    body = upload(gerard, csv_file(f"{tomorrow};SXR8.DE;;;compra;1;5;;;")).json()
    assert "La fecha no puede ser posterior a hoy" in body["errors"][0]["message"]


def test_cannot_sell_more_than_bought(gerard: dict) -> None:
    lines = ("01/04/2025;SXR8.DE;;;compra;1;700;;;", "01/05/2025;SXR8.DE;;;venta;1,5;1000;;;")
    body = upload(gerard, csv_file(*lines), confirm=True).json()
    assert body["saved"] is False
    assert body["errors"][0]["message"] == (
        "Con este archivo venderías más «Core S&P 500» del que tienes en Scalable: "
        "el 01/05/2025 quedarían -0,5"
    )
    assert saved_operations(gerard) == []


def test_row_order_does_not_matter_and_previous_operations_count(gerard: dict) -> None:
    client = gerard["client"]
    manual = {
        "account_id": gerard["account"],
        "product_id": client.get("/api/products").json()[0]["id"],
        "date": "2025-01-10",
        "kind": "buy",
        "shares": "1",
        "amount_eur": "650.00",
    }
    assert client.post(OPS, json=manual).status_code == 201
    lines = ("01/05/2025;SXR8.DE;;;venta;1,5;1000;;;", "01/04/2025;SXR8.DE;;;compra;0,5;350;;;")
    body = upload(gerard, csv_file(*lines), confirm=True).json()
    assert (body["saved"], body["errors"]) == (True, [])


# ---------------------------------------------------------------- cuenta y archivo


def test_spending_account_is_rejected(gerard: dict) -> None:
    imagin = gerard["client"].post("/api/accounts", json={"name": "imagin", "kind": "spending"})
    res = upload(gerard, csv_file(*LINES), account=imagin.json()["id"])
    assert res.status_code == 422
    assert "no es de inversión" in res.json()["detail"]


def test_other_users_account_and_products_are_invisible(gerard: dict, login) -> None:
    padres = login("padres")
    theirs = padres.post("/api/accounts", json={"name": "Su broker", "kind": "investment"})
    assert upload(gerard, csv_file(*LINES), account=theirs.json()["id"]).status_code == 404
    add_product("padres", "Su ETF", "XX0000000009", "SU.DE", "SU")
    body = upload(gerard, csv_file("01/04/2025;SU.DE;;;compra;1;10;;;")).json()
    assert "no tienes ningún producto «SU.DE»" in body["errors"][0]["message"]


def test_empty_and_wrong_files(gerard: dict) -> None:
    res = upload(gerard, b"  \n")
    assert (res.status_code, res.json()) == (422, {"detail": "El archivo está vacío"})
    res = upload(gerard, b"Fecha;Concepto;Importe\n01/01/2025;Mercadona;-10\n")
    assert res.status_code == 422
    assert "plantilla de inversiones" in res.json()["detail"]


def test_file_too_big(gerard: dict, monkeypatch) -> None:
    monkeypatch.setattr(investments_api, "MAX_BYTES", 100)
    res = upload(gerard, csv_file(*LINES))
    assert res.status_code == 413


def test_xlsx_upload(gerard: dict) -> None:
    template = gerard["client"].get("/api/investments/template").content
    workbook = load_workbook(BytesIO(template))
    workbook["Operaciones"].append(
        ["03/03/2025", "SXR8.DE", None, None, "compra", 0.25, 150, "EUR", None, None]
    )
    out = BytesIO()
    workbook.save(out)
    body = upload(gerard, out.getvalue(), confirm=True, name="h.xlsx").json()
    assert (body["new"], body["saved"]) == (1, True)
    with SessionLocal() as db:
        assert db.scalars(select(InvestmentOperation.fingerprint)).one() is not None
