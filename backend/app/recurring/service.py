"""Detección de pagos recurrentes (DISENO 9.5). No se guarda nada: se calcula al pedirlo.

1. Se toman los **gastos** del usuario (importe < 0, sin transferencias internas) de los
   últimos LOOKBACK_DAYS días hasta el final del mes elegido. Lo posterior no cuenta: así un
   mes pasado enseña los recurrentes que había entonces.
2. Se descartan los conceptos que encajan con una **regla sin categoría** (los Bizum): sus
   conceptos no siempre dicen a quién se paga y se agruparían todos juntos.
3. Se agrupan por **concepto normalizado**: mayúsculas, sin acentos y sin las palabras que
   llevan números (fechas, referencias de tarjeta…), igual que «¿Aplicar siempre?».
4. En cada grupo se quedan los importes a ±10 % de la mediana (un pago suelto distinto en el
   mismo comercio no estorba) y, en un mismo día, una sola vez.
5. Desde el más reciente hacia atrás, se busca una cadena de pagos seguidos con la separación
   de una periodicidad, sin huecos ni pagos de más en medio:
   - **mensual:** 25 a 35 días entre pagos y al menos 3 pagos;
   - **anual:** 350 a 380 días entre pagos y al menos 2 pagos.
   Exigir que no haya pagos de más en medio evita confundir la compra semanal del súper
   (a veces del mismo importe) con una suscripción.
6. Solo se enseña si sigue **activo**: el último pago es de hace como mucho 62 días (mensual:
   este mes o el anterior, aunque el mes elegido todavía no esté importado) o 400 días
   (anual), contando desde el final del mes elegido.

El importe es el del último pago (si una suscripción sube de precio, se ve el precio nuevo) y el
total al mes suma los mensuales y los anuales divididos entre 12.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categories.rules import find_rule, load_rules
from app.dashboard.months import add_months, month_end, month_key
from app.importers.base import normalize_text
from app.models import Account, Category, Transaction

Frequency = Literal["monthly", "annual"]

ZERO = Decimal("0.00")
CENTS = Decimal("0.01")
AMOUNT_TOLERANCE = Decimal("0.10")
LOOKBACK_DAYS = 760  # dos pagos anuales + margen
UNCATEGORIZED = ("Sin categoría", "#8A9099")


@dataclass(frozen=True)
class _Pattern:
    frequency: Frequency
    min_gap: int
    max_gap: int
    min_count: int
    active_days: int
    months: int  # meses hasta el siguiente pago


PATTERNS = (
    _Pattern("monthly", 25, 35, 3, 62, 1),
    _Pattern("annual", 350, 380, 2, 400, 12),
)


@dataclass
class RecurringPayment:
    key: str  # concepto normalizado (el que agrupa)
    description: str  # concepto del último pago, tal cual
    frequency: Frequency
    amount: Decimal  # último pago, en positivo
    monthly_amount: Decimal  # mensual = amount; anual = amount / 12
    occurrences: int  # pagos de la cadena
    first_date: date
    last_date: date
    next_date: date  # cuándo debería llegar el siguiente
    detected_on: date  # el pago con el que pasó a contar como recurrente
    is_new: bool  # detected_on cae en el mes elegido (aviso «nuevo recurrente»)
    category_id: int | None
    category_name: str
    category_color: str
    account_name: str


@dataclass
class RecurringSummary:
    month: str
    monthly_total: Decimal
    items: list[RecurringPayment]


@dataclass(frozen=True)
class _Payment:
    date: date
    amount: Decimal  # en positivo
    description: str
    category_id: int | None
    account_name: str


def group_key(description: str) -> str:
    """Concepto normalizado sin las palabras con números. Si todas llevan números, se queda
    entero (igual que suggestPattern en el frontend)."""
    words = normalize_text(description).split()
    without_numbers = [w for w in words if not any(c.isdigit() for c in w)]
    return " ".join(without_numbers or words)


def _same_day(day: date, months: int) -> date:
    """El mismo día `months` meses después; si ese mes es más corto, su último día."""
    first = add_months(day.replace(day=1), months)
    return min(first.replace(day=1) + timedelta(days=day.day - 1), month_end(first))


def _cluster(payments: list[_Payment]) -> list[_Payment]:
    """Los pagos a ±10 % de la mediana, uno por día (el último del día), por fecha."""
    middle = median(p.amount for p in payments)
    close = [p for p in payments if abs(p.amount - middle) <= middle * AMOUNT_TOLERANCE]
    by_day = {p.date: p for p in sorted(close, key=lambda p: p.date)}
    return [by_day[day] for day in sorted(by_day)]


def _chain(payments: list[_Payment], pattern: _Pattern) -> list[_Payment]:
    """La cadena más reciente de pagos seguidos con la separación del patrón."""
    chain = [payments[-1]]
    for payment in reversed(payments[:-1]):
        gap = (chain[0].date - payment.date).days
        if not pattern.min_gap <= gap <= pattern.max_gap:
            break
        chain.insert(0, payment)
    return chain


def _detect(
    key: str, payments: list[_Payment], end: date, first_day: date, categories: dict
) -> RecurringPayment | None:
    cluster = _cluster(payments)
    for pattern in PATTERNS:
        chain = _chain(cluster, pattern)
        if len(chain) < pattern.min_count:
            continue
        last = chain[-1]
        if (end - last.date).days > pattern.active_days:
            return None  # se ha dejado de pagar
        detected_on = chain[pattern.min_count - 1].date
        name, color = categories.get(last.category_id, UNCATEGORIZED)
        monthly = last.amount if pattern.months == 1 else last.amount / pattern.months
        return RecurringPayment(
            key=key,
            description=last.description,
            frequency=pattern.frequency,
            amount=last.amount,
            monthly_amount=monthly.quantize(CENTS),
            occurrences=len(chain),
            first_date=chain[0].date,
            last_date=last.date,
            next_date=_same_day(last.date, pattern.months),
            detected_on=detected_on,
            is_new=first_day <= detected_on <= end,
            category_id=last.category_id,
            category_name=name,
            category_color=color,
            account_name=last.account_name,
        )
    return None


def detect_recurring(db: Session, user_id: int, first_day: date) -> RecurringSummary:
    """Pagos recurrentes activos al final del mes elegido, del más caro al más barato (al mes)."""
    end = month_end(first_day)
    rows = db.execute(
        select(
            Transaction.date,
            Transaction.amount,
            Transaction.description,
            Transaction.category_id,
            Account.name,
        )
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.is_internal_transfer.is_(False),
            Transaction.amount < 0,
            Transaction.date > end - timedelta(days=LOOKBACK_DAYS),
            Transaction.date <= end,
        )
        .order_by(Transaction.date, Transaction.id)
    ).all()

    rules = load_rules(db, user_id)
    groups: dict[str, list[_Payment]] = defaultdict(list)
    for day, amount, description, category_id, account_name in rows:
        rule = find_rule(description, rules)
        if rule is not None and rule.category_id is None:
            continue  # Bizum y demás conceptos que se dejan por revisar
        key = group_key(description)
        if key:
            payment = _Payment(day, -amount, description, category_id, account_name)
            groups[key].append(payment)

    categories = {
        cat_id: (name, color or UNCATEGORIZED[1])
        for cat_id, name, color in db.execute(
            select(Category.id, Category.name, Category.color).where(Category.user_id == user_id)
        )
    }
    items = [
        found
        for key, payments in groups.items()
        if (found := _detect(key, payments, end, first_day, categories)) is not None
    ]
    items.sort(key=lambda r: (-r.monthly_amount, r.key))
    return RecurringSummary(
        month=month_key(first_day),
        monthly_total=sum((r.monthly_amount for r in items), ZERO),
        items=items,
    )
