"""Cartera de un usuario a partir de la base de datos (Fase 3, parte 3.4b).

Lee de una vez sus operaciones, precios, tipos de cambio y valores anotados a mano, y aplica los
cálculos de `calc.py`:

- Posiciones por **producto** (sumando sus cuentas): FIFO, coste, precio medio, valor y plusvalía.
- Valor de la cartera **día a día** desde la primera operación (para la rentabilidad por año y
  la peor caída). Un día sin precio se usa el último anterior; antes del primer precio, lo que
  costó (el refresco ya descarga el histórico desde la primera operación).
- Indicadores: valor, plusvalía latente y realizada, dividendos, TIR, aportaciones y TER.

Los productos con precio manual (`price_source = manual`) valen lo último anotado en
`manual_valuations` (la posición entera, no por participación).
"""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.investments.calc import (
    ZERO,
    DayValue,
    Fifo,
    Op,
    annual_ter_cost,
    apply,
    cash_flows,
    cents,
    chronological,
    contribution_streak,
    max_drawdown,
    monthly_contributions,
    xirr,
    year_returns,
)
from app.models import (
    Account,
    ExchangeRate,
    InvestmentOperation,
    ManualValuation,
    Price,
    Product,
)


@dataclass(frozen=True)
class PriceRow:
    date: date
    price: Decimal
    currency: str
    fetched_at: datetime


class DateSeries:
    """Valores por fecha con búsqueda del último en o antes de un día."""

    def __init__(self, rows: list[tuple[date, object]]) -> None:
        rows.sort(key=lambda r: r[0])
        self.dates = [d for d, _ in rows]
        self.values = [v for _, v in rows]

    def last(self, day: date) -> tuple[date, object] | None:
        """(fecha, valor) del día o del último anterior; None si no hay ninguno."""
        i = bisect_right(self.dates, day)
        return (self.dates[i - 1], self.values[i - 1]) if i else None

    def at(self, day: date):
        found = self.last(day)
        return None if found is None else found[1]


class Market:
    """Precios, tipos de cambio y valores manuales ya cargados en memoria."""

    def __init__(self, db: Session, products: list[Product]) -> None:
        ids = [p.id for p in products]
        prices: dict[int, list] = defaultdict(list)
        if ids:
            for row in db.execute(
                select(
                    Price.product_id, Price.date, Price.price, Price.currency, Price.fetched_at
                ).where(Price.product_id.in_(ids))
            ):
                prices[row.product_id].append(
                    (row.date, PriceRow(row.date, row.price, row.currency, row.fetched_at))
                )
        self.prices = {pid: DateSeries(rows) for pid, rows in prices.items()}

        currencies = {row.currency for rows in prices.values() for _, row in rows} - {"EUR"}
        rates: dict[str, list] = defaultdict(list)
        if currencies:
            for row in db.execute(
                select(ExchangeRate.currency, ExchangeRate.date, ExchangeRate.rate).where(
                    ExchangeRate.currency.in_(currencies)
                )
            ):
                rates[row.currency].append((row.date, row.rate))
        self.rates = {cur: DateSeries(rows) for cur, rows in rates.items()}

        manual_ids = [p.id for p in products if p.price_source == "manual"]
        manual: dict[int, list] = defaultdict(list)
        if manual_ids:
            for row in db.execute(
                select(
                    ManualValuation.product_id, ManualValuation.date, ManualValuation.value_eur
                ).where(ManualValuation.product_id.in_(manual_ids))
            ):
                manual[row.product_id].append((row.date, row.value_eur))
        self.manual = {pid: DateSeries(rows) for pid, rows in manual.items()}

    def last_price(self, product_id: int, day: date) -> PriceRow | None:
        series = self.prices.get(product_id)
        return series.at(day) if series else None

    def to_eur(self, amount: Decimal, currency: str, day: date) -> Decimal | None:
        if currency == "EUR":
            return amount
        series = self.rates.get(currency)
        rate = series.at(day) if series else None
        return None if rate is None else amount * rate

    def value(self, product: Product, book: Fifo, day: date) -> Decimal | None:
        """Valor en euros de lo que se tiene de `product` al cierre de `day` (None: sin precio)."""
        if book.shares <= 0:
            return ZERO
        if product.price_source == "manual":
            series = self.manual.get(product.id)
            return series.at(day) if series else None
        row = self.last_price(product.id, day)
        if row is None:
            return None
        price_eur = self.to_eur(row.price, row.currency, day)
        return None if price_eur is None else book.shares * price_eur


