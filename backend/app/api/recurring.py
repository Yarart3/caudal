"""Pagos recurrentes del usuario de la sesión: GET /api/recurring.

`month=AAAA-MM` es opcional: sin él, el mes del último movimiento (como los paneles).
"""

from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.dashboard.service import resolve_month
from app.db import get_db
from app.models import User
from app.recurring import Frequency, detect_recurring

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


class RecurringOut(BaseModel):
    key: str
    description: str
    frequency: Frequency
    amount: Decimal
    monthly_amount: Decimal
    occurrences: int
    first_date: date
    last_date: date
    next_date: date
    detected_on: date
    is_new: bool
    category_id: int | None
    category_name: str
    category_color: str
    account_name: str


class RecurringSummaryOut(BaseModel):
    month: str
    monthly_total: Decimal
    items: list[RecurringOut]


@router.get("")
def get_recurring(
    month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> RecurringSummaryOut:
    """Pagos recurrentes activos al final del mes, con el total al mes."""
    try:
        first_day = resolve_month(db, user.id, month)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    return RecurringSummaryOut(**asdict(detect_recurring(db, user.id, first_day)))
