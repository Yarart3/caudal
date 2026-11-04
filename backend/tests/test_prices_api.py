"""Fase 3, parte 3.2c: GET /api/prices/status y POST /api/prices/refresh."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.prices import prices_runner, prices_settings
from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models import Price, Product, User
from app.prices.auto import TZ, AutoPrices
from tests.test_prices_service import FakeYahoo, series


@pytest.fixture
def yahoo() -> Iterator[FakeYahoo]:
    fake = FakeYahoo({})
    prices = AutoPrices(get_settings, SessionLocal, lambda: fake)
    app.dependency_overrides[prices_runner] = lambda: prices
    yield fake
    app.dependency_overrides.pop(prices_runner, None)


def user_id(username: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.username == username))


def add_product(username: str, symbol: str | None, name: str, **fields) -> int:
    fields.setdefault("kind", "etf")
    fields.setdefault("price_source", "yahoo")
    with SessionLocal() as db:
        row = Product(user_id=user_id(username), name=name, source_id=symbol, **fields)
        db.add(row)
        db.commit()
        return row.id


def add_price(product_id: int, hours_ago: float, price: str = "10") -> None:
    fetched = datetime.now(TZ) - timedelta(hours=hours_ago)
    with SessionLocal() as db:
        db.add(
            Price(
                product_id=product_id,
                date=fetched.date(),
                price=Decimal(price),
                currency="EUR",
                source="yahoo",
                fetched_at=fetched,
            )
        )
        db.commit()


def test_login_is_required(client: TestClient) -> None:
    assert client.get("/api/prices/status").status_code == 401
    assert client.post("/api/prices/refresh").status_code == 401


def test_status_without_products(login) -> None:
    status = login("gerard").get("/api/prices/status").json()
    assert status == {"last_refresh": None, "stale": False, "max_age_hours": 6, "products": []}


def test_status_shows_price_and_staleness(login) -> None:
    client = login("gerard")
    fresh = add_product("gerard", "SXR8.DE", "Core S&P 500")
    old = add_product("gerard", "IUSQ.DE", "MSCI ACWI")
    add_price(fresh, 1, "731.400024")
    add_price(old, 7)
    status = client.get("/api/prices/status").json()
    rows = {row["symbol"]: row for row in status["products"]}
    assert rows["SXR8.DE"]["price"] == "731.400024"
    assert rows["SXR8.DE"]["currency"] == "EUR"
    assert rows["SXR8.DE"]["stale"] is False
    assert rows["IUSQ.DE"]["stale"] is True
    assert status["stale"] is True


def test_max_age_comes_from_settings(login) -> None:
    client = login("gerard")
    add_price(add_product("gerard", "SXR8.DE", "Core S&P 500"), 7)
    longer = get_settings().model_copy(update={"price_max_age_hours": 24})
    app.dependency_overrides[prices_settings] = lambda: longer
    try:
        status = client.get("/api/prices/status").json()
    finally:
        app.dependency_overrides.pop(prices_settings, None)
    assert (status["max_age_hours"], status["stale"]) == (24, False)


def test_status_is_isolated_between_users(login) -> None:
    gerard, padres = login("gerard"), login("padres")
    add_product("gerard", "SXR8.DE", "Mío")
    add_product("padres", "IUSQ.DE", "De mis padres")
    assert [p["name"] for p in gerard.get("/api/prices/status").json()["products"]] == ["Mío"]
    names = [p["name"] for p in padres.get("/api/prices/status").json()["products"]]
    assert names == ["De mis padres"]


def test_refresh_updates_only_the_users_products(login, yahoo: FakeYahoo) -> None:
    client = login("gerard")
    login("padres")
    add_product("gerard", "SXR8.DE", "Mío")
    add_product("padres", "IUSQ.DE", "De mis padres")
    today = datetime.now(TZ).strftime("d%Y%m%d")
    yahoo.data.update({"SXR8.DE": series("EUR", **{today: "733.1"}), "IUSQ.DE": series("EUR")})
    res = client.post("/api/prices/refresh")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == [{"symbol": "SXR8.DE", "ok": True, "days": 1, "message": None}]
    assert [call[0] for call in yahoo.calls] == ["SXR8.DE"]
    product = body["status"]["products"][0]
    assert (product["price"], product["stale"]) == ("733.100000", False)
    assert body["status"]["stale"] is False


def test_refresh_reports_yahoo_errors(login, yahoo: FakeYahoo) -> None:
    from app.prices.yahoo import YahooError

    client = login("gerard")
    add_product("gerard", "SXR8.DE", "Mío")
    yahoo.data["SXR8.DE"] = YahooError("Yahoo no responde (sin red)")
    body = client.post("/api/prices/refresh").json()
    assert body["items"] == [
        {"symbol": "SXR8.DE", "ok": False, "days": 0, "message": "Yahoo no responde (sin red)"}
    ]
    assert body["status"]["stale"] is True


def test_refresh_while_another_is_running_is_a_conflict(login, yahoo: FakeYahoo) -> None:
    client = login("gerard")
    busy = app.dependency_overrides[prices_runner]()
    busy._lock.acquire()
    try:
        res = client.post("/api/prices/refresh")
    finally:
        busy._lock.release()
    assert res.status_code == 409
    assert res.json() == {"detail": "Ya se están actualizando los precios. Prueba en un momento."}
