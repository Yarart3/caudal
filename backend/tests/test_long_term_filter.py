"""Fase 5, parte 5.5: «solo largo plazo» en Inversiones (?long_term=true)."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.investments.operations import TZ
from app.investments.portfolio import build, summarize
from app.models import BenchmarkPrice
from tests.test_portfolio import TODAY, account, op, prices, product, user

D = Decimal


def test_build_keeps_only_long_term_products(db) -> None:
    me = user(db)
    broker = account(db, me, "Trade Republic", kind="mixed")
    world = product(db, me, "World inventado", "WLD.DE", long_term=True)
    trade = product(db, me, "Acción a corto inventada", "CRT.DE", kind="stock", long_term=False)
    prices(db, world, {date(2026, 1, 5): "10", date(2026, 11, 3): "12"})
    prices(db, trade, {date(2026, 3, 2): "50", date(2026, 11, 3): "40"})
    op(db, broker, world, date(2026, 1, 5), "buy", "100.00", "10")
    op(db, broker, trade, date(2026, 3, 2), "buy", "500.00", "10")
    op(db, broker, trade, date(2026, 4, 1), "fee", "1.00")

    everything = summarize(build(db, me.id, TODAY))
    assert (everything.value, everything.cost) == (D("520.00"), D("600.00"))

    portfolio = build(db, me.id, TODAY, long_term_only=True)
    assert [p.product.name for p in portfolio.positions] == ["World inventado"]
    only = summarize(portfolio)
    assert (only.value, only.cost, only.gain) == (D("120.00"), D("100.00"), D("20.00"))
    assert only.fees == D("0")  # la comisión era del producto a corto
    assert only.contributed_12m == D("100.00")


@pytest.fixture
def gerard_mixed(login) -> TestClient:
    """Gerard con un ETF a largo plazo y una acción que no lo es, comprados hace 30 días."""
    client = login("gerard")
    today = datetime.now(TZ).date()
    bought = today - timedelta(days=30)
    with SessionLocal() as db:
        me = user(db)
        acc = account(db, me, "Scalable")
        etf = product(db, me, "ETF inventado", "AAA.DE", long_term=True)
        stock = product(db, me, "Acción inventada", "BBB.DE", kind="stock", long_term=False)
        prices(db, etf, {bought: "10", today: "11"})
        prices(db, stock, {bought: "20", today: "30"})
        op(db, acc, etf, bought, "buy", "100.00", "10")
        op(db, acc, stock, bought, "buy", "200.00", "10")
        for day in (bought, today):
            db.add(
                BenchmarkPrice(
                    symbol="EUNL.DE",
                    date=day,
                    price=D("100"),
                    currency="EUR",
                    source="yahoo",
                    fetched_at=datetime.now(TZ),
                )
            )
        db.commit()
    return client


def test_positions_and_summary_api(gerard_mixed: TestClient) -> None:
    all_items = gerard_mixed.get("/api/investments/positions").json()
    assert len(all_items["items"]) == 2
    assert all_items["total_value"] == "410.00"

    only = gerard_mixed.get("/api/investments/positions", params={"long_term": "true"}).json()
    assert [i["name"] for i in only["items"]] == ["ETF inventado"]
    assert only["total_value"] == "110.00"
    assert only["items"][0]["weight"] == "1.000000"

    summary = gerard_mixed.get("/api/investments/summary", params={"long_term": "true"}).json()
    assert (summary["value"], summary["cost"]) == ("110.00", "100.00")
    assert gerard_mixed.get("/api/investments/summary").json()["value"] == "410.00"


def test_benchmark_api(gerard_mixed: TestClient) -> None:
    res = gerard_mixed.get("/api/investments/benchmark", params={"long_term": "true"}).json()
    assert res["value"] == "110.00"
    world = next(i for i in res["items"] if i["symbol"] == "EUNL.DE")
    # Con el índice plano, lo aportado al ETF (100 €) sigue valiendo 100 €
    assert world["value"] == "100.00"
    everything = gerard_mixed.get("/api/investments/benchmark").json()
    assert next(i for i in everything["items"] if i["symbol"] == "EUNL.DE")["value"] == "300.00"


def test_isolation(gerard_mixed: TestClient, login) -> None:
    padres = login("padres")
    res = padres.get("/api/investments/positions", params={"long_term": "true"}).json()
    assert res == {"total_value": "0.00", "items": []}
    summary = padres.get("/api/investments/summary", params={"long_term": "true"}).json()
    assert summary["has_investments"] is False
