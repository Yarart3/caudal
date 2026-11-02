"""Fase 2, parte 2.4: avisos (GET /api/alerts) con movimientos inventados."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.alerts.service import eur
from app.models import Account, Transaction


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


@pytest.fixture
def account(gerard: TestClient, make_account) -> Account:
    return make_account("imagin", username="gerard")


def _category_id(client: TestClient, name: str) -> int:
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def _add(
    db: Session, account: Account, day: str, description: str, amount: str, **fields
) -> Transaction:
    tx = Transaction(
        account_id=account.id,
        date=date.fromisoformat(day),
        description=description,
        amount=Decimal(amount),
        category_status="auto" if fields.get("category_id") else "review",
        **fields,
    )
    db.add(tx)
    db.commit()
    return tx


def _get(client: TestClient, month: str = "2026-09") -> list[dict]:
    res = client.get(f"/api/alerts?month={month}")
    assert res.status_code == 200
    assert res.json()["month"] == month
    return res.json()["items"]


def _kinds(items: list[dict]) -> list[str]:
    return [a["kind"] for a in items]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", "0,00 €"),
        ("15.5", "15,50 €"),
        ("1234.56", "1.234,56 €"),
        ("1234567.8", "1.234.567,80 €"),
        ("-42.1", "−42,10 €"),
    ],
)
def test_eur(value: str, expected: str) -> None:
    assert eur(Decimal(value)) == expected


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/alerts").status_code == 401


def test_no_data_no_alerts(gerard: TestClient) -> None:
    assert _get(gerard) == []


def test_budget_over(gerard: TestClient, db: Session, account: Account) -> None:
    food = _category_id(gerard, "Comida fuera")
    market = _category_id(gerard, "Supermercado")
    body = {
        "items": [
            {"category_id": food, "amount": "60.00"},
            {"category_id": market, "amount": "200.00"},
        ]
    }
    assert gerard.put("/api/budgets?month=2026-09", json=body).status_code == 200
    _add(db, account, "2026-09-10", "BAR PEPE", "-75.50", category_id=food)
    _add(db, account, "2026-09-11", "MERCADONA", "-190.00", category_id=market)  # al límite
    items = _get(gerard)
    assert items == [
        {
            "kind": "budget_over",
            "level": "danger",
            "title": "Presupuesto",
            "message": "Has superado Comida fuera en 15,50 €.",
            "category_id": food,
            "amount": "15.50",
        }
    ]


def test_spending_high_against_three_month_average(
    gerard: TestClient, db: Session, account: Account
) -> None:
    leisure = _category_id(gerard, "Ocio y salidas")
    market = _category_id(gerard, "Supermercado")
    # Media de ocio: (40 + 50 + 60) / 3 = 50. Septiembre: 120 → más de 1,5 veces y +70 €
    for day, amount in (
        ("2026-06-05", "-40.00"),
        ("2026-07-05", "-50.00"),
        ("2026-08-05", "-60.00"),
    ):
        _add(db, account, day, "CINE", amount, category_id=leisure)
        _add(db, account, day, "MERCADONA", "-100.00", category_id=market)
    _add(db, account, "2026-09-05", "CINE", "-120.00", category_id=leisure)
    # Supermercado: 140 frente a 100 de media → +40 %, no llega a 1,5 veces
    _add(db, account, "2026-09-06", "MERCADONA", "-140.00", category_id=market)
    items = [a for a in _get(gerard) if a["kind"] == "spending_high"]
    assert items == [
        {
            "kind": "spending_high",
            "level": "warning",
            "title": "Gasto alto",
            "message": "Ocio y salidas: 120,00 € este mes, frente a 50,00 € de media.",
            "category_id": leisure,
            "amount": "70.00",
        }
    ]


def test_spending_high_needs_minimum_difference(
    gerard: TestClient, db: Session, account: Account
) -> None:
    leisure = _category_id(gerard, "Ocio y salidas")
    _add(db, account, "2026-08-05", "CINE", "-10.00", category_id=leisure)
    _add(db, account, "2026-09-05", "CINE", "-35.00", category_id=leisure)  # ×3,5 pero +25 €
    assert "spending_high" not in _kinds(_get(gerard))


def test_months_without_data_do_not_lower_the_average(
    gerard: TestClient, db: Session, account: Account
) -> None:
    leisure = _category_id(gerard, "Ocio y salidas")
    # Solo agosto tiene datos: la media es 80, no 80 / 3
    _add(db, account, "2026-08-05", "CINE", "-80.00", category_id=leisure)
    _add(db, account, "2026-09-05", "CINE", "-100.00", category_id=leisure)
    assert "spending_high" not in _kinds(_get(gerard))


def test_first_month_has_no_spending_alert(
    gerard: TestClient, db: Session, account: Account
) -> None:
    leisure = _category_id(gerard, "Ocio y salidas")
    _add(db, account, "2026-09-05", "CINE", "-500.00", category_id=leisure)
    assert _get(gerard) == []


def test_new_category_spending_is_high(gerard: TestClient, db: Session, account: Account) -> None:
    leisure = _category_id(gerard, "Ocio y salidas")
    health = _category_id(gerard, "Salud")
    _add(db, account, "2026-08-05", "CINE", "-20.00", category_id=leisure)
    _add(db, account, "2026-09-05", "DENTISTA", "-60.00", category_id=health)
    items = [a for a in _get(gerard) if a["kind"] == "spending_high"]
    assert [(a["category_id"], a["message"]) for a in items] == [
        (health, "Salud: 60,00 € este mes, frente a 0,00 € de media.")
    ]


def test_over_budget_is_not_repeated_as_high(
    gerard: TestClient, db: Session, account: Account
) -> None:
    leisure = _category_id(gerard, "Ocio y salidas")
    body = {"items": [{"category_id": leisure, "amount": "50.00"}]}
    gerard.put("/api/budgets?month=2026-09", json=body)
    _add(db, account, "2026-08-05", "CINE", "-20.00", category_id=leisure)
    _add(db, account, "2026-09-05", "CINE", "-100.00", category_id=leisure)
    kinds = _kinds(_get(gerard))
    assert "budget_over" in kinds
    assert "spending_high" not in kinds


def test_expense_change(gerard: TestClient, db: Session, account: Account) -> None:
    _add(db, account, "2026-08-05", "TIENDA", "-100.00")
    _add(db, account, "2026-09-05", "TIENDA", "-112.00")
    _add(db, account, "2026-09-06", "NOMINA", "500.00")  # los ingresos no cuentan
    change = [a for a in _get(gerard) if a["kind"] == "expense_change"]
    assert change == [
        {
            "kind": "expense_change",
            "level": "warning",
            "title": "Gasto ↑",
            "message": "Gastos +12 % respecto a agosto.",
            "category_id": None,
            "amount": "12.00",
        }
    ]
    _add(db, account, "2026-10-05", "TIENDA", "-56.00")
    change = [a for a in _get(gerard, "2026-10") if a["kind"] == "expense_change"]
    assert (change[0]["level"], change[0]["title"], change[0]["message"]) == (
        "positive",
        "Gasto ↓",
        "Gastos -50 % respecto a septiembre.",
    )


def test_expense_change_january_compares_with_december(
    gerard: TestClient, db: Session, account: Account
) -> None:
    _add(db, account, "2025-12-05", "TIENDA", "-100.00")
    _add(db, account, "2026-01-05", "TIENDA", "-100.00")
    change = [a for a in _get(gerard, "2026-01") if a["kind"] == "expense_change"]
    assert change[0]["message"] == "Gastos 0 % respecto a diciembre."


def test_internal_transfers_do_not_count(gerard: TestClient, db: Session, account: Account) -> None:
    _add(db, account, "2026-08-05", "TIENDA", "-100.00")
    _add(db, account, "2026-09-05", "TIENDA", "-100.00")
    _add(db, account, "2026-09-06", "TRASPASO A WISE", "-500.00", is_internal_transfer=True)
    change = [a for a in _get(gerard) if a["kind"] == "expense_change"]
    assert change[0]["message"] == "Gastos 0 % respecto a agosto."


def test_recurring_alerts(gerard: TestClient, db: Session, account: Account) -> None:
    for day in ("2026-06-25", "2026-07-25", "2026-08-25", "2026-09-25"):
        _add(db, account, day, "SPOTIFY", "-10.99")
    for day in ("2026-07-01", "2026-08-01", "2026-09-01"):
        _add(db, account, day, "GIMNASIO", "-34.90")
    items = [a for a in _get(gerard) if a["kind"].startswith("recurring")]
    assert [(a["kind"], a["title"], a["message"]) for a in items] == [
        ("recurring_new", "Nuevo recurrente", "GIMNASIO: 34,90 € al mes."),
        ("recurring_total", "Recurrentes", "2 pagos recurrentes suman 45,89 € al mes."),
    ]


def test_new_annual_recurring(gerard: TestClient, db: Session, account: Account) -> None:
    _add(db, account, "2025-09-15", "SEGURO HOGAR", "-340.00")
    _add(db, account, "2026-09-14", "SEGURO HOGAR", "-342.00")
    items = [a for a in _get(gerard) if a["kind"].startswith("recurring")]
    assert [a["message"] for a in items] == [
        "SEGURO HOGAR: 342,00 € al año.",
        "1 pago recurrente suma 28,50 € al mes.",
    ]


def test_order_of_alerts(gerard: TestClient, db: Session, account: Account) -> None:
    food = _category_id(gerard, "Comida fuera")
    leisure = _category_id(gerard, "Ocio y salidas")
    gerard.put(
        "/api/budgets?month=2026-09", json={"items": [{"category_id": food, "amount": "10.00"}]}
    )
    for day in ("2026-07-01", "2026-08-01"):
        _add(db, account, day, "GIMNASIO", "-34.90")
        _add(db, account, day, "CINE", "-10.00", category_id=leisure)
    _add(db, account, "2026-09-01", "GIMNASIO", "-34.90")
    _add(db, account, "2026-09-03", "CINE", "-90.00", category_id=leisure)
    _add(db, account, "2026-09-04", "BAR PEPE", "-20.00", category_id=food)
    assert _kinds(_get(gerard)) == [
        "budget_over",
        "spending_high",
        "expense_change",
        "recurring_new",
        "recurring_total",
    ]


def test_invalid_month_is_rejected(gerard: TestClient) -> None:
    assert gerard.get("/api/alerts?month=2026-00").status_code == 422


def test_users_are_isolated(
    gerard: TestClient, padres: TestClient, db: Session, account: Account, make_account
) -> None:
    padres_account = make_account("caixabank", username="padres")
    food = _category_id(gerard, "Comida fuera")
    gerard.put(
        "/api/budgets?month=2026-09", json={"items": [{"category_id": food, "amount": "10.00"}]}
    )
    _add(db, account, "2026-09-04", "BAR PEPE", "-20.00", category_id=food)
    _add(db, padres_account, "2026-08-04", "TIENDA", "-100.00")
    _add(db, padres_account, "2026-09-04", "TIENDA", "-150.00")
    assert _kinds(_get(gerard)) == ["budget_over"]
    assert _kinds(_get(padres)) == ["expense_change"]
