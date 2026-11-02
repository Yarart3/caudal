"""Avisos del usuario de la sesión: GET /api/alerts.

`month=AAAA-MM` es opcional: sin él, el mes del último movimiento (como los paneles).
"""

from dataclasses import asdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.alerts import AlertKind, AlertLevel, monthly_alerts
from app.auth.deps import current_user
from app.dashboard.service import resolve_month
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    kind: AlertKind
    level: AlertLevel
    title: str
    message: str
    category_id: int | None
    amount: Decimal | None


class AlertsOut(BaseModel):
    month: str
    items: list[AlertOut]


@router.get("")
def get_alerts(
    month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> AlertsOut:
    """Avisos del mes: presupuestos superados, gasto alto, cambio frente al mes anterior y
    pagos recurrentes."""
    try:
        first_day = resolve_month(db, user.id, month)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    return AlertsOut(**asdict(monthly_alerts(db, user.id, first_day)))
