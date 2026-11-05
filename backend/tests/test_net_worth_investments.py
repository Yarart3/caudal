"""Fase 3, parte 3.6: Patrimonio con las inversiones (valor a fin de mes, por cuenta y por tipo).

Productos, precios y operaciones inventados, escritos directamente en la BD. Las fechas son de
2025 para que el fin de mes ya haya pasado (si no, se valora a hoy).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dashboard.service import net_worth
from app.db import SessionLocal
from app.investments.operations import TZ
from app.investments.portfolio import InvestmentHistory
from app.models import (
    Account,
    InvestmentOperation,
    ManualValuation,
    Price,
    Product,
    User,
)

D = Decimal
FETCHED = datetime(2025, 8, 1, 12, 0, tzinfo=TZ)


def user(db: Session, username: str = "gerard") -> User:
    row = db.scalar(select(User).where(User.username == username))
    if row is None:
        row = User(username=username, display_name=username, color="#0E6B58", password_hash="x")
        db.add(row)
        db.commit()
    return row


def account(db: Session, owner: User, name: str, kind: str = "investment") -> Account:
    row = Account(user_id=owner.id, name=name, kind=kind)
    db.add(row)
    db.commit()
    return row


def op(db: Session, acc: Account, prod: Product, day: date, kind: str, amount: str, shares="0"):
    db.add(
        InvestmentOperation(
            account_id=acc.id,
            product_id=prod.id,
            date=day,
            kind=kind,
            shares=D(shares),
            amount_eur=D(amount),
        )
    )
    db.commit()


def portfolio(db: Session) -> dict:
    """Gerard: un ETF en Scalable y en Trade Republic, y un plan de pensiones a mano."""
    me = user(db)
    scalable = account(db, me, "Scalable")
    tr = account(db, me, "Trade Republic", "mixed")
    plan_account = account(db, me, "Plan")
    etf = Product(
        user_id=me.id, name="ETF inventado", kind="etf", price_source="yahoo", source_id="A.DE"
    )
    plan = Product(user_id=me.id, name="Plan inventado", kind="pension", price_source="manual")
    db.add_all([etf, plan])
    db.commit()
    for day, price in (
        (date(2025, 3, 3), "10"),
        (date(2025, 6, 30), "12"),
        (date(2025, 7, 31), "11"),
    ):
        db.add(
            Price(
                product_id=etf.id,
                date=day,
                price=D(price),
                currency="EUR",
                source="yahoo",
                fetched_at=FETCHED,
            )
        )
    db.add(ManualValuation(product_id=plan.id, date=date(2025, 5, 31), value_eur=D("520.00")))
    db.commit()
    op(db, scalable, etf, date(2025, 3, 3), "buy", "100.00", "10")
    op(db, plan_account, plan, date(2025, 4, 1), "buy", "500.00", "1")
    op(db, tr, etf, date(2025, 5, 2), "buy", "110.00", "10")
    return {"me": me, "scalable": scalable, "tr": tr, "plan": plan_account, "etf": etf}


def test_net_worth_includes_investments_at_month_end(db):
    p = portfolio(db)
    result = net_worth(db, p["me"].id, date(2025, 6, 1))
    # 30-6: 20 participaciones × 12 = 240 (la mitad en cada cuenta) + plan 520 = 760
    assert result.investments == D("760.00")
    assert result.net_worth == D("760.00")  # sin liquidez
    assert result.investments_gain == D("50.00")  # 760 − (100 + 110 + 500)
    assert result.investments_by_kind == {"etf": D("240.00"), "pension": D("520.00")}
    invested = {a.name: a.invested for a in result.accounts}
    assert invested == {"Scalable": D("120.00"), "Trade Republic": D("120.00"), "Plan": D("520.00")}
    assert all(a.balance == 0 for a in result.accounts)
    # Evolución: feb 0 · mar 10 × 10 = 100 · abr 100 + plan sin valor anotado (lo que costó,
    # 500) = 600 · may 20 × 10 + 520 = 720 · jun 760
    history = {m.month: m.investments for m in result.history}
    assert [history[m] for m in ("2025-02", "2025-03", "2025-04", "2025-05", "2025-06")] == [
        D("0"),
        D("100.00"),
        D("600.00"),
        D("720.00"),
        D("760.00"),
    ]


def test_a_sale_moves_the_split_between_accounts(db):
    p = portfolio(db)
    op(db, p["tr"], p["etf"], date(2025, 7, 15), "sell", "115.00", "10")
    holdings = InvestmentHistory(db, p["me"].id).at(date(2025, 7, 31))
    # Quedan 10 en Scalable a 11 €; en Trade Republic ya no hay nada
    assert holdings.by_account == {p["scalable"].id: D("110.00"), p["plan"].id: D("520.00")}
    assert holdings.value == D("630.00")
    # FIFO por producto: se vendió el lote de Scalable (100 €); queda el de TR (110 €)
    assert holdings.cost == D("610.00")


def test_without_investments_nothing_changes(db):
    me = user(db)
    account(db, me, "imagin", "spending")
    result = net_worth(db, me.id, date(2025, 6, 1))
    assert (result.investments, result.investments_gain) == (D("0"), D("0"))
    assert result.investments_by_kind == {}
    assert all(m.investments == 0 for m in result.history)


def test_net_worth_api_and_goal_include_investments(login):
    client = login("gerard")
    with SessionLocal() as db:
        p = portfolio(db)
        tr_id = p["tr"].id
    res = client.post(
        "/api/transactions",
        json={
            "account_id": tr_id,
            "date": "2025-06-10",
            "description": "Ingreso",
            "amount": "1000",
        },
    )
    assert res.status_code == 201

    data = client.get("/api/dashboard/net-worth?month=2025-06").json()
    assert (data["liquidity"], data["investments"], data["net_worth"]) == (
        "1000.00",
        "760.00",
        "1760.00",
    )
    assert data["investments_gain"] == "50.00"
    assert data["investments_by_kind"] == {"etf": "240.00", "pension": "520.00"}
    tr = next(a for a in data["accounts"] if a["name"] == "Trade Republic")
    assert (tr["balance"], tr["invested"]) == ("1000.00", "120.00")
    assert data["history"][-1] == {
        "month": "2025-06",
        "liquidity": "1000.00",
        "investments": "760.00",
    }

    client.put("/api/goals?month=2025-06", json={"name": "Meta", "target_amount": "10000"})
    assert client.get("/api/goals?month=2025-06").json()["net_worth"] == "1760.00"

    # Los padres no ven nada de Gerard
    padres = login("padres").get("/api/dashboard/net-worth?month=2025-06").json()
    assert (padres["investments"], padres["net_worth"]) == ("0.00", "0.00")
    assert padres["investments_by_kind"] == {}
