"""Fase 3, parte 3.4c: comparativa con un indexado (simulación, descarga de índices y API).

Índices, precios y operaciones inventados; Yahoo simulado.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.investments.benchmark import BENCHMARK_SYMBOLS, BenchmarkPrices, simulate
from app.investments.calc import Op, xirr
from app.investments.operations import TZ
from app.models import Account, BenchmarkPrice, InvestmentOperation, Price, Product, User
from app.prices.service import benchmarks_need_refresh, refresh_benchmarks
from app.prices.yahoo import YahooError
from tests.test_prices_auto import runner
from tests.test_prices_service import FakeYahoo, series

D = Decimal
TODAY = date(2026, 11, 4)  # miércoles
NOW = datetime(2026, 11, 4, 15, 0, tzinfo=TZ)
MAX_AGE = timedelta(hours=6)


def buy(day: date, amount: str) -> Op:
    return Op(day, "buy", D(1), D(amount))


def sell(day: date, amount: str) -> Op:
    return Op(day, "sell", D(1), D(amount))


def index(**closes: str) -> BenchmarkPrices:
    """index(d20260105="100") → cierres en euros."""
    return BenchmarkPrices.from_rows(
        [
            (datetime.strptime(k[1:], "%Y%m%d").date(), D(v))  # noqa: DTZ007
            for k, v in closes.items()
        ]
    )


# ---------------------------------------------------------------- simulate


def test_same_buys_in_the_index():
    # 1.000 € a 100 (10 part.) y 500 € a 125 (4 part.): 14 × 150 = 2.100 €
    prices = index(d20260105="100", d20260302="125", d20261103="150")
    ops = [buy(date(2026, 1, 5), "1000.00"), buy(date(2026, 3, 2), "500.00")]
    sim = simulate(ops, prices, TODAY)
    assert sim.shares == D(14)
    assert sim.value == D("2100.00")
    assert sim.price_date == date(2026, 11, 3)  # el 4 aún no hay cierre: el del 3
    expected = xirr(
        [
            (date(2026, 1, 5), D("-1000.00")),
            (date(2026, 3, 2), D("-500.00")),
            (TODAY, D("2100.00")),
        ]
    )
    assert sim.xirr == expected


def test_a_sale_sells_the_same_euros():
    # Compra 1.000 € a 100 (10 part.); vende 600 € a 120 (5 part.); quedan 5 a 130 = 650 €
    prices = index(d20260105="100", d20260601="120", d20261103="130")
    ops = [buy(date(2026, 1, 5), "1000.00"), sell(date(2026, 6, 1), "600.00")]
    sim = simulate(ops, prices, TODAY)
    assert (sim.shares, sim.value) == (D(5), D("650.00"))


def test_a_sale_bigger_than_the_index_position_sells_everything():
    # En la cartera real se ganó más: se venden 300 €, pero en el índice solo hay 1 × 110
    prices = index(d20260105="100", d20260601="110")
    ops = [buy(date(2026, 1, 5), "100.00"), sell(date(2026, 6, 1), "300.00")]
    sim = simulate(ops, prices, TODAY)
    assert (sim.shares, sim.value) == (D(0), D("0.00"))
    assert sim.xirr == xirr([(date(2026, 1, 5), D("-100.00")), (date(2026, 6, 1), D("110.00"))])


def test_weekend_operations_use_the_previous_close():
    # Compra un domingo: el cierre del viernes
    prices = index(d20260306="100", d20260309="200", d20261103="100")
    sim = simulate([buy(date(2026, 3, 8), "1000.00")], prices, TODAY)
    assert sim.shares == D(10)


def test_index_younger_than_the_operations():
    # Hasta 7 días antes del primer cierre se usa ese cierre; más, no se compara
    prices = index(d20260110="100", d20261103="120")
    assert simulate([buy(date(2026, 1, 5), "100.00")], prices, TODAY).value == D("120.00")
    late = simulate([buy(date(2026, 1, 2), "100.00")], prices, TODAY)
    assert (late.value, late.xirr) == (None, None)
    assert simulate([buy(TODAY, "1")], index(), TODAY).value is None


def test_dividends_and_fees_are_not_repeated():
    prices = index(d20260105="100", d20261103="100")
    ops = [
        buy(date(2026, 1, 5), "1000.00"),
        Op(date(2026, 6, 1), "dividend", D(0), D("50.00")),
        Op(date(2026, 7, 1), "fee", D(0), D("5.00")),
    ]
    assert simulate(ops, prices, TODAY).value == D("1000.00")


def test_without_operations():
    sim = simulate([], index(d20261103="100"), TODAY)
    assert (sim.value, sim.xirr) == (D("0.00"), None)


# ---------------------------------------------------------------- descarga de los índices


def gerard_with_an_operation(db: Session, day: date = date(2026, 1, 5)) -> None:
    user = User(username="gerard", display_name="Gerard", color="#0E6B58", password_hash="x")
    db.add(user)
    db.commit()
    acc = Account(user_id=user.id, name="Scalable", kind="investment")
    prod = Product(user_id=user.id, name="ETF", kind="etf", price_source="yahoo", source_id="A.DE")
    db.add_all([acc, prod])
    db.commit()
    db.add(
        InvestmentOperation(
            account_id=acc.id,
            product_id=prod.id,
            date=day,
            kind="buy",
            shares=D(1),
            amount_eur=D("100.00"),
        )
    )
    db.commit()


def stored(db: Session, symbol: str) -> dict[date, tuple[Decimal, str]]:
    rows = db.scalars(
        select(BenchmarkPrice).where(BenchmarkPrice.symbol == symbol).order_by(BenchmarkPrice.date)
    )
    return {r.date: (r.price, r.currency) for r in rows}


def test_no_operations_no_download(db):
    yahoo = FakeYahoo({})
    assert refresh_benchmarks(db, yahoo, BENCHMARK_SYMBOLS, TODAY, NOW) == []
    assert yahoo.calls == []
    assert benchmarks_need_refresh(db, BENCHMARK_SYMBOLS, NOW, MAX_AGE) is False


def test_downloads_from_the_first_operation_then_continues(db):
    gerard_with_an_operation(db)
    yahoo = FakeYahoo({"EUNL.DE": series("EUR", d20260105="90.1", d20261104="110.5")})
    items = refresh_benchmarks(db, yahoo, ["EUNL.DE"], TODAY, NOW)
    assert [(i.symbol, i.ok, i.days) for i in items] == [("EUNL.DE", True, 2)]
    assert yahoo.calls == [("EUNL.DE", date(2026, 1, 5), TODAY)]
    assert stored(db, "EUNL.DE")[date(2026, 11, 4)] == (D("110.500000"), "EUR")
    # La segunda vez, desde el último cierre guardado
    refresh_benchmarks(db, yahoo, ["EUNL.DE"], TODAY, NOW)
    assert yahoo.calls[-1] == ("EUNL.DE", TODAY, TODAY)


def test_an_older_operation_downloads_again_from_it(db):
    gerard_with_an_operation(db)
    yahoo = FakeYahoo({"EUNL.DE": series("EUR", d20260105="90")})
    refresh_benchmarks(db, yahoo, ["EUNL.DE"], TODAY, NOW)
    gerard_operation = db.scalar(select(InvestmentOperation))
    gerard_operation.date = date(2025, 3, 3)
    db.commit()
    refresh_benchmarks(db, yahoo, ["EUNL.DE"], TODAY, NOW)
    assert yahoo.calls[-1] == ("EUNL.DE", date(2025, 3, 3), TODAY)


def test_a_failure_does_not_stop_the_others_and_foreign_currency_brings_rates(db):
    gerard_with_an_operation(db)
    yahoo = FakeYahoo(
        {
            "MALO.DE": YahooError("Yahoo no responde"),
            "IWDA.L": series("GBp", d20261104="9000"),
            "GBPEUR=X": series("EUR", d20261104="1.15"),
        }
    )
    items = refresh_benchmarks(db, yahoo, ["MALO.DE", "IWDA.L"], TODAY, NOW)
    assert [(i.symbol, i.ok) for i in items] == [
        ("MALO.DE", False),
        ("IWDA.L", True),
        ("GBPEUR=X", True),
    ]
    assert stored(db, "IWDA.L") == {TODAY: (D("90.000000"), "GBP")}
    # En euros: 90 GBP × 1,15
    assert BenchmarkPrices(db, "IWDA.L").at(TODAY) == (TODAY, D("103.500000"))


def test_benchmarks_need_refresh(db):
    gerard_with_an_operation(db)
    symbols = ["EUNL.DE", "SXR8.DE"]
    assert benchmarks_need_refresh(db, symbols, NOW, MAX_AGE) is True  # sin cierres
    for symbol, fetched in (("EUNL.DE", NOW), ("SXR8.DE", NOW - timedelta(hours=1))):
        db.add(
            BenchmarkPrice(
                symbol=symbol,
                date=TODAY,
                price=D(1),
                currency="EUR",
                source="yahoo",
                fetched_at=fetched,
            )
        )
    db.commit()
    assert benchmarks_need_refresh(db, symbols, NOW, MAX_AGE) is False
    assert benchmarks_need_refresh(db, symbols, NOW + timedelta(hours=6, minutes=1), MAX_AGE)


def test_the_price_refresh_also_updates_the_benchmarks(db):
    gerard_with_an_operation(db)
    data = {s: series("EUR", d20261104="100") for s in BENCHMARK_SYMBOLS}
    data["A.DE"] = series("EUR", d20261104="10")
    yahoo = FakeYahoo(data)
    items = runner(yahoo).refresh()
    assert [i.symbol for i in items] == ["A.DE", *BENCHMARK_SYMBOLS]
    # Al arrancar: con todo recién bajado no hace nada
    calls = len(yahoo.calls)
    assert runner(yahoo).startup_check() is None
    assert len(yahoo.calls) == calls


def test_startup_downloads_missing_benchmarks(db):
    gerard_with_an_operation(db)
    data = {s: series("EUR") for s in BENCHMARK_SYMBOLS}
    data["A.DE"] = series("EUR")
    yahoo = FakeYahoo(data)
    assert runner(yahoo).startup_check() is not None
    assert {c[0] for c in yahoo.calls} >= set(BENCHMARK_SYMBOLS)


# ---------------------------------------------------------------- API


def test_benchmark_api(login):
    client = login("gerard")
    today = datetime.now(TZ).date()
    start = today - timedelta(days=60)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "gerard"))
        acc = Account(user_id=user.id, name="Scalable", kind="investment")
        prod = Product(
            user_id=user.id, name="ETF", kind="etf", price_source="yahoo", source_id="A.DE"
        )
        db.add_all([acc, prod])
        db.commit()
        db.add(
            InvestmentOperation(
                account_id=acc.id,
                product_id=prod.id,
                date=start,
                kind="buy",
                shares=D(10),
                amount_eur=D("1000.00"),
            )
        )
        for day, price in ((start, "100"), (today, "110")):
            db.add(
                Price(
                    product_id=prod.id,
                    date=day,
                    price=D(price),
                    currency="EUR",
                    source="yahoo",
                    fetched_at=NOW,
                )
            )
        # MSCI World sube a 120 y S&P 500 baja a 95; el monetario no tiene cierres
        for symbol, end in (("EUNL.DE", "120"), ("SXR8.DE", "95")):
            for day, price in ((start, "100"), (today, end)):
                db.add(
                    BenchmarkPrice(
                        symbol=symbol, date=day, price=D(price), currency="EUR", source="yahoo"
                    )
                )
        db.commit()

    body = client.get("/api/investments/benchmark").json()
    assert body["has_investments"] is True
    assert body["value"] == "1100.00"
    world, sp500, money = body["items"]
    assert (world["key"], world["symbol"], world["name"]) == (
        "msci_world",
        "EUNL.DE",
        "MSCI World (IWDA)",
    )
    assert (world["available"], world["value"], world["diff"]) == (True, "1200.00", "100.00")
    assert (sp500["value"], sp500["diff"]) == ("950.00", "-150.00")
    assert world["price_date"] == today.isoformat()
    assert float(world["xirr"]) > float(body["xirr"]) > float(sp500["xirr"])
    assert (money["available"], money["value"], money["diff"]) == (False, None, None)

    # Los padres no ven nada de Gerard (los índices son públicos, sus operaciones no)
    padres = login("padres").get("/api/investments/benchmark").json()
    assert padres["has_investments"] is False
    assert padres["value"] == "0.00"
    assert all(item["value"] in ("0.00", None) for item in padres["items"])


def test_benchmark_requires_login(client):
    assert client.get("/api/investments/benchmark").status_code == 401
