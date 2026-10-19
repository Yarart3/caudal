"""Cuentas del usuario de la sesión. Nadie ve ni toca las cuentas de otro usuario."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import get_db
from app.models import Account, User

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
AccountKind = Literal["spending", "investment", "mixed"]
LiquidityType = Literal["cash", "money_market"]
# Bancos con importador. Se amplía en la Fase 4 (caixabank, sabadell, genérico).
ImportFormat = Literal["imagin", "wise"]
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]

DUPLICATE_NAME = "Ya tienes una cuenta con ese nombre"
NOT_FOUND = "Cuenta no encontrada"


class _BalanceCheck(BaseModel):
    @model_validator(mode="after")
    def _balance_and_date_together(self):
        has_balance = getattr(self, "reference_balance", None) is not None
        has_date = getattr(self, "reference_balance_date", None) is not None
        if has_balance != has_date:
            raise ValueError("El saldo de referencia y su fecha van juntos")
        return self


class AccountCreate(_BalanceCheck):
    name: AccountName
    kind: AccountKind
    import_format: ImportFormat | None = None
    liquidity_type: LiquidityType = "cash"
    reference_balance: Money | None = None
    reference_balance_date: date | None = None


class AccountUpdate(BaseModel):
    """PATCH: solo se cambian los campos que se envían (el saldo y su fecha se comprueban
    después, con los valores ya combinados con los de la cuenta)."""

    name: AccountName | None = None
    kind: AccountKind | None = None
    import_format: ImportFormat | None = None
    liquidity_type: LiquidityType | None = None
    reference_balance: Money | None = None
    reference_balance_date: date | None = None


class AccountOut(BaseModel):
    id: int
    name: str
    kind: str
    import_format: str | None
    liquidity_type: str
    # Dinero: Decimal en Python; en el JSON viaja como texto ("1234.50"), nunca como float
    reference_balance: Decimal | None
    reference_balance_date: date | None


def _out(account: Account) -> AccountOut:
    return AccountOut.model_validate(account, from_attributes=True)


def get_own_account(db: Session, user: User, account_id: int) -> Account:
    """La cuenta, solo si es del usuario. Si es de otro, 404 (como si no existiera)."""
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return account


def _commit_or_duplicate(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_NAME) from None


@router.get("")
def list_accounts(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[AccountOut]:
    accounts = db.scalars(select(Account).where(Account.user_id == user.id).order_by(Account.id))
    return [_out(a) for a in accounts]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> AccountOut:
    account = Account(user_id=user.id, **body.model_dump())
    db.add(account)
    _commit_or_duplicate(db)
    return _out(account)


@router.get("/{account_id}")
def get_account(
    account_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> AccountOut:
    return _out(get_own_account(db, user, account_id))


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    body: AccountUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AccountOut:
    account = get_own_account(db, user, account_id)
    changes = body.model_dump(exclude_unset=True)
    for field in ("name", "kind", "liquidity_type"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"El campo {field} no puede ir vacío"
            )
    for field, value in changes.items():
        setattr(account, field, value)
    if (account.reference_balance is None) != (account.reference_balance_date is None):
        db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El saldo de referencia y su fecha van juntos",
        )
    _commit_or_duplicate(db)
    return _out(account)
