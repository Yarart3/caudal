"""Datos de los paneles: GET /api/dashboard/net-worth y /api/dashboard/cashflow.

`month=AAAA-MM` es opcional: sin él, el mes del último movimiento del usuario.
"""

from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.dashboard import service
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class AccountBalanceOut(BaseModel):
    id: int
    name: str
    kind: str
    liquidity_type: str
    balance: Decimal


class NetWorthMonthOut(BaseModel):
    month: str
    liquidity: Decimal
    investments: Decimal


class NetWorthOut(BaseModel):
    month: str
    net_worth: Decimal
    liquidity: Decimal
    investments: Decimal
    savings: Decimal
    accounts: list[AccountBalanceOut]
    by_type: dict[str, Decimal]
    history: list[NetWorthMonthOut]


class CashflowMonthOut(BaseModel):
    month: str
    income: Decimal
    expense: Decimal


class CategorySpendOut(BaseModel):
    category_id: int | None
    name: str
    color: str
    amount: Decimal


class CashflowOut(BaseModel):
    month: str
    cash_total: Decimal
    income: Decimal
    expense: Decimal
    savings: Decimal
    savings_rate: int | None
    previous_expense: Decimal
    expense_change: int | None
    history: list[CashflowMonthOut]
    by_category: list[CategorySpendOut]


def _month(db: Session, user: User, month: str | None) -> date:
    try:
        return service.resolve_month(db, user.id, month)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None


@router.get("/net-worth")
def get_net_worth(
    month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> NetWorthOut:
    """Pestaña Patrimonio: indicadores, saldo de cada cuenta, reparto y evolución a 12 meses.
    En la 1c solo hay liquidez; las inversiones llegan en la Fase 3."""
    return NetWorthOut(**asdict(service.net_worth(db, user.id, _month(db, user, month))))


@router.get("/cashflow")
def get_cashflow(
    month: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> CashflowOut:
    """Pestaña Movimientos: indicadores, ingresos vs gastos a 12 meses y gasto por categoría.
    Sin transferencias internas."""
    return CashflowOut(**asdict(service.cashflow(db, user.id, _month(db, user, month))))
