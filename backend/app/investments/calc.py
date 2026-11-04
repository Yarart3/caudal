"""Cálculos de la cartera sin base de datos (Fase 3, parte 3.4a): FIFO, TIR, rentabilidad por año,
peor caída y aportaciones. Todo recibe listas ya leídas, así se prueba con casos hechos a mano.

Convenios (los mismos que la tabla `investment_operations`):
- Compra: `amount` es lo que salió de la cuenta, comisiones incluidas (es el coste del lote).
- Venta: `amount` es lo que entró, ya descontadas las comisiones.
- Dividendo: dinero que entra. Comisión suelta (`fee`): dinero que sale.
- El mismo día, las compras van antes que las ventas (no se sabe la hora).
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal(0)


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Op:
    date: date
    kind: str  # buy | sell | dividend | fee
    shares: Decimal
    amount: Decimal
    id: int = 0


def chronological(ops: Iterable[Op]) -> list[Op]:
    """Por fecha; el mismo día, compras primero y después el resto, por orden de alta."""
    return sorted(ops, key=lambda o: (o.date, 0 if o.kind == "buy" else 1, o.id))


# ---------------------------------------------------------------- FIFO


@dataclass
class Lot:
    """Lo que queda de una compra: participaciones y su coste (proporcional)."""

    date: date
    shares: Decimal
    cost: Decimal


@dataclass(frozen=True)
class Sale:
    date: date
    shares: Decimal
    cost: Decimal  # coste FIFO de lo vendido
    proceeds: Decimal

    @property
    def gain(self) -> Decimal:
        return self.proceeds - self.cost


@dataclass
class Fifo:
    lots: list[Lot] = field(default_factory=list)
    sales: list[Sale] = field(default_factory=list)
    dividends: Decimal = ZERO
    fees: Decimal = ZERO  # comisiones sueltas (las de compra y venta ya van en el importe)

    @property
    def shares(self) -> Decimal:
        return sum((lot.shares for lot in self.lots), ZERO)

    @property
    def cost(self) -> Decimal:
        """Coste de lo que se tiene (lo que se pagó por las participaciones que quedan)."""
        return sum((lot.cost for lot in self.lots), ZERO)

    @property
    def average_price(self) -> Decimal | None:
        return self.cost / self.shares if self.shares > 0 else None

    @property
    def realized(self) -> Decimal:
        return sum((s.gain for s in self.sales), ZERO)


class OversoldError(ValueError):
    """Se vende más de lo que se tiene. La API ya lo impide; aquí es una red de seguridad."""


def fifo(ops: Iterable[Op]) -> Fifo:
    """Lotes que quedan y ventas con su coste. Se venden primero las participaciones más antiguas.

    El coste de un lote vendido a medias se reparte en proporción a las participaciones y se
    redondea al céntimo; lo que queda del lote se calcula por resta, así la suma siempre cuadra.
    """
    result = Fifo()
    for op in chronological(ops):
        if op.kind == "buy":
            result.lots.append(Lot(op.date, op.shares, op.amount))
        elif op.kind == "sell":
            result.sales.append(_sell(result.lots, op))
        elif op.kind == "dividend":
            result.dividends += op.amount
        elif op.kind == "fee":
            result.fees += op.amount
        else:
            raise ValueError(f"Tipo de operación desconocido: {op.kind}")
    return result


def _sell(lots: list[Lot], op: Op) -> Sale:
    pending = op.shares
    cost = ZERO
    while pending > 0:
        if not lots:
            raise OversoldError(f"El {op.date} se venden más participaciones de las que hay")
        lot = lots[0]
        if lot.shares <= pending:
            pending -= lot.shares
            cost += lot.cost
            lots.pop(0)
        else:
            part = cents(lot.cost * pending / lot.shares)
            lot.shares -= pending
            lot.cost -= part
            cost += part
            pending = ZERO
    return Sale(op.date, op.shares, cost, op.amount)


# ---------------------------------------------------------------- TIR (XIRR)


def cash_flows(ops: Iterable[Op]) -> list[tuple[date, Decimal]]:
    """Flujos vistos por el inversor: lo que sale, negativo; lo que entra, positivo."""
    sign = {"buy": -1, "fee": -1, "sell": 1, "dividend": 1}
    return [(o.date, o.amount * sign[o.kind]) for o in ops]


def xirr(flows: Sequence[tuple[date, Decimal]]) -> Decimal | None:
    """TIR anual con fechas, como `XIRR` de Excel: Σ v / (1 + r) ^ (días / 365) = 0.

    Newton desde el 10 % y, si no converge, bisección entre -99,99 % y +100.000 %.
    Devuelve `None` si no hay al menos un flujo negativo y uno positivo (no tiene solución).
    El resultado va con 8 decimales (0.07123456 = 7,12 %).
    """
    flows = [(d, float(v)) for d, v in flows if v != 0]
    if not any(v < 0 for _, v in flows) or not any(v > 0 for _, v in flows):
        return None
    start = min(d for d, _ in flows)
    points = [((d - start).days / 365.0, v) for d, v in flows]

    def npv(rate: float) -> float:
        return sum(v / (1.0 + rate) ** t for t, v in points)

    def d_npv(rate: float) -> float:
        return sum(-t * v / (1.0 + rate) ** (t + 1.0) for t, v in points)

    rate = _newton(npv, d_npv, 0.1)
    if rate is None:
        rate = _bisect(npv, -0.9999, 1000.0)
    return None if rate is None else Decimal(repr(round(rate, 8)))


def _newton(f, df, guess: float) -> float | None:
    rate = guess
    for _ in range(100):
        try:
            value, slope = f(rate), df(rate)
        except (OverflowError, ZeroDivisionError):
            return None
        if slope == 0 or not math.isfinite(value) or not math.isfinite(slope):
            return None
        step = value / slope
        rate -= step
        if rate <= -1.0:
            return None
        if abs(step) < 1e-12:
            return rate if abs(f(rate)) < 1e-6 else None
    return None


def _bisect(f, low: float, high: float) -> float | None:
    try:
        f_low, f_high = f(low), f(high)
    except (OverflowError, ZeroDivisionError):
        return None
    if f_low * f_high > 0:
        return None
    for _ in range(300):
        mid = (low + high) / 2.0
        f_mid = f(mid)
        if abs(f_mid) < 1e-9 or (high - low) < 1e-12:
            return mid
        if f_low * f_mid < 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


# ---------------------------------------------------------------- rentabilidad por año y caída


@dataclass(frozen=True)
class DayValue:
    """Valor de la cartera al cierre de `date` y dinero que entró en ella ese día.

    `flow` = compras + comisiones sueltas − ventas − dividendos: un dividendo es dinero que sale
    de la cartera como ganancia, y una comisión suelta es dinero que entra sin aumentar el valor.
    """

    date: date
    value: Decimal
    flow: Decimal = ZERO


def year_returns(series: Sequence[DayValue]) -> dict[int, Decimal]:
    """Rentabilidad de cada año natural por el método Dietz modificado (no anualizada).

    R = (V_fin − V_inicio − F) / (V_inicio + Σ F_i · w_i), con w_i la parte del año que el
    dinero estuvo dentro. Así una aportación grande en diciembre no cuenta como ganancia.
    El año en curso va hasta el último día de la serie. Un año sin capital invertido no sale.
    """
    result: dict[int, Decimal] = {}
    if not series:
        return result
    ordered = sorted(series, key=lambda d: d.date)
    by_year: dict[int, list[DayValue]] = {}
    for day in ordered:
        by_year.setdefault(day.date.year, []).append(day)
    previous_end = ZERO
    for year in sorted(by_year):
        days = by_year[year]
        period_start = date(year, 1, 1) if previous_end > 0 else days[0].date
        # El primer día de la cartera, el valor de partida es 0 y la compra es el flujo
        end = days[-1]
        length = (end.date - period_start).days + 1
        net = sum((d.flow for d in days), ZERO)
        weighted = sum(
            (d.flow * Decimal((end.date - d.date).days + 1) / Decimal(length) for d in days),
            ZERO,
        )
        base = previous_end + weighted
        if base > 0:
            result[year] = (end.value - previous_end - net) / base
        previous_end = end.value
    return result


def max_drawdown(series: Sequence[DayValue]) -> Decimal | None:
    """Peor caída desde un máximo, sobre la rentabilidad diaria encadenada (no sobre el valor).

    Sobre el valor, comprar más taparía las caídas. Cada día: r = (V_hoy − F_hoy) / V_ayer − 1.
    Devuelve un número ≤ 0 (−0.25 = −25 %) o `None` si no hay al menos dos días con valor.
    """
    ordered = sorted(series, key=lambda d: d.date)
    index = Decimal(1)
    peak = Decimal(1)
    worst = ZERO
    previous: Decimal | None = None
    days = 0
    for day in ordered:
        if previous is not None and previous > 0:
            index *= (day.value - day.flow) / previous
            peak = max(peak, index)
            worst = min(worst, index / peak - 1)
            days += 1
        previous = day.value
    return worst if days > 0 else None


# ---------------------------------------------------------------- aportaciones


def monthly_contributions(ops: Iterable[Op]) -> dict[tuple[int, int], Decimal]:
    """Aportación neta de cada mes (año, mes): compras − ventas (sin dividendos ni comisiones)."""
    result: dict[tuple[int, int], Decimal] = {}
    for op in ops:
        if op.kind in ("buy", "sell"):
            key = (op.date.year, op.date.month)
            result[key] = result.get(key, ZERO) + (op.amount if op.kind == "buy" else -op.amount)
    return result


def contribution_streak(months: dict[tuple[int, int], Decimal], today: date) -> int:
    """Meses seguidos aportando (aportación neta > 0) hasta hoy.

    Si este mes aún no hay aportación, la racha se cuenta desde el mes pasado: no se rompe
    a mitad de mes.
    """
    year, month = today.year, today.month
    if months.get((year, month), ZERO) <= 0:
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    streak = 0
    while months.get((year, month), ZERO) > 0:
        streak += 1
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return streak


def annual_ter_cost(positions: Iterable[tuple[Decimal, Decimal | None]]) -> Decimal:
    """Comisiones anuales de los fondos: Σ valor × TER. `ter` en tanto por uno (0.0007 = 0,07 %)."""
    return cents(sum((value * ter for value, ter in positions if ter), ZERO))
