"""Cartera del usuario de la sesión (Fase 3, parte 3.4b; la pantalla llega en la 3.5).

- GET /api/investments/summary    indicadores: valor, plusvalías, TIR, aportaciones, TER…
- GET /api/investments/positions  «Mis posiciones»: una fila por producto que aún se tiene
- GET /api/investments/benchmark  «¿Y si todo fuera a un indexado?» (parte 3.4c)

Las cifras salen como texto (`"1234.56"`); los porcentajes, en tanto por uno con 6 decimales
(`"0.071234"` = 7,12 %). Cada usuario ve solo lo suyo.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, PlainSerializer
from sqlalchemy.orm import Session

from app.api.prices import prices_settings
from app.auth.deps import current_user
from app.config import Settings
from app.db import get_db
from app.investments.benchmark import BENCHMARKS, BenchmarkPrices, simulate
from app.investments.calc import cents
from app.investments.operations import TZ
from app.investments.portfolio import build, summarize
from app.models import User

router = APIRouter(prefix="/api/investments", tags=["investments"])

# Decimal como texto y sin notación científica (Decimal("0E-8") saldría "0E-8")
Num = Annotated[Decimal, PlainSerializer(lambda v: format(v, "f"), return_type=str)]
RATE = Decimal("0.000001")


def _rate(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATE)


def _price(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(RATE)


class MonthOut(BaseModel):
    month: str  # "2026-10"
    amount: Num


class YearReturnOut(BaseModel):
    year: int
    return_pct: Num


class SummaryOut(BaseModel):
    has_investments: bool
    as_of: date
    value: Num
    cost: Num
    gain: Num
    gain_pct: Num | None
    realized: Num
    dividends: Num
    dividends_12m: Num
    fees: Num
    xirr: Num | None
    contributed_12m: Num
    contributions: list[MonthOut]
    streak: int
    ter_annual: Num
    year_returns: list[YearReturnOut]
    max_drawdown: Num | None
    missing_prices: list[str]


class PositionOut(BaseModel):
    product_id: int
    name: str
    isin: str | None
    symbol: str | None
    kind: str
    accounts: list[str]
    shares: Num
    average_price: Num | None
    cost: Num
    price: Num | None
    price_currency: str | None
    price_eur: Num | None
    price_date: date | None
    fetched_at: datetime | None
    stale: bool
    value: Num | None
    gain: Num | None
    gain_pct: Num | None
    weight: Num | None
    ter: Num | None


class PositionsOut(BaseModel):
    total_value: Num
    items: list[PositionOut]


@router.get("/summary")
def get_summary(user: User = Depends(current_user), db: Session = Depends(get_db)) -> SummaryOut:
    today = datetime.now(TZ).date()
    portfolio = build(db, user.id, today)
    s = summarize(portfolio)
    return SummaryOut(
        has_investments=bool(portfolio.ops),
        as_of=today,
        value=s.value,
        cost=s.cost,
        gain=s.gain,
        gain_pct=_rate(s.gain_pct),
        realized=s.realized,
        dividends=s.dividends,
        dividends_12m=s.dividends_12m,
        fees=s.fees,
        xirr=_rate(s.xirr),
        contributed_12m=s.contributed_12m,
        contributions=[MonthOut(month=m, amount=a) for m, a in s.contributions],
        streak=s.streak,
        ter_annual=s.ter_annual,
        year_returns=[YearReturnOut(year=y, return_pct=_rate(r)) for y, r in s.year_returns],
        max_drawdown=_rate(s.max_drawdown),
        missing_prices=s.missing,
    )


@router.get("/positions")
def get_positions(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(prices_settings),
) -> PositionsOut:
    now = datetime.now(TZ)
    max_age = timedelta(hours=settings.price_max_age_hours)
    portfolio = build(db, user.id, now.date())
    total = cents(portfolio.value)
    items = []
    for p in portfolio.positions:
        book, product, price = p.book, p.product, p.price
        manual = product.price_source == "manual"
        items.append(
            PositionOut(
                product_id=product.id,
                name=product.name,
                isin=product.isin,
                symbol=product.source_id,
                kind=product.kind,
                accounts=p.accounts,
                shares=book.shares,
                average_price=_price(book.average_price),
                cost=book.cost,
                price=None if price is None else price.price,
                price_currency=None if price is None else price.currency,
                price_eur=_price(p.price_eur),
                price_date=None if price is None else price.date,
                fetched_at=None if price is None else price.fetched_at,
                # Un manual no se descarga: nunca está «desactualizado»
                stale=not manual and (price is None or now - price.fetched_at > max_age),
                value=p.value,
                gain=p.gain,
                gain_pct=(
                    _rate(p.gain / book.cost) if p.gain is not None and book.cost > 0 else None
                ),
                weight=(_rate(p.value / total) if p.value is not None and total > 0 else None),
                ter=product.ter,
            )
        )
    return PositionsOut(total_value=total, items=items)


class BenchmarkItemOut(BaseModel):
    key: str
    name: str
    symbol: str
    available: bool  # False: faltan cierres del índice para alguna fecha (no se compara)
    value: Num | None
    diff: Num | None  # valor del índice − valor real (positivo: el índice habría ido mejor)
    xirr: Num | None
    price_date: date | None


class BenchmarkOut(BaseModel):
    has_investments: bool
    value: Num  # lo que vale hoy la cartera de verdad
    xirr: Num | None
    items: list[BenchmarkItemOut]


@router.get("/benchmark")
def get_benchmark(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> BenchmarkOut:
    today = datetime.now(TZ).date()
    portfolio = build(db, user.id, today)
    mine = summarize(portfolio)
    items = []
    for bench in BENCHMARKS:
        sim = simulate(portfolio.ops, BenchmarkPrices(db, bench.symbol), today)
        items.append(
            BenchmarkItemOut(
                key=bench.key,
                name=bench.name,
                symbol=bench.symbol,
                available=sim.value is not None,
                value=sim.value,
                diff=None if sim.value is None else sim.value - mine.value,
                xirr=_rate(sim.xirr),
                price_date=sim.price_date,
            )
        )
    return BenchmarkOut(
        has_investments=bool(portfolio.ops),
        value=mine.value,
        xirr=_rate(mine.xirr),
        items=items,
    )
