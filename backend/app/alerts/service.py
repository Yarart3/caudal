"""Avisos del mes. No se guardan: se calculan al pedirlos (por eso no se pueden descartar).

Tipos, en este orden:
1. **budget_over** (danger): una categoría ha superado su presupuesto.
2. **spending_high** (warning): una categoría gasta más de SPENDING_RATIO veces su media de los
   3 meses anteriores y la diferencia es de al menos SPENDING_MIN_DIFF €. La media se hace con
   los meses anteriores que tienen algún movimiento: así el primer mes importado no salta con
   todo, y un mes sin datos no baja la media. No se repite si la categoría ya ha superado el
   presupuesto.
3. **expense_change** (warning si sube, positive si baja): gastos del mes frente al anterior,
   como la maqueta. Solo si el mes anterior tiene gastos.
4. **recurring_new** (info): un pago ha pasado a ser recurrente este mes.
5. **recurring_total** (info): cuántos pagos recurrentes hay y cuánto suman al mes.

Los umbrales van aquí y no en el .env: no dependen del equipo en el que se ejecute.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.budgets.service import monthly_budgets, spent_by_category
from app.dashboard.months import add_months, month_key
from app.dashboard.service import cashflow
from app.models import Account, Category, Transaction
from app.recurring import detect_recurring

AlertKind = Literal[
    "budget_over", "spending_high", "expense_change", "recurring_new", "recurring_total"
]
AlertLevel = Literal["danger", "warning", "positive", "info"]

SPENDING_RATIO = Decimal("1.5")
SPENDING_MIN_DIFF = Decimal("30.00")
AVERAGE_MONTHS = 3
ZERO = Decimal("0.00")
CENTS = Decimal("0.01")
MONTH_NAMES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


@dataclass
class Alert:
    kind: AlertKind
    level: AlertLevel
    title: str  # etiqueta corta («Presupuesto», «Gasto alto»…)
    message: str  # frase en castellano, con los importes ya formateados
    category_id: int | None = None
    amount: Decimal | None = None  # la cifra principal del aviso (para ordenar o enlazar)


@dataclass
class AlertSummary:
    month: str
    items: list[Alert]


def eur(value: Decimal) -> str:
    """1234.5 → «1.234,50 €» (con punto de miles también en 4 cifras, como el frontend)."""
    text = f"{abs(value.quantize(CENTS)):,.2f}".replace(",", " ").replace(".", ",")
    return ("−" if value < 0 else "") + text.replace(" ", ".") + " €"


def _months_with_data(db: Session, user_id: int, first: date, before: date) -> list[date]:
    """Primer día de los meses entre `first` y `before` (sin incluirlo) con algún movimiento."""
    month = func.date_trunc("month", Transaction.date)
    rows = db.scalars(
        select(month)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.is_internal_transfer.is_(False),
            Transaction.date >= first,
            Transaction.date < before,
        )
        .group_by(month)
    )
    return sorted(row.date() for row in rows)


def _budget_alerts(db: Session, user_id: int, first_day: date) -> list[Alert]:
    summary = monthly_budgets(db, user_id, first_day)
    over = [x for x in summary.lines if x.status == "over" and x.remaining is not None]
    over.sort(key=lambda x: x.remaining or ZERO)  # el más superado primero
    return [
        Alert(
            kind="budget_over",
            level="danger",
            title="Presupuesto",
            message=f"Has superado {x.name} en {eur(-(x.remaining or ZERO))}.",
            category_id=x.category_id,
            amount=-(x.remaining or ZERO),
        )
        for x in over
    ]


def _spending_alerts(db: Session, user_id: int, first_day: date, skip: set[int]) -> list[Alert]:
    months = _months_with_data(db, user_id, add_months(first_day, -AVERAGE_MONTHS), first_day)
    if not months:
        return []
    totals: dict[int, Decimal] = {}
    for month in months:
        for category_id, spent in spent_by_category(db, user_id, month).items():
            totals[category_id] = totals.get(category_id, ZERO) + spent
    names = dict(
        db.execute(select(Category.id, Category.name).where(Category.user_id == user_id)).all()
    )
    alerts = []
    for category_id, spent in spent_by_category(db, user_id, first_day).items():
        if category_id in skip:
            continue
        average = (totals.get(category_id, ZERO) / len(months)).quantize(CENTS)
        if spent > average * SPENDING_RATIO and spent - average >= SPENDING_MIN_DIFF:
            alerts.append(
                Alert(
                    kind="spending_high",
                    level="warning",
                    title="Gasto alto",
                    message=(
                        f"{names[category_id]}: {eur(spent)} este mes, "
                        f"frente a {eur(average)} de media."
                    ),
                    category_id=category_id,
                    amount=spent - average,
                )
            )
    alerts.sort(key=lambda a: -(a.amount or ZERO))
    return alerts


def _expense_change_alert(db: Session, user_id: int, first_day: date) -> list[Alert]:
    flow = cashflow(db, user_id, first_day)
    if flow.expense_change is None:  # el mes anterior no tiene gastos
        return []
    previous = MONTH_NAMES[add_months(first_day, -1).month - 1]
    change = flow.expense_change
    sign = "+" if change > 0 else ""
    return [
        Alert(
            kind="expense_change",
            level="warning" if change > 0 else "positive",
            title="Gasto ↑" if change > 0 else "Gasto ↓",
            message=f"Gastos {sign}{change} % respecto a {previous}.",
            amount=flow.expense - flow.previous_expense,
        )
    ]


def _recurring_alerts(db: Session, user_id: int, first_day: date) -> list[Alert]:
    summary = detect_recurring(db, user_id, first_day)
    alerts = [
        Alert(
            kind="recurring_new",
            level="info",
            title="Nuevo recurrente",
            message=(
                f"{r.description}: {eur(r.amount)} "
                f"{'al mes' if r.frequency == 'monthly' else 'al año'}."
            ),
            category_id=r.category_id,
            amount=r.monthly_amount,
        )
        for r in summary.items
        if r.is_new
    ]
    count = len(summary.items)
    if count:
        payments = "pago recurrente suma" if count == 1 else "pagos recurrentes suman"
        alerts.append(
            Alert(
                kind="recurring_total",
                level="info",
                title="Recurrentes",
                message=f"{count} {payments} {eur(summary.monthly_total)} al mes.",
                amount=summary.monthly_total,
            )
        )
    return alerts


def monthly_alerts(db: Session, user_id: int, first_day: date) -> AlertSummary:
    budget = _budget_alerts(db, user_id, first_day)
    over_budget = {a.category_id for a in budget if a.category_id is not None}
    return AlertSummary(
        month=month_key(first_day),
        items=[
            *budget,
            *_spending_alerts(db, user_id, first_day, over_budget),
            *_expense_change_alert(db, user_id, first_day),
            *_recurring_alerts(db, user_id, first_day),
        ],
    )
