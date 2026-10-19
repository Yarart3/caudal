"""Movimientos. En la Fase 1b solo el alta manual (para las filas que el importador no ha
podido leer); el listado, la edición y el borrado llegan en la 1c."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.api.accounts import get_own_account
from app.auth.deps import current_user
from app.db import get_db
from app.models import Transaction, User
from app.transfers import match_internal_transfers

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]


class TransactionCreate(BaseModel):
    account_id: int
    date: date
    description: Description
    amount: Money  # negativo = gasto, positivo = ingreso


class TransactionOut(BaseModel):
    id: int
    account_id: int
    date: date
    description: str
    amount: Decimal
    category_id: int | None
    category_status: str
    is_internal_transfer: bool


@router.post("", status_code=status.HTTP_201_CREATED)
def create_transaction(
    body: TransactionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> TransactionOut:
    account = get_own_account(db, user, body.account_id)  # 404 si la cuenta es de otro
    tx = Transaction(
        account_id=account.id,
        date=body.date,
        description=body.description,
        amount=body.amount,
        category_status="review",
        fingerprint=None,  # a mano: sin huella (los NULL no chocan con la restricción única)
    )
    db.add(tx)
    db.flush()
    # Un ingreso apuntado a mano (por ejemplo, en Trade Republic) se empareja igual que uno
    # importado con la salida de imagin (DISENO 9.3)
    match_internal_transfers(db, user.id, [tx.id], {})
    db.commit()
    return TransactionOut.model_validate(tx, from_attributes=True)
