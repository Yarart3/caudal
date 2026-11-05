"""Fase 3, parte 3.4b: cartera desde la base de datos y GET /api/investments/summary · /positions.

Productos, precios y operaciones inventados, escritos directamente en la BD (sin Yahoo).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.investments.operations import TZ
from app.investments.portfolio import build, last_months, summarize
from app.models import (
    Account,
    ExchangeRate,
    InvestmentOperation,
    ManualValuation,
    Price,
    Product,
    User,
)

D = Decimal
TODAY = date(2026, 11, 4)
FETCHED = datetime(2026, 11, 4, 15, 0, tzinfo=TZ)


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


def product(db: Session, owner: User, name: str, symbol: str | None = None, **fields) -> Product:
    fields.setdefault("kind", "etf")
    fields.setdefault("price_source", "yahoo" if symbol else "manual")
    row = Product(user_id=owner.id, name=name, source_id=symbol, **fields)
    db.add(row)
    db.commit()
    return row


def prices(db: Session, prod: Product, rows: dict[date, str], currency: str = "EUR") -> None:
    for day, value in rows.items():
        db.add(
            Price(
                product_id=prod.id,
                date=day,
                price=D(value),
                currency=currency,
                source="yahoo",
                fetched_at=FETCHED,
            )
        )
    db.commit()


def op(db, acc, prod, day, kind, amount, shares="0") -> None:
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


# ---------------------------------------------------------------- build y summarize


def test_one_product_value_gain_xirr_and_year_return(db):
    me = user(db)
    scalable = account(db, me, "Scalable")
    sxr8 = product(db, me, "S&P 500 inventado", "SXR8.DE", ter=D("0.0007"), isin="XX0000000001")
    prices(db, sxr8, {date(2026, 1, 5): "100", date(2026, 6, 1): "110", date(2026, 11, 3): "120"})
    op(db, scalable, sxr8, date(2026, 1, 5), "buy", "1000.00", "10")

    portfolio = build(db, me.id, TODAY)
    [position] = portfolio.positions
    assert position.accounts == ["Scalable"]
    assert (position.book.shares, position.book.cost) == (D("10"), D("1000.00"))
    assert position.book.average_price == D("100")
    assert (position.value, position.gain) == (D("1200.00"), D("200.00"))
    assert position.price.date == date(2026, 11, 3)  # el miércoles 4 aún no hay: el del 3

    s = summarize(portfolio)
    assert (s.value, s.cost, s.gain) == (D("1200.00"), D("1000.00"), D("200.00"))
    assert s.gain_pct == D("0.2")
    # TIR: −1.000 el 5-1 y +1.200 el 4-11 (303 días) → 1,2 ^ (365/303) − 1
    days = (TODAY - date(2026, 1, 5)).days
    assert days == 303
    assert abs(float(s.xirr) - (1.2 ** (365 / days) - 1)) < 1e-6
    assert s.year_returns == [(2026, D("0.2"))]
    assert s.max_drawdown == 0
    assert s.ter_annual == D("0.84")  # 1.200 × 0,07 %
    assert s.missing == []


def test_drawdown_from_the_daily_series(db):
    me = user(db)
    acc = account(db, me, "Scalable")
    etf = product(db, me, "ETF inventado", "AAA.DE")
    prices(db, etf, {date(2026, 3, 2): "100", date(2026, 3, 3): "120", date(2026, 3, 4): "90"})
    op(db, acc, etf, date(2026, 3, 2), "buy", "1000.00", "10")
    s = summarize(build(db, me.id, date(2026, 3, 6)))
    assert s.max_drawdown == D("-0.25")  # de 1.200 a 900
    assert s.value == D("900.00")


def test_same_product_in_two_accounts_is_one_fifo(db):
    # Compra en Scalable (antes) y en Trade Republic; vende en TR. FIFO global: el coste de lo
    # vendido sale del lote de Scalable (el más antiguo), aunque la venta sea en TR.
    me = user(db)
    scalable = account(db, me, "Scalable")
    tr = account(db, me, "Trade Republic", "mixed")
    etf = product(db, me, "ETF inventado", "AAA.DE")
    prices(db, etf, {date(2026, 1, 2): "100", date(2026, 11, 2): "150"})
    op(db, scalable, etf, date(2026, 1, 2), "buy", "1000.00", "10")
    op(db, tr, etf, date(2026, 2, 2), "buy", "1200.00", "10")
    op(db, tr, etf, date(2026, 10, 1), "sell", "1400.00", "10")

    portfolio = build(db, me.id, TODAY)
    [position] = portfolio.positions
    assert position.accounts == ["Scalable"]  # en TR ya no queda nada
    assert (position.book.shares, position.book.cost) == (D("10"), D("1200.00"))
    assert summarize(portfolio).realized == D("400.00")  # 1.400 − 1.000


def test_fully_sold_product_counts_only_as_realized(db):
    me = user(db)
    acc = account(db, me, "Scalable")
    etf = product(db, me, "ETF vendido", "BBB.DE")
    prices(db, etf, {date(2026, 1, 2): "10"})
    op(db, acc, etf, date(2026, 1, 2), "buy", "100.00", "10")
    op(db, acc, etf, date(2026, 5, 4), "sell", "130.00", "10")
    op(db, acc, etf, date(2026, 4, 1), "dividend", "2.50")

    portfolio = build(db, me.id, TODAY)
    s = summarize(portfolio)
    assert portfolio.positions == []
    assert (s.value, s.realized, s.dividends) == (D("0.00"), D("30.00"), D("2.50"))
    # TIR sin valor final: −100 en enero, +2,50 en abril y +130 en mayo
    assert s.xirr is not None and s.xirr > 0


def test_foreign_currency_uses_the_exchange_rate(db):
    me = user(db)
    acc = account(db, me, "Scalable")
    usd = product(db, me, "ETF en dólares", "CCC", currency="USD")
    prices(db, usd, {date(2026, 11, 3): "50"}, currency="USD")
    db.add_all(
        [
            ExchangeRate(currency="USD", date=date(2026, 10, 1), rate=D("0.8"), source="yahoo"),
            ExchangeRate(currency="USD", date=date(2026, 11, 2), rate=D("0.9"), source="yahoo"),
        ]
    )
    db.commit()
    op(db, acc, usd, date(2026, 11, 3), "buy", "400.00", "10")
    [position] = build(db, me.id, TODAY).positions
    assert position.price_eur == D("45.0")  # 50 USD × 0,9 (el último tipo, del día 2)
    assert position.value == D("450.00")


def test_missing_price_or_rate_is_reported_and_left_out_of_the_value(db):
    me = user(db)
    acc = account(db, me, "Scalable")
    ok = product(db, me, "Con precio", "OK.DE")
    prices(db, ok, {date(2026, 11, 2): "10"})
    no_price = product(db, me, "Sin precio", "NOP.DE")
    no_rate = product(db, me, "Sin tipo de cambio", "NOR", currency="JPY")
    prices(db, no_rate, {date(2026, 11, 2): "1000"}, currency="JPY")
    for prod in (ok, no_price, no_rate):
        op(db, acc, prod, date(2026, 11, 2), "buy", "100.00", "10")

    portfolio = build(db, me.id, TODAY)
    s = summarize(portfolio)
    assert s.missing == ["Sin precio", "Sin tipo de cambio"]
    assert (s.value, s.cost) == (D("100.00"), D("100.00"))  # solo el que tiene precio
    # En la serie (y la TIR), lo que no tiene precio vale lo que costó
    assert portfolio.series[-1].value == D("300.00")


def test_manual_product_uses_the_last_valuation(db):
    me = user(db)
    acc = account(db, me, "Plan")
    plan = product(db, me, "Plan de pensiones inventado", kind="pension")
    op(db, acc, plan, date(2026, 1, 15), "buy", "1000.00", "1")
    db.add_all(
        [
            ManualValuation(product_id=plan.id, date=date(2026, 6, 30), value_eur=D("1040.00")),
            ManualValuation(product_id=plan.id, date=date(2026, 9, 30), value_eur=D("1075.50")),
        ]
    )
    db.commit()
    [position] = build(db, me.id, TODAY).positions
    assert (position.value, position.gain, position.price) == (D("1075.50"), D("75.50"), None)


def test_contributions_window_streak_and_dividends_12m(db):
    me = user(db)
    acc = account(db, me, "Scalable")
    etf = product(db, me, "ETF inventado", "AAA.DE")
    prices(db, etf, {date(2025, 10, 1): "10"})
    op(db, acc, etf, date(2025, 10, 1), "buy", "50.00", "5")  # fuera de los 12 meses
    for month in (8, 9, 10):
        op(db, acc, etf, date(2026, month, 1), "buy", "100.00", "10")
    # Los 12 meses son de diciembre de 2025 a noviembre de 2026
    op(db, acc, etf, date(2025, 12, 5), "dividend", "1.00")  # dentro
    op(db, acc, etf, date(2025, 11, 20), "dividend", "9.00")  # fuera

    s = summarize(build(db, me.id, TODAY))
    assert [m for m, _ in s.contributions] == ["2025-12"] + [f"2026-{m:02d}" for m in range(1, 12)]
    assert s.contributions[-1] == ("2026-11", D("0.00"))
    assert s.contributions[-2] == ("2026-10", D("100.00"))
    assert s.contributed_12m == D("300.00")
    assert s.streak == 3  # agosto, septiembre y octubre (noviembre aún sin aportar)
    assert (s.dividends, s.dividends_12m) == (D("10.00"), D("1.00"))


def test_empty_portfolio(db):
    me = user(db)
    portfolio = build(db, me.id, TODAY)
    s = summarize(portfolio)
    assert portfolio.ops == [] and portfolio.positions == []
    assert (s.value, s.xirr, s.max_drawdown, s.streak) == (D("0.00"), None, None, 0)


def test_last_months_crosses_the_year():
    assert last_months(date(2026, 2, 10), 4) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]


# ---------------------------------------------------------------- API


@pytest.fixture
def gerard_with_a_position(login):
    """Gerard con una compra hace 30 días y un precio descargado ahora."""
    client = login("gerard")
    today = datetime.now(TZ).date()
    with SessionLocal() as db:
        me = user(db)
        acc = account(db, me, "Scalable")
        etf = product(db, me, "ETF inventado", "AAA.DE", isin="XX0000000002", ter=D("0.002"))
        db.add_all(
            [
                Price(
                    product_id=etf.id,
                    date=today - timedelta(days=30),
                    price=D("10"),
                    currency="EUR",
                    source="yahoo",
                    fetched_at=datetime.now(TZ),
                ),
                Price(
                    product_id=etf.id,
                    date=today,
                    price=D("12.5"),
                    currency="EUR",
                    source="yahoo",
                    fetched_at=datetime.now(TZ),
                ),
            ]
        )
        db.commit()
        op(db, acc, etf, today - timedelta(days=30), "buy", "100.00", "10")
    return client


def test_positions_api(gerard_with_a_position):
    res = gerard_with_a_position.get("/api/investments/positions")
    assert res.status_code == 200
    body = res.json()
    assert body["total_value"] == "125.00"
    [item] = body["items"]
    assert item["name"] == "ETF inventado"
    assert item["isin"] == "XX0000000002"
    assert item["accounts"] == ["Scalable"]
    assert item["shares"] == "10.00000000"
    assert item["average_price"] == "10.000000"
    assert (item["price"], item["price_eur"], item["value"]) == ("12.500000", "12.500000", "125.00")
    assert (item["gain"], item["gain_pct"], item["weight"]) == ("25.00", "0.250000", "1.000000")
    assert item["stale"] is False
    assert item["ter"] == "0.00200"


def test_summary_api(gerard_with_a_position):
    res = gerard_with_a_position.get("/api/investments/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["has_investments"] is True
    assert (body["value"], body["cost"], body["gain"]) == ("125.00", "100.00", "25.00")
    assert body["gain_pct"] == "0.250000"
    assert body["contributed_12m"] == "100.00"
    assert len(body["contributions"]) == 12
    assert body["ter_annual"] == "0.25"
    assert body["missing_prices"] == []
    assert float(body["xirr"]) > 1  # +25 % en 30 días, anualizado
    assert body["max_drawdown"] == "0.000000"


def test_stale_price_is_flagged(login):
    client = login("gerard")
    with SessionLocal() as db:
        me = user(db)
        acc = account(db, me, "Scalable")
        etf = product(db, me, "ETF viejo", "OLD.DE")
        prices(db, etf, {date(2026, 1, 2): "10"})
        db.execute(Price.__table__.update().values(fetched_at=datetime.now(TZ) - timedelta(days=3)))
        db.commit()
        op(db, acc, etf, date(2026, 1, 2), "buy", "100.00", "10")
    [item] = client.get("/api/investments/positions").json()["items"]
    assert item["stale"] is True


def test_each_user_sees_only_their_portfolio(gerard_with_a_position, login):
    padres = login("padres")
    assert padres.get("/api/investments/positions").json() == {"total_value": "0.00", "items": []}
    summary = padres.get("/api/investments/summary").json()
    assert summary["has_investments"] is False
    assert summary["value"] == "0.00"


def test_requires_login(client):
    assert client.get("/api/investments/summary").status_code == 401
    assert client.get("/api/investments/positions").status_code == 401
