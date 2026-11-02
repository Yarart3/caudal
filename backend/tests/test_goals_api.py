"""Fase 2, parte 2.5: objetivo de patrimonio (GET/PUT/DELETE /api/goals), importes inventados."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.goals import milestones
from app.models import Account, Transaction


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _balance(db: Session, account: Account, day: str, amount: str) -> None:
    """Cuenta a mano: su saldo es la suma de sus movimientos."""
    tx = Transaction(
        account_id=account.id,
        date=date.fromisoformat(day),
        description="SALDO INICIAL",
        amount=Decimal(amount),
        category_status="review",
    )
    db.add(tx)
    db.commit()


@pytest.fixture
def savings(gerard: TestClient, db: Session, make_account) -> Account:
    """Gerard con 30.000 € a final de septiembre de 2026."""
    account = make_account(None, username="gerard", name="Efectivo")
    _balance(db, account, "2026-09-10", "30000.00")
    return account


def _put(client: TestClient, body: dict, month: str = "2026-09"):
    return client.put(f"/api/goals?month={month}", json=body)


def test_milestones_series() -> None:
    steps = milestones(Decimal("25000.00"))
    assert [str(m.amount) for m in steps][:5] == [
        "1000.00",
        "2500.00",
        "5000.00",
        "10000.00",
        "25000.00",
    ]
    assert [m.reached for m in steps][:6] == [True, True, True, True, True, False]


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/goals").status_code == 401
    assert client.put("/api/goals", json={"target_amount": "1000"}).status_code == 401
    assert client.delete("/api/goals").status_code == 401


def test_without_goal(gerard: TestClient, savings: Account) -> None:
    body = gerard.get("/api/goals?month=2026-09").json()
    assert body == {
        "month": "2026-09",
        "net_worth": "30000.00",
        "name": None,
        "target_amount": None,
        "percent": None,
        "remaining": None,
        "last_milestone": "25000.00",
        "next_milestones": ["50000.00", "100000.00", "250000.00"],
        "milestones": body["milestones"],
    }
    assert len(body["milestones"]) == 10


def test_put_creates_goal(gerard: TestClient, savings: Account) -> None:
    res = _put(gerard, {"target_amount": "50000"})
    assert res.status_code == 200
    body = res.json()
    assert (body["name"], body["target_amount"], body["percent"], body["remaining"]) == (
        "Objetivo de patrimonio",
        "50000.00",
        60,
        "20000.00",
    )
    assert gerard.get("/api/goals?month=2026-09").json() == body


def test_put_updates_the_same_goal(gerard: TestClient, savings: Account, db: Session) -> None:
    _put(gerard, {"target_amount": "50000.00"})
    body = _put(gerard, {"name": "  Piso  ", "target_amount": "40000.00"}).json()
    assert (body["name"], body["target_amount"], body["percent"]) == ("Piso", "40000.00", 75)


def test_percent_rounds_down_and_reached_goal(
    gerard: TestClient, savings: Account, db: Session
) -> None:
    assert _put(gerard, {"target_amount": "30001.00"}).json()["percent"] == 99
    body = _put(gerard, {"target_amount": "20000.00"}).json()
    assert (body["percent"], body["remaining"]) == (150, "0.00")


def test_negative_net_worth(gerard: TestClient, db: Session, make_account) -> None:
    account = make_account(None, username="gerard", name="Tarjeta")
    _balance(db, account, "2026-09-10", "-500.00")
    body = _put(gerard, {"target_amount": "1000.00"}).json()
    assert (body["net_worth"], body["percent"], body["remaining"]) == ("-500.00", 0, "1500.00")
    assert body["last_milestone"] is None
    assert body["next_milestones"] == ["1000.00", "2500.00", "5000.00"]


def test_net_worth_of_selected_month(gerard: TestClient, savings: Account, db: Session) -> None:
    _balance(db, savings, "2026-10-05", "10000.00")
    _put(gerard, {"target_amount": "50000.00"})
    assert gerard.get("/api/goals?month=2026-08").json()["net_worth"] == "0.00"
    assert gerard.get("/api/goals?month=2026-09").json()["percent"] == 60
    assert gerard.get("/api/goals?month=2026-10").json()["percent"] == 80
    assert gerard.get("/api/goals").json()["month"] == "2026-10"


@pytest.mark.parametrize(
    "body",
    [
        {"target_amount": "0"},
        {"target_amount": "-100.00"},
        {"target_amount": "100.001"},
        {"target_amount": "100", "name": "   "},
        {"target_amount": "100", "name": "x" * 61},
        {},
    ],
)
def test_invalid_goal_is_rejected(gerard: TestClient, body: dict) -> None:
    res = _put(gerard, body)
    assert res.status_code == 422
    assert "detail" in res.json()


def test_invalid_month_is_rejected(gerard: TestClient) -> None:
    assert gerard.get("/api/goals?month=2026-13").status_code == 422


def test_delete_goal(gerard: TestClient, savings: Account) -> None:
    _put(gerard, {"target_amount": "50000.00"})
    assert gerard.delete("/api/goals").status_code == 204
    assert gerard.get("/api/goals?month=2026-09").json()["target_amount"] is None
    assert gerard.delete("/api/goals").status_code == 204  # sin objetivo, tampoco falla


def test_users_are_isolated(
    gerard: TestClient, padres: TestClient, savings: Account, db: Session, make_account
) -> None:
    padres_account = make_account(None, username="padres", name="Efectivo")
    _balance(db, padres_account, "2026-09-10", "4000.00")
    _put(gerard, {"target_amount": "50000.00"})
    _put(padres, {"name": "Viaje", "target_amount": "8000.00"})

    gerard_goal = gerard.get("/api/goals?month=2026-09").json()
    padres_goal = padres.get("/api/goals?month=2026-09").json()
    assert (gerard_goal["name"], gerard_goal["net_worth"], gerard_goal["percent"]) == (
        "Objetivo de patrimonio",
        "30000.00",
        60,
    )
    assert (padres_goal["name"], padres_goal["net_worth"], padres_goal["percent"]) == (
        "Viaje",
        "4000.00",
        50,
    )
    # Padres borra el suyo: el de Gerard sigue
    padres.delete("/api/goals")
    assert gerard.get("/api/goals?month=2026-09").json()["target_amount"] == "50000.00"
