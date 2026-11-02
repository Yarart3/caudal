"""Objetivo de patrimonio del usuario de la sesión: GET, PUT y DELETE /api/goals.

`month=AAAA-MM` es opcional: sin él, el mes del último movimiento (como los paneles).
"""

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.dashboard.service import resolve_month
from app.db import get_db
from app.goals import goal_progress
from app.models import Goal, User

router = APIRouter(prefix="/api/goals", tags=["goals"])

GoalName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Target = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

DEFAULT_NAME = "Objetivo de patrimonio"
CENTS = Decimal("0.01")


class GoalIn(BaseModel):
    name: GoalName = DEFAULT_NAME
    target_amount: Target


class MilestoneOut(BaseModel):
    amount: Decimal
    reached: bool


class GoalOut(BaseModel):
    month: str
    net_worth: Decimal
    name: str | None
    target_amount: Decimal | None
    percent: int | None
    remaining: Decimal | None
    last_milestone: Decimal | None
    next_milestones: list[Decimal]
    milestones: list[MilestoneOut]


def _month(db: Session, user: User, month: str | None) -> date:
    try:
        return resolve_month(db, user.id, month)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None


def _out(db: Session, user: User, first_day: date) -> GoalOut:
    return GoalOut(**asdict(goal_progress(db, user.id, first_day)))


@router.get("")
def get_goal(
    month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> GoalOut:
    """Objetivo (o null si no hay), patrimonio del mes, porcentaje e hitos."""
    return _out(db, user, _month(db, user, month))


@router.put("")
def put_goal(
    body: GoalIn,
    month: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> GoalOut:
    """Crea o cambia el objetivo del usuario (solo hay uno)."""
    first_day = _month(db, user, month)
    goal = db.scalar(select(Goal).where(Goal.user_id == user.id))
    if goal is None:
        goal = Goal(user_id=user.id)
        db.add(goal)
    goal.name = body.name
    goal.target_amount = body.target_amount.quantize(CENTS)
    db.commit()
    return _out(db, user, first_day)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    """Quita el objetivo. Si no había, no pasa nada."""
    db.execute(delete(Goal).where(Goal.user_id == user.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
