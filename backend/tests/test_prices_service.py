"""Fase 3, parte 3.2b: servicio de precios (histórico, divisas y precios desactualizados)."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, ExchangeRate, InvestmentOperation, Price, Product, User
from app.prices.service import (
    normalize_currency,
    price_status,
    refresh_prices,
    to_eur,
)
from app.prices.yahoo import DailyClose, History, SymbolNotFoundError

TZ = ZoneInfo("Europe/Madrid")
TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 15, 0, tzinfo=TZ)
MAX_AGE = timedelta(hours=6)


class FakeYahoo:
    """Yahoo simulado: {símbolo: History o excepción}. Guarda qué se le ha pedido."""

    def __init__(self, data: dict) -> None:
        self.data = data
        self.calls: list[tuple[str, date, date]] = []

    def history(self, symbol: str, start: date, end: date) -> History:
        self.calls.append((symbol, start, end))
        value = self.data[symbol]
        if isinstance(value, Exception):
            raise value
        return value


def series(currency: str, **prices: str) -> History:
    """series("EUR", d20261103="100.5") → History con esos cierres."""
    closes = [
        DailyClose(datetime.strptime(key[1:], "%Y%m%d").date(), Decimal(value))  # noqa: DTZ007
        for key, value in prices.items()
    ]
    return History(currency, closes)


def product(db: Session, user: User, symbol: str | None, **fields) -> Product:
    fields.setdefault("name", f"Producto {symbol}")
    fields.setdefault("kind", "etf")
    fields.setdefault("price_source", "yahoo")
    row = Product(user_id=user.id, source_id=symbol, **fields)
    db.add(row)
    db.commit()
    return row


def prices(db: Session, item: Product) -> dict[date, tuple[Decimal, str]]:
    rows = db.scalars(select(Price).where(Price.product_id == item.id).order_by(Price.date))
    return {row.date: (row.price, row.currency) for row in rows}


# ---------------------------------------------------------------- normalize_currency


def test_pence_are_converted_to_pounds() -> None:
    assert normalize_currency("GBp", Decimal("2751.500000")) == ("GBP", Decimal("27.515000"))
    assert normalize_currency("GBX", Decimal("100")) == ("GBP", Decimal("1.000000"))


def test_other_currencies_are_kept() -> None:
    assert normalize_currency("usd", Decimal("9.37")) == ("USD", Decimal("9.37"))
    assert normalize_currency("EUR", Decimal("1")) == ("EUR", Decimal("1"))


# ---------------------------------------------------------------- refresh_prices


def test_new_product_downloads_one_year_and_stores_it(db: Session, make_user) -> None:
    item = product(db, make_user("gerard"), "SXR8.DE")
    yahoo = FakeYahoo({"SXR8.DE": series("EUR", d20261103="731.400024", d20261104="733.1")})
    items = refresh_prices(db, yahoo, TODAY, NOW)
    assert yahoo.calls == [("SXR8.DE", date(2025, 11, 4), TODAY)]
    assert [(i.symbol, i.ok, i.days) for i in items] == [("SXR8.DE", True, 2)]
    assert prices(db, item) == {
        date(2026, 11, 3): (Decimal("731.400024"), "EUR"),
        date(2026, 11, 4): (Decimal("733.100000"), "EUR"),
    }
    stored = db.scalars(select(Price)).first()
    assert (stored.source, stored.fetched_at) == ("yahoo", NOW)


def test_history_starts_at_the_first_operation(db: Session, make_user) -> None:
    user = make_user("gerard")
    item = product(db, user, "SXR8.DE")
    account = Account(user_id=user.id, name="Trade Republic", kind="mixed")
    db.add(account)
    db.commit()
    for day in (date(2023, 5, 2), date(2021, 3, 15)):
        db.add(
            InvestmentOperation(
                account_id=account.id,
                product_id=item.id,
                date=day,
                kind="buy",
                shares=Decimal(1),
                amount_eur=Decimal("100.00"),
            )
        )
    db.commit()
    yahoo = FakeYahoo({"SXR8.DE": series("EUR")})
    refresh_prices(db, yahoo, TODAY, NOW)
    assert yahoo.calls == [("SXR8.DE", date(2021, 3, 15), TODAY)]


def test_an_operation_older_than_the_prices_brings_older_history(db: Session, make_user) -> None:
    user = make_user("gerard")
    item = product(db, user, "SXR8.DE")
    db.add(
        Price(
            product_id=item.id,
            date=date(2026, 11, 3),
            price=Decimal("725"),
            currency="EUR",
            source="yahoo",
        )
    )
    account = Account(user_id=user.id, name="Scalable", kind="investment")
    db.add(account)
    db.commit()
    db.add(
        InvestmentOperation(
            account_id=account.id,
            product_id=item.id,
            date=date(2024, 6, 3),
            kind="buy",
            shares=Decimal(1),
            amount_eur=Decimal("500.00"),
        )
    )
    db.commit()
    yahoo = FakeYahoo({"SXR8.DE": series("EUR")})
    refresh_prices(db, yahoo, TODAY, NOW)
    assert yahoo.calls == [("SXR8.DE", date(2024, 6, 3), TODAY)]


def test_refresh_continues_from_the_last_price_and_overwrites_it(db: Session, make_user) -> None:
    item = product(db, make_user("gerard"), "SXR8.DE")
    earlier = NOW - timedelta(days=1)
    for day, value in ((date(2026, 11, 2), "720"), (date(2026, 11, 3), "725")):
        db.add(
            Price(
                product_id=item.id,
                date=day,
                price=Decimal(value),
                currency="EUR",
                source="yahoo",
                fetched_at=earlier,
            )
        )
    db.commit()
    yahoo = FakeYahoo({"SXR8.DE": series("EUR", d20261103="731.4", d20261104="733.1")})
    refresh_prices(db, yahoo, TODAY, NOW)
    assert yahoo.calls == [("SXR8.DE", date(2026, 11, 3), TODAY)]
    stored = prices(db, item)
    assert stored[date(2026, 11, 2)] == (Decimal("720.000000"), "EUR")  # no se ha vuelto a pedir
    assert stored[date(2026, 11, 3)] == (Decimal("731.400000"), "EUR")  # corregido
    assert stored[date(2026, 11, 4)] == (Decimal("733.100000"), "EUR")
    refreshed = db.scalar(select(Price).where(Price.date == date(2026, 11, 3)))
    assert refreshed.fetched_at == NOW


def test_a_symbol_shared_by_two_users_is_downloaded_once(db: Session, make_user) -> None:
    mine = product(db, make_user("gerard"), "SXR8.DE")
    theirs = product(db, make_user("padres"), "SXR8.DE")
    yahoo = FakeYahoo({"SXR8.DE": series("EUR", d20261104="733.1")})
    refresh_prices(db, yahoo, TODAY, NOW)
    assert len(yahoo.calls) == 1
    assert prices(db, mine) == prices(db, theirs) == {date(2026, 11, 4): (Decimal("733.1"), "EUR")}


def test_one_failing_symbol_does_not_stop_the_others(db: Session, make_user) -> None:
    user = make_user("gerard")
    product(db, user, "MALO.DE")
    good = product(db, user, "SXR8.DE")
    yahoo = FakeYahoo(
        {
            "MALO.DE": SymbolNotFoundError("Yahoo no conoce ese símbolo"),
            "SXR8.DE": series("EUR", d20261104="733.1"),
        }
    )
    items = refresh_prices(db, yahoo, TODAY, NOW)
    assert [(i.symbol, i.ok, i.message) for i in items] == [
        ("MALO.DE", False, "Yahoo no conoce ese símbolo"),
        ("SXR8.DE", True, None),
    ]
    assert prices(db, good) == {date(2026, 11, 4): (Decimal("733.1"), "EUR")}


def test_products_without_automatic_price_are_skipped(db: Session, make_user) -> None:
    user = make_user("gerard")
    product(db, user, None)
    product(db, user, "PLAN-1", kind="pension", price_source="manual")
    yahoo = FakeYahoo({})
    assert refresh_prices(db, yahoo, TODAY, NOW) == []
    assert yahoo.calls == []


def test_refresh_can_be_limited_to_one_user(db: Session, make_user) -> None:
    gerard, padres = make_user("gerard"), make_user("padres")
    product(db, gerard, "SXR8.DE")
    product(db, padres, "IUSQ.DE")
    yahoo = FakeYahoo({"SXR8.DE": series("EUR"), "IUSQ.DE": series("EUR")})
    refresh_prices(db, yahoo, TODAY, NOW, user_id=padres.id)
    assert [call[0] for call in yahoo.calls] == ["IUSQ.DE"]


def test_foreign_prices_bring_their_exchange_rates(db: Session, make_user) -> None:
    user = make_user("gerard")
    in_pence = product(db, user, "AIAG.L")
    product(db, user, "FWRA.L")
    product(db, user, "SXR8.DE")
    yahoo = FakeYahoo(
        {
            "AIAG.L": series("GBp", d20261104="2751.5"),
            "FWRA.L": series("USD", d20261104="9.37"),
            "SXR8.DE": series("EUR", d20261104="733.1"),
            "GBPEUR=X": series("EUR", d20261104="1.141234"),
            "USDEUR=X": series("EUR", d20261103="0.861", d20261104="0.862345"),
        }
    )
    items = refresh_prices(db, yahoo, TODAY, NOW)
    assert prices(db, in_pence) == {date(2026, 11, 4): (Decimal("27.515000"), "GBP")}
    # Un tipo de cambio por divisa (no por producto), y nunca para EUR
    assert sorted(call[0] for call in yahoo.calls if call[0].endswith("=X")) == [
        "GBPEUR=X",
        "USDEUR=X",
    ]
    assert [i.symbol for i in items][-2:] == ["GBPEUR=X", "USDEUR=X"]
    rates = {(r.currency, r.date): r.rate for r in db.scalars(select(ExchangeRate))}
    assert rates == {
        ("GBP", date(2026, 11, 4)): Decimal("1.141234"),
        ("USD", date(2026, 11, 3)): Decimal("0.861000"),
        ("USD", date(2026, 11, 4)): Decimal("0.862345"),
    }


def test_exchange_rates_continue_from_the_last_one(db: Session, make_user) -> None:
    item = product(db, make_user("gerard"), "FWRA.L")
    db.add(
        Price(
            product_id=item.id,
            date=date(2026, 10, 1),
            price=Decimal("9"),
            currency="USD",
            source="yahoo",
        )
    )
    for day in (date(2026, 9, 1), date(2026, 11, 2)):
        db.add(ExchangeRate(currency="USD", date=day, rate=Decimal("0.86"), source="yahoo"))
    db.commit()
    yahoo = FakeYahoo({"FWRA.L": series("USD"), "USDEUR=X": series("EUR")})
    refresh_prices(db, yahoo, TODAY, NOW)
    assert ("USDEUR=X", date(2026, 11, 2), TODAY) in yahoo.calls


def test_older_prices_need_older_exchange_rates(db: Session, make_user) -> None:
    product(db, make_user("gerard"), "FWRA.L")  # sin precios: se piden desde hace un año
    db.add(
        ExchangeRate(currency="USD", date=date(2026, 11, 2), rate=Decimal("0.86"), source="yahoo")
    )
    db.commit()
    yahoo = FakeYahoo({"FWRA.L": series("USD"), "USDEUR=X": series("EUR")})
    refresh_prices(db, yahoo, TODAY, NOW)
    assert ("USDEUR=X", date(2025, 11, 4), TODAY) in yahoo.calls


def test_failing_exchange_rate_is_reported(db: Session, make_user) -> None:
    product(db, make_user("gerard"), "FWRA.L")
    yahoo = FakeYahoo(
        {
            "FWRA.L": series("USD", d20261104="9.37"),
            "USDEUR=X": SymbolNotFoundError("Yahoo no tiene datos de USDEUR=X"),
        }
    )
    items = refresh_prices(db, yahoo, TODAY, NOW)
    assert (items[-1].symbol, items[-1].ok) == ("USDEUR=X", False)


# ---------------------------------------------------------------- to_eur


def test_euros_need_no_exchange_rate(db: Session) -> None:
    assert to_eur(db, Decimal("10.50"), "EUR", TODAY) == Decimal("10.50")


def test_to_eur_uses_the_rate_of_that_day_or_the_previous_one(db: Session) -> None:
    db.add(
        ExchangeRate(currency="USD", date=date(2026, 10, 30), rate=Decimal("0.86"), source="yahoo")
    )
    db.add(
        ExchangeRate(currency="USD", date=date(2026, 11, 2), rate=Decimal("0.87"), source="yahoo")
    )
    db.commit()
    assert to_eur(db, Decimal("100"), "USD", date(2026, 10, 30)) == Decimal("86.00")
    # Sábado 31: vale el viernes 30
    assert to_eur(db, Decimal("100"), "USD", date(2026, 10, 31)) == Decimal("86.00")
    assert to_eur(db, Decimal("100"), "USD", date(2026, 11, 4)) == Decimal("87.00")
    assert to_eur(db, Decimal("100"), "USD", date(2026, 10, 29)) is None
    assert to_eur(db, Decimal("100"), "GBP", TODAY) is None


# ---------------------------------------------------------------- price_status


def _price(db: Session, item: Product, day: date, fetched_at: datetime) -> None:
    db.add(
        Price(
            product_id=item.id,
            date=day,
            price=Decimal("10"),
            currency="EUR",
            source="yahoo",
            fetched_at=fetched_at,
        )
    )
    db.commit()


def test_status_marks_old_downloads_as_stale(db: Session, make_user) -> None:
    user = make_user("gerard")
    fresh = product(db, user, "A.DE", name="A")
    old = product(db, user, "B.DE", name="B")
    missing = product(db, user, "C.DE", name="C")
    _price(db, fresh, date(2026, 10, 30), NOW - timedelta(hours=1))  # viernes, bajado hoy
    _price(db, old, date(2026, 11, 3), NOW - timedelta(hours=7))
    status = price_status(db, user.id, NOW, MAX_AGE)
    by_name = {row.name: row for row in status.products}
    assert by_name["A"].stale is False
    assert by_name["A"].date == date(2026, 10, 30)
    assert by_name["B"].stale is True
    assert (by_name["C"].stale, by_name["C"].price) == (True, None)
    assert status.stale is True
    assert status.last_refresh == NOW - timedelta(hours=1)
    assert [row.product_id for row in status.products] == [fresh.id, old.id, missing.id]


def test_status_with_everything_fresh(db: Session, make_user) -> None:
    user = make_user("gerard")
    _price(db, product(db, user, "A.DE"), TODAY, NOW - timedelta(minutes=5))
    status = price_status(db, user.id, NOW, MAX_AGE)
    assert status.stale is False


def test_status_uses_the_latest_price(db: Session, make_user) -> None:
    user = make_user("gerard")
    item = product(db, user, "A.DE")
    _price(db, item, date(2026, 11, 3), NOW - timedelta(days=2))
    _price(db, item, TODAY, NOW)
    row = price_status(db, user.id, NOW, MAX_AGE).products[0]
    assert (row.date, row.stale) == (TODAY, False)


def test_status_only_shows_the_users_own_automatic_products(db: Session, make_user) -> None:
    gerard, padres = make_user("gerard"), make_user("padres")
    product(db, gerard, "A.DE", name="Mío")
    product(db, gerard, None, name="Plan", kind="pension", price_source="manual")
    product(db, padres, "B.DE", name="De mis padres")
    status = price_status(db, gerard.id, NOW, MAX_AGE)
    assert [row.name for row in status.products] == ["Mío"]


def test_status_without_products(db: Session, make_user) -> None:
    status = price_status(db, make_user("gerard").id, NOW, MAX_AGE)
    assert (status.last_refresh, status.stale, status.products) == (None, False, [])


@pytest.mark.parametrize("hours", [5.9, 6.0])
def test_status_limit_is_inclusive(db: Session, make_user, hours: float) -> None:
    user = make_user("gerard")
    _price(db, product(db, user, "A.DE"), TODAY, NOW - timedelta(hours=hours))
    assert price_status(db, user.id, NOW, MAX_AGE).stale is False
