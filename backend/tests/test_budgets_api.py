"""Fase 2, parte 2.2: presupuestos (GET/PUT /api/budgets) con importes inventados."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.budgets import budget_status


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _account(client: TestClient, name: str = "imagin") -> int:
    body = {"name": name, "kind": "spending", "import_format": None, "liquidity_type": "cash"}
    res = client.post("/api/accounts", json=body)
    assert res.status_code == 201
    return res.json()["id"]


def _tx(client: TestClient, account: int, day: str, description: str, amount: str) -> dict:
    body = {"account_id": account, "date": day, "description": description, "amount": amount}
    res = client.post("/api/transactions", json=body)
    assert res.status_code == 201
    return res.json()


def _category_id(client: TestClient, name: str) -> int:
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def _put(client: TestClient, items: list[dict], month: str = "2026-09"):
    return client.put(f"/api/budgets?month={month}", json={"items": items})


def _line(body: dict, name: str) -> dict:
    return next(line for line in body["lines"] if line["name"] == name)


@pytest.mark.parametrize(
    ("spent", "expected"),
    [
        ("0.00", "ok"),
        ("89.99", "ok"),
        ("90.00", "near"),
        ("100.00", "near"),
        ("100.01", "over"),
    ],
)
def test_budget_status_thresholds(spent: str, expected: str) -> None:
    assert budget_status(Decimal(spent), Decimal("100.00")) == expected


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/budgets").status_code == 401
    assert client.put("/api/budgets", json={"items": []}).status_code == 401


def test_without_budgets_lists_every_expense_category(gerard: TestClient) -> None:
    body = gerard.get("/api/budgets?month=2026-09").json()
    expense = [c["name"] for c in gerard.get("/api/categories").json() if c["kind"] == "expense"]
    assert body["month"] == "2026-09"
    assert sorted(line["name"] for line in body["lines"]) == sorted(expense)
    assert all(line["budget"] is None and line["status"] is None for line in body["lines"])
    assert body["total_budget"] == "0.00"
    assert body["total_spent"] == "0.00"


def test_spent_and_status_per_category(gerard: TestClient) -> None:
    account = _account(gerard)
    market = _category_id(gerard, "Supermercado")
    food = _category_id(gerard, "Comida fuera")
    online = _category_id(gerard, "Compras online")
    # Supermercado: 40 + 50 = 90 de 100 → Al límite (la devolución no resta)
    _tx(gerard, account, "2026-09-03", "MERCADONA VALENCIA", "-40.00")
    _tx(gerard, account, "2026-09-20", "MERCADONA VALENCIA", "-50.00")
    _tx(gerard, account, "2026-09-21", "MERCADONA VALENCIA", "10.00")
    # Comida fuera: 75,50 de 60 → Superado
    _tx(gerard, account, "2026-09-10", "BAR PEPE", "-75.50")
    # Otros meses no cuentan
    _tx(gerard, account, "2026-08-31", "BAR PEPE", "-99.00")
    _tx(gerard, account, "2026-10-01", "MERCADONA VALENCIA", "-99.00")
    # Una transferencia interna con categoría tampoco cuenta
    internal = _tx(gerard, account, "2026-09-15", "AMAZON EU", "-30.00")
    res = gerard.patch(f"/api/transactions/{internal['id']}", json={"is_internal_transfer": True})
    assert res.status_code == 200
    # Compras online: nada gastado de 120 → OK
    res = _put(
        gerard,
        [
            {"category_id": market, "amount": "100.00"},
            {"category_id": food, "amount": "60"},
            {"category_id": online, "amount": "120.00"},
        ],
    )
    assert res.status_code == 200
    body = res.json()

    assert _line(body, "Supermercado") | {"color": None} == {
        "category_id": market,
        "name": "Supermercado",
        "color": None,
        "budget": "100.00",
        "spent": "90.00",
        "remaining": "10.00",
        "percent": 90,
        "status": "near",
    }
    food_line = _line(body, "Comida fuera")
    assert (food_line["spent"], food_line["remaining"], food_line["percent"]) == (
        "75.50",
        "-15.50",
        126,
    )
    assert food_line["status"] == "over"
    online_line = _line(body, "Compras online")
    assert (online_line["spent"], online_line["status"]) == ("0.00", "ok")
    assert body["total_budget"] == "280.00"
    assert body["total_spent"] == "165.50"
    # Primero las que tienen presupuesto, de más a menos consumido
    assert [line["name"] for line in body["lines"][:3]] == [
        "Comida fuera",
        "Supermercado",
        "Compras online",
    ]
    assert all(line["budget"] is None for line in body["lines"][3:])
    # El GET devuelve lo mismo que el PUT
    assert gerard.get("/api/budgets?month=2026-09").json() == body


def test_budget_applies_to_every_month(gerard: TestClient) -> None:
    account = _account(gerard)
    market = _category_id(gerard, "Supermercado")
    _put(gerard, [{"category_id": market, "amount": "100.00"}])
    _tx(gerard, account, "2026-10-02", "MERCADONA VALENCIA", "-120.00")
    line = _line(gerard.get("/api/budgets?month=2026-10").json(), "Supermercado")
    assert (line["budget"], line["status"]) == ("100.00", "over")


def test_without_month_uses_last_transaction_month(gerard: TestClient) -> None:
    account = _account(gerard)
    _tx(gerard, account, "2026-07-14", "MERCADONA VALENCIA", "-5.00")
    assert gerard.get("/api/budgets").json()["month"] == "2026-07"


def test_put_null_removes_the_budget(gerard: TestClient) -> None:
    market = _category_id(gerard, "Supermercado")
    _put(gerard, [{"category_id": market, "amount": "100.00"}])
    body = _put(gerard, [{"category_id": market, "amount": None}]).json()
    line = _line(body, "Supermercado")
    assert (line["budget"], line["percent"], line["status"]) == (None, None, None)


def test_put_only_changes_listed_categories(gerard: TestClient) -> None:
    market = _category_id(gerard, "Supermercado")
    food = _category_id(gerard, "Comida fuera")
    _put(gerard, [{"category_id": market, "amount": "100.00"}])
    body = _put(gerard, [{"category_id": food, "amount": "50.00"}]).json()
    assert _line(body, "Supermercado")["budget"] == "100.00"
    assert _line(body, "Comida fuera")["budget"] == "50.00"


@pytest.mark.parametrize("amount", ["0", "-10.00", "12.345", "abc"])
def test_invalid_amount_is_rejected(gerard: TestClient, amount: str) -> None:
    market = _category_id(gerard, "Supermercado")
    res = _put(gerard, [{"category_id": market, "amount": amount}])
    assert res.status_code == 422
    assert "detail" in res.json()


def test_income_category_cannot_have_budget(gerard: TestClient) -> None:
    payroll = _category_id(gerard, "Nómina")
    res = _put(gerard, [{"category_id": payroll, "amount": "100.00"}])
    assert res.status_code == 422
    assert res.json()["detail"] == "Solo las categorías de gasto tienen presupuesto"


def test_repeated_category_is_rejected(gerard: TestClient) -> None:
    market = _category_id(gerard, "Supermercado")
    items = [{"category_id": market, "amount": "10.00"}, {"category_id": market, "amount": "20.00"}]
    assert _put(gerard, items).status_code == 422


def test_invalid_month_is_rejected(gerard: TestClient) -> None:
    assert gerard.get("/api/budgets?month=2026-13").status_code == 422
    assert _put(gerard, [], month="septiembre").status_code == 422


def test_changing_category_to_income_removes_its_budget(gerard: TestClient) -> None:
    other = _category_id(gerard, "Otros")
    _put(gerard, [{"category_id": other, "amount": "30.00"}])
    res = gerard.patch(f"/api/categories/{other}", json={"kind": "income"})
    assert res.status_code == 200
    assert all(line["category_id"] != other for line in gerard.get("/api/budgets").json()["lines"])
    res = gerard.patch(f"/api/categories/{other}", json={"kind": "expense"})
    assert _line(gerard.get("/api/budgets").json(), "Otros")["budget"] is None


def test_users_are_isolated(gerard: TestClient, padres: TestClient) -> None:
    gerard_market = _category_id(gerard, "Supermercado")
    padres_market = _category_id(padres, "Supermercado")
    _put(gerard, [{"category_id": gerard_market, "amount": "100.00"}])
    _tx(padres, _account(padres, "CaixaBank"), "2026-09-05", "MERCADONA VALENCIA", "-80.00")

    # Padres no ve el presupuesto de Gerard y Gerard no ve el gasto de Padres
    assert _line(padres.get("/api/budgets?month=2026-09").json(), "Supermercado")["budget"] is None
    assert _line(gerard.get("/api/budgets?month=2026-09").json(), "Supermercado")["spent"] == "0.00"

    # Padres no puede tocar una categoría de Gerard: 404 y no se guarda nada del lote
    items = [
        {"category_id": padres_market, "amount": "50.00"},
        {"category_id": gerard_market, "amount": "1.00"},
    ]
    res = _put(padres, items)
    assert res.status_code == 404
    assert res.json()["detail"] == "Categoría no encontrada"
    assert _line(padres.get("/api/budgets?month=2026-09").json(), "Supermercado")["budget"] is None
    assert _line(gerard.get("/api/budgets?month=2026-09").json(), "Supermercado")["budget"] == (
        "100.00"
    )
