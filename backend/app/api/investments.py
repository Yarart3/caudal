"""Operaciones de inversión del usuario de la sesión (Fase 3, DISENO §7.2 y §7.4).

- GET  /api/investments/operations?account_id=&product_id=  (las más recientes primero)
- POST /api/investments/operations
- GET/PATCH/DELETE /api/investments/operations/{id}

Importes siempre en positivo; el sentido lo da el tipo: en una compra, lo que salió de la cuenta
(comisiones incluidas); en una venta o un dividendo, lo que entró; en una comisión suelta, lo que
se pagó. Las compras y ventas llevan participaciones; los dividendos y las comisiones, no.
Nunca se puede haber vendido más de lo que había en esa cuenta (se comprueba al crear, editar y
borrar). "Duplicar operación" lo hace el formulario copiando los campos: no necesita API.
Nadie ve ni toca las operaciones de otro usuario.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import get_db
from app.investments.holdings import first_shortfall
from app.models import Account, InvestmentOperation, Product, User

router = APIRouter(prefix="/api/investments", tags=["investments"])

# Alias: dentro de las clases, un campo llamado `date` con valor por defecto taparía al tipo
Day = date

TZ = ZoneInfo("Europe/Madrid")
INVESTMENT_ACCOUNTS = ("investment", "mixed")

OperationKind = Literal["buy", "sell", "dividend", "fee"]
Shares = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=8)]
Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Fee = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

NOT_FOUND = "Operación no encontrada"
ACCOUNT_NOT_FOUND = "Cuenta no encontrada"
PRODUCT_NOT_FOUND = "Producto no encontrado"
NOT_AN_INVESTMENT_ACCOUNT = "Esa cuenta no es de inversión (elige Trade Republic, Scalable…)"


class OperationCreate(BaseModel):
    account_id: int
    product_id: int
    date: date
    kind: OperationKind
    shares: Shares = Decimal(0)
    amount_eur: Amount
    fee_eur: Fee | None = None

    @field_validator("date")
    @classmethod
    def _not_in_the_future(cls, value: date) -> date:
        if value > datetime.now(TZ).date():
            raise ValueError("La fecha no puede ser posterior a hoy")
        return value

    @model_validator(mode="after")
    def _shares_and_fee(self):
        if self.kind in ("buy", "sell") and self.shares <= 0:
            raise ValueError("Indica cuántas participaciones has comprado o vendido")
        if self.kind in ("dividend", "fee") and self.shares != 0:
            raise ValueError("Un dividendo o una comisión no lleva participaciones")
        if self.fee_eur is not None and self.fee_eur > self.amount_eur:
            raise ValueError("La comisión no puede ser mayor que el importe")
        return self


class OperationUpdate(BaseModel):
    """PATCH: solo los campos que se envían; el resultado se valida como una operación nueva."""

    account_id: int | None = None
    product_id: int | None = None
    date: Day | None = None
    kind: OperationKind | None = None
    shares: Shares | None = None
    amount_eur: Amount | None = None
    fee_eur: Fee | None = None


class OperationOut(BaseModel):
    id: int
    account_id: int
    account_name: str
    product_id: int
    product_name: str
    date: date
    kind: str
    shares: Decimal
    amount_eur: Decimal
    fee_eur: Decimal | None

    @field_serializer("shares")
    def _plain_shares(self, value: Decimal) -> str:
        # Sin notación científica: Decimal("0E-8") o Decimal("1.2E-7") saldrían así en el JSON
        return format(value, "f")


FIELDS = ("account_id", "product_id", "date", "kind", "shares", "amount_eur", "fee_eur")


def _out(db: Session, op: InvestmentOperation) -> OperationOut:
    account, product = db.get(Account, op.account_id), db.get(Product, op.product_id)
    return OperationOut(
        account_name=account.name,
        product_name=product.name,
        **{field: getattr(op, field) for field in ("id", *FIELDS)},
    )


def _own_operation(db: Session, user: User, operation_id: int) -> InvestmentOperation:
    op = db.scalar(
        select(InvestmentOperation)
        .join(Account, Account.id == InvestmentOperation.account_id)
        .where(InvestmentOperation.id == operation_id, Account.user_id == user.id)
    )
    if op is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return op


def _check_refs(db: Session, user: User, account_id: int, product_id: int) -> None:
    """Cuenta de inversión y producto, los dos del usuario (si son de otro: 404)."""
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ACCOUNT_NOT_FOUND)
    if account.kind not in INVESTMENT_ACCOUNTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=NOT_AN_INVESTMENT_ACCOUNT)
    if (
        db.scalar(select(Product.id).where(Product.id == product_id, Product.user_id == user.id))
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=PRODUCT_NOT_FOUND)


def _format_shares(value: Decimal) -> str:
    text = f"{value.normalize():f}"
    return text.replace(".", ",")


def _commit_if_holdings_ok(db: Session, pairs: set[tuple[int, int]]) -> None:
    """Guarda solo si, en cada (cuenta, producto) tocado, nunca se vende más de lo que hay."""
    db.flush()
    for account_id, product_id in sorted(pairs):
        shortfall = first_shortfall(db, account_id, product_id)
        if shortfall is not None:
            db.rollback()
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Venderías más participaciones de las que tienes en esa cuenta: el "
                    f"{shortfall.date:%d/%m/%Y} quedarían {_format_shares(shortfall.shares)}"
                ),
            )
    db.commit()


@router.get("/operations")
def list_operations(
    account_id: Annotated[int | None, Query()] = None,
    product_id: Annotated[int | None, Query()] = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[OperationOut]:
    query = (
        select(InvestmentOperation)
        .join(Account, Account.id == InvestmentOperation.account_id)
        .where(Account.user_id == user.id)
    )
    if account_id is not None:
        query = query.where(InvestmentOperation.account_id == account_id)
    if product_id is not None:
        query = query.where(InvestmentOperation.product_id == product_id)
    query = query.order_by(InvestmentOperation.date.desc(), InvestmentOperation.id.desc())
    return [_out(db, op) for op in db.scalars(query)]


@router.post("/operations", status_code=status.HTTP_201_CREATED)
def create_operation(
    body: OperationCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> OperationOut:
    _check_refs(db, user, body.account_id, body.product_id)
    op = InvestmentOperation(**body.model_dump())
    db.add(op)
    _commit_if_holdings_ok(db, {(body.account_id, body.product_id)})
    db.refresh(op)  # con los decimales tal como quedan en la BD
    return _out(db, op)


@router.get("/operations/{operation_id}")
def get_operation(
    operation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> OperationOut:
    return _out(db, _own_operation(db, user, operation_id))


@router.patch("/operations/{operation_id}")
def update_operation(
    operation_id: int,
    body: OperationUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> OperationOut:
    op = _own_operation(db, user, operation_id)
    before = (op.account_id, op.product_id)
    merged = {field: getattr(op, field) for field in FIELDS} | body.model_dump(exclude_unset=True)
    try:
        valid = OperationCreate.model_validate(merged)
    except ValidationError as error:
        first = error.errors()[0]
        message = first["msg"].removeprefix("Value error, ")
        if first.get("type") != "value_error":
            message = (
                f"Datos no válidos: revisa {first['loc'][-1]}" if first.get("loc") else message
            )
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message) from None
    _check_refs(db, user, valid.account_id, valid.product_id)
    for field, value in valid.model_dump().items():
        setattr(op, field, value)
    _commit_if_holdings_ok(db, {before, (valid.account_id, valid.product_id)})
    db.refresh(op)
    return _out(db, op)


@router.delete("/operations/{operation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_operation(
    operation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    op = _own_operation(db, user, operation_id)
    pair = (op.account_id, op.product_id)
    db.delete(op)
    _commit_if_holdings_ok(db, {pair})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