@dataclass
class Position:
    product: Product
    accounts: list[str]  # cuentas donde quedan participaciones, por nombre
    book: Fifo
    price: PriceRow | None  # último precio (None en los manuales o si no hay ninguno)
    price_eur: Decimal | None
    value: Decimal | None  # None: no se sabe (falta precio o tipo de cambio)

    @property
    def gain(self) -> Decimal | None:
        return None if self.value is None else self.value - self.book.cost


@dataclass
class Portfolio:
    today: date
    ops: list[Op] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    books: dict[int, Fifo] = field(default_factory=dict)
    series: list[DayValue] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # productos sin precio hoy

    @property
    def value(self) -> Decimal:
        return sum((p.value for p in self.positions if p.value is not None), ZERO)

    @property
    def cost(self) -> Decimal:
        return sum((p.book.cost for p in self.positions if p.value is not None), ZERO)


def _day_flow(op: Op) -> Decimal:
    """Dinero que entra en la cartera ese día (convenio de `DayValue`)."""
    return op.amount if op.kind in ("buy", "fee") else -op.amount


def build(db: Session, user_id: int, today: date) -> Portfolio:
    products = db.scalars(select(Product).where(Product.user_id == user_id)).all()
    by_id = {p.id: p for p in products}
    rows = db.execute(
        select(InvestmentOperation, Account.name)
        .join(Account, Account.id == InvestmentOperation.account_id)
        .where(Account.user_id == user_id, InvestmentOperation.product_id.in_(by_id or [0]))
    ).all()

    portfolio = Portfolio(today=today)
    product_of: dict[int, int] = {}  # id de la operación → producto
    # (producto, nombre de la cuenta) → participaciones que quedan ahí
    held: dict[tuple[int, str], Decimal] = defaultdict(Decimal)
    for operation, account_name in rows:
        op = Op(
            operation.date, operation.kind, operation.shares, operation.amount_eur, operation.id
        )
        portfolio.ops.append(op)
        product_of[operation.id] = operation.product_id
        if operation.kind == "buy":
            held[(operation.product_id, account_name)] += operation.shares
        elif operation.kind == "sell":
            held[(operation.product_id, account_name)] -= operation.shares
    if not portfolio.ops:
        return portfolio

    market = Market(db, list(products))
    ops = chronological(portfolio.ops)
    books: dict[int, Fifo] = defaultdict(Fifo)
    by_day: dict[date, list[Op]] = defaultdict(list)
    for op in ops:
        by_day[op.date].append(op)

    day = ops[0].date
    while day <= today:
        flow = ZERO
        for op in by_day.get(day, ()):
            apply(books[product_of[op.id]], op)
            flow += _day_flow(op)
        value = ZERO
        for pid, book in books.items():
            known = market.value(by_id[pid], book, day)
            value += book.cost if known is None else known
        portfolio.series.append(DayValue(day, cents(value), flow))
        day += timedelta(days=1)

    portfolio.books = dict(books)
    for pid, book in books.items():
        product = by_id[pid]
        if book.shares <= 0:
            continue
        value = market.value(product, book, today)
        price = None if product.price_source == "manual" else market.last_price(pid, today)
        price_eur = None if price is None else market.to_eur(price.price, price.currency, today)
        if value is None:
            portfolio.missing.append(product.name)
        accounts = sorted(name for (p, name), shares in held.items() if p == pid and shares > 0)
        portfolio.positions.append(
            Position(
                product=product,
                accounts=accounts,
                book=book,
                price=price,
                price_eur=price_eur,
                value=None if value is None else cents(value),
            )
        )
    portfolio.positions.sort(key=lambda p: (-(p.value or ZERO), p.product.name.lower()))
    return portfolio


def last_months(today: date, count: int = 12) -> list[tuple[int, int]]:
    """Los `count` últimos meses (año, mes), del más antiguo al actual."""
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        months.append((year, month))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return months[::-1]


@dataclass(frozen=True)
class Summary:
    value: Decimal
    cost: Decimal
    gain: Decimal
    gain_pct: Decimal | None
    realized: Decimal
    dividends: Decimal
    dividends_12m: Decimal
    fees: Decimal
    xirr: Decimal | None
    contributed_12m: Decimal
    contributions: list[tuple[str, Decimal]]  # ("2026-10", importe) de los últimos 12 meses
    streak: int
    ter_annual: Decimal
    year_returns: list[tuple[int, Decimal]]
    max_drawdown: Decimal | None
    missing: list[str]


