"""Progreso hacia el objetivo de patrimonio y los hitos (DISENO 3.1).

- El objetivo es uno por usuario (tabla goals) y lo pone el usuario en la app.
- El patrimonio es el del final del mes elegido, el mismo que enseña la pestaña Patrimonio.
- El porcentaje se redondea **hacia abajo**: con un 99,6 % no se enseña «100 % conseguido».
  Nunca es negativo.
- Los hitos no se guardan: es una serie fija (1.000, 2.500, 5.000, 10.000, 25.000 €…). Se
  marcan los conseguidos y se proponen los NEXT_MILESTONES siguientes, como la maqueta
  («Siguientes hitos: 25.000 € · 50.000 € · 100.000 €»). La serie empieza en 1.000 € para que
  también tenga sentido con un patrimonio pequeño.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dashboard.months import month_key
from app.dashboard.service import net_worth
from app.models import Goal

MILESTONES = tuple(
    Decimal(value)
    for value in (
        "1000",
        "2500",
        "5000",
        "10000",
        "25000",
        "50000",
        "100000",
        "250000",
        "500000",
        "1000000",
    )
)
NEXT_MILESTONES = 3
ZERO = Decimal("0.00")
CENTS = Decimal("0.01")


@dataclass
class Milestone:
    amount: Decimal
    reached: bool


@dataclass
class GoalProgress:
    month: str
    net_worth: Decimal
    name: str | None  # None = todavía no hay objetivo
    target_amount: Decimal | None
    percent: int | None  # patrimonio / objetivo, hacia abajo, de 0 en adelante
    remaining: Decimal | None  # lo que falta (0 si ya se ha conseguido)
    last_milestone: Decimal | None  # el hito más alto conseguido
    next_milestones: list[Decimal]
    milestones: list[Milestone]


def milestones(value: Decimal) -> list[Milestone]:
    return [Milestone(amount.quantize(CENTS), value >= amount) for amount in MILESTONES]


def goal_progress(db: Session, user_id: int, first_day: date) -> GoalProgress:
    total = net_worth(db, user_id, first_day).net_worth
    goal = db.scalar(select(Goal).where(Goal.user_id == user_id))
    steps = milestones(total)
    reached = [m.amount for m in steps if m.reached]
    upcoming = [m.amount for m in steps if not m.reached][:NEXT_MILESTONES]
    percent = remaining = None
    if goal is not None:
        ratio = (total / goal.target_amount * 100).quantize(Decimal("1"), rounding=ROUND_DOWN)
        percent = max(0, int(ratio))
        remaining = max(ZERO, goal.target_amount - total)
    return GoalProgress(
        month=month_key(first_day),
        net_worth=total,
        name=goal.name if goal else None,
        target_amount=goal.target_amount if goal else None,
        percent=percent,
        remaining=remaining,
        last_milestone=reached[-1] if reached else None,
        next_milestones=upcoming,
        milestones=steps,
    )
