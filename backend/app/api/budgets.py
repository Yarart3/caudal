"""Presupuestos del usuario de la sesión: GET y PUT /api/budgets.

`month=AAAA-MM` es opcional: sin él, el mes del último movimiento (como los paneles).
"""

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.budgets import BudgetStatus, monthly_budgets
from app.dashboard.service import resolve_month
from app.db import get_db
from app.models import Category, User

router = APIRouter(prefix="/api/budgets", tags=["budgets"])

# Presupuesto: mayor que 0 y con 2 decimales como máximo. None = quitar el presupuesto.
Budget = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]

CENTS = Decimal("0.01")
NOT_FOUND = "Categoría no encontrada"
ONLY_EXPENSES = "Solo las categorías de gasto tienen presupuesto"
REPEATED = "Una categoría aparece más de una vez"


class BudgetLineOut(BaseModel):
    category_id: int
    name: str
    color: str
    budget: Decimal | None
    spent: Decimal
    remaining: Decimal | None
    percent: int | None
    status: BudgetStatus | None


class BudgetsOut(BaseModel):
    month: str
    total_budget: Decimal
    total_spent: Decimal
    lines: list[BudgetLineOut]


class BudgetIn(BaseModel):
    category_id: int
    amount: Budget | None


class BudgetsIn(BaseModel):
    items: list[BudgetIn] = Field(max_length=200)


def _month(db: Session, user: User, month: str | None) -> date:
    try:
        return resolve_month(db, user.id, month)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None


def _out(db: Session, user: User, first_day: date) -> BudgetsOut:
    summary = monthly_budgets(db, user.id, first_day)
    return BudgetsOut(
        month=summary.month,
        total_budget=summary.total_budget,
        total_spent=summary.total_spent,
        lines=[BudgetLineOut(**asdict(line)) for line in summary.lines],
    )


@router.get("")
def get_budgets(
    month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> BudgetsOut:
    """Todas las categorías de gasto con su presupuesto (o sin él), lo gastado y el estado."""
    return _out(db, user, _month(db, user, month))


@router.put("")
def put_budgets(
    body: BudgetsIn,
    month: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> BudgetsOut:
    """Pone o quita (amount = null) el presupuesto de las categorías indicadas. Las que no
    vienen no cambian. Si alguna no vale, no se guarda ninguna."""
    first_day = _month(db, user, month)
    ids = [item.category_id for item in body.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=REPEATED)
    categories = {
        c.id: c
        for c in db.scalars(
            select(Category).where(Category.user_id == user.id, Category.id.in_(ids))
        )
    }
    for item in body.items:
        category = categories.get(item.category_id)
        if category is None:  # no existe o es de otro usuario
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
        if category.kind != "expense":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=ONLY_EXPENSES)
        # Siempre con 2 decimales («60» → 60.00), igual que lo devuelve la BD
        category.monthly_budget = item.amount.quantize(CENTS) if item.amount is not None else None
    db.commit()
    return _out(db, user, first_day)
