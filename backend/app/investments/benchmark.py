"""«¿Y si todo fuera a un indexado?» (Fase 3, parte 3.4c; DISENO §7.4).

Se repiten las compras y ventas del usuario, en las mismas fechas y por el mismo importe en
euros, en tres índices de referencia, y se compara lo que valdría hoy con lo que vale de verdad:

- Compra de X €: se compran X € del índice al cierre de ese día (o el último anterior).
- Venta de X €: se venden X € del índice (o todo lo que quede, si no llega).
- Dividendos y comisiones sueltas no se repiten: los tres son de acumulación (reinvierten) y
  una comisión no es una aportación.

Los flujos de dinero son los mismos que los reales, así que la diferencia está solo en el valor
final. Los índices se guardan en `benchmark_prices` (datos públicos, para todos los usuarios).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.investments.calc import ZERO, Op, cents, chronological, xirr
from app.investments.portfolio import DateSeries
from app.models import BenchmarkPrice, ExchangeRate

# Si la primera operación es unos días anterior al primer cierre guardado (festivos, fin de
# semana), se usa ese primer cierre. Más allá, el índice no existía aún: no se compara.
GRACE = timedelta(days=7)


@dataclass(frozen=True)
class Benchmark:
    key: str
    name: str
    symbol: str  # símbolo de Yahoo (cotización en euros en Xetra)


BENCHMARKS = (
    # iShares Core MSCI World (IE00B4L5Y983): IWDA en Ámsterdam y Londres, EUNL en Xetra (EUR)
    Benchmark("msci_world", "MSCI World (IWDA)", "EUNL.DE"),
    # iShares Core S&P 500 (IE00B5BMR087)
    Benchmark("sp500", "S&P 500 (SXR8)", "SXR8.DE"),
    # Xtrackers II EUR Overnight Rate Swap (LU0290358497): monetario del euro
    Benchmark("money_market", "Monetario del euro (XEON)", "XEON.DE"),
)
BENCHMARK_SYMBOLS = tuple(b.symbol for b in BENCHMARKS)


class BenchmarkPrices:
    """Cierres en euros de un índice, ya cargados."""

    def __init__(self, db: Session, symbol: str) -> None:
        rows = db.execute(
            select(BenchmarkPrice.date, BenchmarkPrice.price, BenchmarkPrice.currency).where(
                BenchmarkPrice.symbol == symbol
            )
        ).all()
        rates: dict[str, DateSeries] = {}
        for currency in {r.currency for r in rows} - {"EUR"}:
            rates[currency] = DateSeries(
                [
                    (r.date, r.rate)
                    for r in db.execute(
                        select(ExchangeRate.date, ExchangeRate.rate).where(
                            ExchangeRate.currency == currency
                        )
                    )
                ]
            )
        in_eur = []
        for r in rows:
            if r.currency == "EUR":
                in_eur.append((r.date, r.price))
            else:
                rate = rates[r.currency].at(r.date)
                if rate is not None:
                    in_eur.append((r.date, r.price * rate))
        self.series = DateSeries(in_eur)

    @classmethod
    def from_rows(cls, rows: list[tuple[date, Decimal]]) -> "BenchmarkPrices":
        """Para los tests: cierres ya en euros."""
        prices = cls.__new__(cls)
        prices.series = DateSeries(list(rows))
        return prices

    def at(self, day: date) -> tuple[date, Decimal] | None:
        """(fecha, cierre en euros) del día o el último anterior; si no hay, el primero si cae
        dentro de `GRACE`."""
        found = self.series.last(day)
        if found is not None:
            return found
        dates = self.series.dates
        if dates and dates[0] - day <= GRACE:
            return dates[0], self.series.values[0]
        return None


@dataclass(frozen=True)
class Simulation:
    value: Decimal | None  # None: el índice no tiene precio para alguna fecha (no se compara)
    xirr: Decimal | None
    price_date: date | None  # fecha del cierre usado para el valor de hoy
    shares: Decimal


def simulate(ops: list[Op], prices: BenchmarkPrices, today: date) -> Simulation:
    """Repite las compras y ventas de `ops` en el índice. Ver la explicación del módulo."""
    shares = ZERO
    flows: list[tuple[date, Decimal]] = []
    for op in chronological(ops):
        if op.kind not in ("buy", "sell"):
            continue
        quote = prices.at(op.date)
        if quote is None:
            return Simulation(None, None, None, ZERO)
        price = quote[1]
        if op.kind == "buy":
            shares += op.amount / price
            flows.append((op.date, -op.amount))
        else:
            sold = min(shares, op.amount / price)
            shares -= sold
            flows.append((op.date, cents(sold * price)))
    if not flows:
        return Simulation(cents(ZERO), None, None, ZERO)
    last = prices.at(today)
    if last is None:
        return Simulation(None, None, None, shares)
    value = cents(shares * last[1])
    if value > 0:
        flows.append((today, value))
    return Simulation(value, xirr(flows), last[0], shares)
