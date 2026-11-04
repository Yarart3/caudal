"""Fase 3, parte 3.2c: refresco automático de precios (al arrancar si son antiguos y periódico)."""

import threading
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import Price, Product
from app.prices.auto import TZ, AutoPrices, PricesBusyError, auto_prices, needs_refresh
from tests.test_prices_service import FakeYahoo, product, series

NOW = datetime(2026, 11, 4, 15, 0, tzinfo=TZ)
MAX_AGE = timedelta(hours=6)


def settings(**fields) -> Settings:
    return get_settings().model_copy(update={"price_auto": True, **fields})


def runner(yahoo, **fields) -> AutoPrices:
    return AutoPrices(lambda: settings(**fields), SessionLocal, lambda: yahoo, lambda: NOW)


def add_price(db: Session, item: Product, fetched_at: datetime) -> None:
    db.add(
        Price(
            product_id=item.id,
            date=fetched_at.date(),
            price=Decimal("10"),
            currency="EUR",
            source="yahoo",
            fetched_at=fetched_at,
        )
    )
    db.commit()


# ---------------------------------------------------------------- needs_refresh


def test_nothing_to_refresh_without_products(db: Session) -> None:
    assert needs_refresh(db, NOW, MAX_AGE) is False


def test_a_product_without_price_needs_refresh(db: Session, make_user) -> None:
    product(db, make_user("gerard"), "SXR8.DE")
    assert needs_refresh(db, NOW, MAX_AGE) is True


def test_fresh_and_old_prices(db: Session, make_user) -> None:
    item = product(db, make_user("gerard"), "SXR8.DE")
    add_price(db, item, NOW - timedelta(days=1, hours=1))  # ayer
    assert needs_refresh(db, NOW, MAX_AGE) is True
    add_price(db, item, NOW - timedelta(hours=1))  # hoy, descargado hace poco
    assert needs_refresh(db, NOW, MAX_AGE) is False


def test_one_old_product_is_enough(db: Session, make_user) -> None:
    user = make_user("gerard")
    add_price(db, product(db, user, "A.DE"), NOW - timedelta(hours=1))
    add_price(db, product(db, user, "B.DE"), NOW - timedelta(days=2))
    assert needs_refresh(db, NOW, MAX_AGE) is True


def test_manual_products_never_need_refresh(db: Session, make_user) -> None:
    product(db, make_user("gerard"), None, kind="pension", price_source="manual")
    assert needs_refresh(db, NOW, MAX_AGE) is False


# ---------------------------------------------------------------- AutoPrices


def test_refresh_downloads_and_stores(db: Session, make_user) -> None:
    item = product(db, make_user("gerard"), "SXR8.DE")
    yahoo = FakeYahoo({"SXR8.DE": series("EUR", d20261104="733.1")})
    items = runner(yahoo).refresh()
    assert [(i.symbol, i.ok) for i in items] == [("SXR8.DE", True)]
    stored = db.scalars(select(Price).where(Price.product_id == item.id)).all()
    assert [(p.date, p.price, p.fetched_at) for p in stored] == [
        (date(2026, 11, 4), Decimal("733.100000"), NOW)
    ]


def test_two_refreshes_do_not_overlap(db: Session, make_user) -> None:
    product(db, make_user("gerard"), "SXR8.DE")
    started, release = threading.Event(), threading.Event()

    class SlowYahoo(FakeYahoo):
        def history(self, symbol, start, end):
            started.set()
            release.wait(5)
            return super().history(symbol, start, end)

    prices = runner(SlowYahoo({"SXR8.DE": series("EUR")}))
    worker = threading.Thread(target=prices.refresh)
    worker.start()
    assert started.wait(5)
    with pytest.raises(PricesBusyError, match="Ya se están actualizando"):
        prices.refresh()
    assert prices.refresh_quietly("interval") is None
    release.set()
    worker.join(5)
    assert prices.refresh() is not None  # al acabar, el candado queda libre


def test_refresh_quietly_never_raises(db: Session, make_user) -> None:
    product(db, make_user("gerard"), "SXR8.DE")

    class BrokenYahoo:
        def history(self, symbol, start, end):
            raise RuntimeError("fallo inesperado")

    assert runner(BrokenYahoo()).refresh_quietly("interval") is None


def test_refresh_quietly_returns_yahoo_failures(db: Session, make_user) -> None:
    from app.prices.yahoo import YahooError

    product(db, make_user("gerard"), "SXR8.DE")
    items = runner(FakeYahoo({"SXR8.DE": YahooError("Yahoo no responde")})).refresh_quietly("x")
    assert [(i.symbol, i.ok) for i in items] == [("SXR8.DE", False)]


def test_startup_refreshes_only_when_needed(db: Session, make_user) -> None:
    item = product(db, make_user("gerard"), "SXR8.DE")
    yahoo = FakeYahoo({"SXR8.DE": series("EUR")})
    add_price(db, item, NOW - timedelta(hours=1))
    assert runner(yahoo).startup_check() is None
    assert yahoo.calls == []
    assert runner(yahoo, price_max_age_hours=0).startup_check() is not None
    assert len(yahoo.calls) == 1


def test_thread_refreshes_at_startup_and_stops(db: Session, make_user) -> None:
    product(db, make_user("gerard"), "SXR8.DE")
    yahoo = FakeYahoo({"SXR8.DE": series("EUR")})
    prices = runner(yahoo, price_refresh_min=60)
    prices.start()
    try:
        assert prices.running
        for _ in range(50):  # hasta 5 s
            if yahoo.calls:
                break
            time.sleep(0.1)
        assert len(yahoo.calls) == 1
    finally:
        prices.stop()
    assert not prices.running


def test_thread_does_not_start_when_disabled() -> None:
    prices = runner(FakeYahoo({}), price_auto=False)
    prices.start()
    assert not prices.running


def test_app_does_not_refresh_prices_during_tests(client: TestClient) -> None:
    # PRICE_AUTO=false en conftest: al arrancar la app no se lanza el hilo (ni sale a internet)
    assert not auto_prices.running