def summarize(portfolio: Portfolio) -> Summary:
    today = portfolio.today
    books = portfolio.books.values()
    value, cost = portfolio.value, portfolio.cost
    months = monthly_contributions(portfolio.ops)
    window = last_months(today)
    first_month = window[0]
    in_window = [o for o in portfolio.ops if (o.date.year, o.date.month) >= first_month]

    # La TIR usa el valor de hoy de la serie: si a algún producto le falta el precio, cuenta
    # lo que costó (mejor una TIR aproximada que ninguna; la pantalla avisa con `missing`).
    final = portfolio.series[-1].value if portfolio.series else ZERO
    flows = cash_flows(portfolio.ops)
    if final > 0:
        flows.append((today, final))

    return Summary(
        value=cents(value),
        cost=cents(cost),
        gain=cents(value - cost),
        gain_pct=(value - cost) / cost if cost > 0 else None,
        realized=cents(sum((b.realized for b in books), ZERO)),
        dividends=cents(sum((b.dividends for b in books), ZERO)),
        dividends_12m=cents(sum((o.amount for o in in_window if o.kind == "dividend"), ZERO)),
        fees=cents(sum((b.fees for b in books), ZERO)),
        xirr=xirr(flows),
        contributed_12m=cents(sum((months.get(m, ZERO) for m in window), ZERO)),
        contributions=[(f"{y}-{m:02d}", cents(months.get((y, m), ZERO))) for y, m in window],
        streak=contribution_streak(months, today),
        ter_annual=annual_ter_cost(
            (p.value, p.product.ter) for p in portfolio.positions if p.value is not None
        ),
        year_returns=sorted(year_returns(portfolio.series).items()),
        max_drawdown=max_drawdown(portfolio.series),
        missing=sorted(portfolio.missing, key=str.lower),
    )


# ---------------------------------------------------------------- Patrimonio (parte 3.6)


@dataclass(frozen=True)
class Holdings:
    """Lo invertido a una fecha: valor total, lo que costó y el reparto por cuenta y por tipo."""

    value: Decimal
    cost: Decimal
    by_account: dict[int, Decimal]  # id de la cuenta → valor
    by_kind: dict[str, Decimal]  # tipo de producto (etf, crypto…) → valor


class InvestmentHistory:
    """Operaciones y precios de un usuario, cargados una vez para valorar a varias fechas.

    Mismas reglas que la serie diaria de `build`: el último precio del día o anterior y, si no
    hay, lo que costó. Un producto en dos cuentas reparte su valor según las participaciones
    que hay en cada una (el FIFO es por producto).
    """

    def __init__(self, db: Session, user_id: int) -> None:
        products = db.scalars(select(Product).where(Product.user_id == user_id)).all()
        self.products = {p.id: p for p in products}
        operations = db.scalars(
            select(InvestmentOperation)
            .join(Account, Account.id == InvestmentOperation.account_id)
            .where(
                Account.user_id == user_id,
                InvestmentOperation.product_id.in_(self.products or [0]),
            )
        ).all()
        self.where: dict[int, tuple[int, int]] = {}  # operación → (producto, cuenta)
        ops = []
        for o in operations:
            ops.append(Op(o.date, o.kind, o.shares, o.amount_eur, o.id))
            self.where[o.id] = (o.product_id, o.account_id)
        self.ops = chronological(ops)
        self.market = Market(db, list(products)) if ops else None

    def at(self, day: date) -> Holdings:
        books: dict[int, Fifo] = defaultdict(Fifo)
        held: dict[int, dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for op in self.ops:
            if op.date > day:
                break
            product_id, account_id = self.where[op.id]
            apply(books[product_id], op)
            if op.kind == "buy":
                held[product_id][account_id] += op.shares
            elif op.kind == "sell":
                held[product_id][account_id] -= op.shares

        value = cost = ZERO
        by_account: dict[int, Decimal] = defaultdict(Decimal)
        by_kind: dict[str, Decimal] = defaultdict(Decimal)
        for product_id, book in books.items():
            if book.shares <= 0 or self.market is None:
                continue
            product = self.products[product_id]
            known = self.market.value(product, book, day)
            worth = book.cost if known is None else known
            value += worth
            cost += book.cost
            by_kind[product.kind] += worth
            for account_id, shares in held[product_id].items():
                if shares > 0:
                    by_account[account_id] += worth * shares / book.shares
        return Holdings(
            value=cents(value),
            cost=cents(cost),
            by_account={k: cents(v) for k, v in by_account.items()},
            by_kind={k: cents(v) for k, v in sorted(by_kind.items()) if v > 0},
        )
