"""Presupuestos del mes: cuánto se ha gastado en cada categoría frente a su presupuesto.

- El presupuesto es fijo por categoría (categories.monthly_budget) y vale para todos los meses:
  si se cambia, los meses pasados se recalculan con el nuevo (decisión de la Fase 2).
- «Gastado» se cuenta igual que el gasto por categoría del panel (DISENO 9.1): solo importes
  negativos y sin transferencias internas. Una devolución (+) no resta: cuenta como ingreso.
- Estados: «ok» por debajo del 90 %, «near» (Al límite) del 90 % al 100 % y «over» (Superado)
  por encima del 100 %. Se decide con los importes exactos, no con el porcentaje redondeado.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dashboard.months import month_end, month_key
from app.models import Account, Category, Transaction

BudgetStatus = Literal["ok", "near", "over"]

ZERO = Decimal("0.00")
NEAR_RATIO = Decimal("0.90")
DEFAULT_COLOR = "#5B616B"


def budget_status(spent: Decimal, budget: Decimal) -> BudgetStatus:
    if spent > budget:
        return "over"
    if spent >= budget * NEAR_RATIO:
        return "near"
    return "ok"


@dataclass
class BudgetLine:
    category_id: int
    name: str
    color: str
    budget: Decimal | None  # None = la categoría no tiene presupuesto
    spent: Decimal
    remaining: Decimal | None  # negativo si se ha superado
    percent: int | None  # gastado / presupuesto, redondeado al entero
    status: BudgetStatus | None


@dataclass
class BudgetSummary:
    month: str
    total_budget: Decimal  # suma de los presupuestos puestos
    total_spent: Decimal  # gastado en las categorías con presupuesto
    lines: list[BudgetLine]


def spent_by_category(db: Session, user_id: int, first_day: date) -> dict[int, Decimal]:
    """{categoría: gastado en el mes} (en positivo), sin internas ni movimientos sin categoría."""
    rows = db.execute(
        select(Transaction.category_id, func.sum(-Transaction.amount))
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.is_internal_transfer.is_(False),
            Transaction.amount < 0,
            Transaction.category_id.is_not(None),
            Transaction.date >= first_day,
            Transaction.date <= month_end(first_day),
        )
        .group_by(Transaction.category_id)
    ).all()
    return {category_id: Decimal(total) for category_id, total in rows}


def _line(category: Category, spent: Decimal) -> BudgetLine:
    budget = category.monthly_budget
    color = category.color or DEFAULT_COLOR
    if budget is None:
        return BudgetLine(category.id, category.name, color, None, spent, None, None, None)
    percent = int((spent / budget * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return BudgetLine(
        category_id=category.id,
        name=category.name,
        color=color,
        budget=budget,
        spent=spent,
        remaining=budget - spent,
        percent=percent,
        status=budget_status(spent, budget),
    )


def monthly_budgets(db: Session, user_id: int, first_day: date) -> BudgetSummary:
    """Todas las categorías de gasto del usuario: primero las que tienen presupuesto (de más a
    menos consumido) y después las demás (de más a menos gastado). La ventana «Editar» las
    necesita todas; la tarjeta solo enseña las que tienen presupuesto."""
    spent = spent_by_category(db, user_id, first_day)
    categories = db.scalars(
        select(Category).where(Category.user_id == user_id, Category.kind == "expense")
    )
    lines = [_line(c, spent.get(c.id, ZERO).quantize(ZERO)) for c in categories]
    lines.sort(
        key=lambda x: (
            x.budget is None,
            -(x.spent / x.budget) if x.budget is not None else -x.spent,
            x.name,
        )
    )
    with_budget = [x for x in lines if x.budget is not None]
    return BudgetSummary(
        month=month_key(first_day),
        total_budget=sum((x.budget for x in with_budget if x.budget is not None), ZERO),
        total_spent=sum((x.spent for x in with_budget), ZERO),
        lines=lines,
    )
