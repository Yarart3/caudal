"""Operaciones de inversión del usuario de la sesión (Fase 3, DISENO §7.2 y §7.4).

- GET  /api/investments/operations?account_id=&product_id=  (las más recientes primero)
- POST /api/investments/operations
- GET/PATCH/DELETE /api/investments/operations/{id}
- GET  /api/investments/template?format=xlsx|csv  (plantilla vacía para el historial)
- POST /api/investments/import  (multipart: account_id, file, confirm)

Importes siempre en positivo; el sentido lo da el tipo: en una compra, lo que salió de la cuenta
(comisiones incluidas); en una venta o un dividendo, lo que entró; en una comisión suelta, lo que
se pagó. Las compras y ventas llevan participaciones; los dividendos y las comisiones, no.
Nunca se puede haber vendido más de lo que había en esa cuenta (se comprueba al crear, editar,
borrar e importar). "Duplicar operación" lo hace el formulario copiando los campos.
Nadie ve ni toca las operaciones de otro usuario.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ValidationError, field_serializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.backup.auto import auto_backup
from app.db import get_db
from app.importers.base import ImportFormatError
from app.importers.plantilla_inversiones import build_template
from app.investments.holdings import first_shortfall, format_shares
from app.investments.importer import import_template
from app.investments.operations import (
    FIELDS,
    INVESTMENT_ACCOUNTS,
    TZ,
    Amount,
    Fee,
    OperationCreate,
    OperationKind,
    Shares,
    first_error,
)
from app.models import Account, InvestmentOperation, Product, User

__all__ = ["TZ", "router"]

router = APIRouter(prefix="/api/investments", tags=["investments"])

# Alias: dentro de las clases, un campo llamado `date` con valor por defecto taparía al tipo
Day = date

NOT_FOUND = "Operación no encontrada"
ACCOUNT_NOT_FOUND = "Cuenta no encontrada"
PRODUCT_NOT_FOUND = "Producto no encontrado"
NOT_AN_INVESTMENT_ACCOUNT = "Esa cuenta no es de inversión (elige Trade Republic, Scalable…)"
# La plantilla de un historial largo ocupa unos KB: 2 MB sobra (y frena archivos enormes)
MAX_BYTES = 2 * 1024 * 1024
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class OperationUpdate(BaseModel):
    """PATCH: solo los campos que se envían; el resultado se valida como una operación nueva."""

    account_id: int | None = None
    product_id: int | None = None
    date: Day | None = None
    kind: OperationKind | None = None
    shares: Shares | None = None
    amount_eur: Amount | None = None
    fee_eur: Fee | None = None


def _plain(value: Decimal) -> str:
    # Sin notación científica: Decimal("0E-8") o Decimal("1.2E-7") saldrían así en el JSON
    return format(value, "f")


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
        return _plain(value)


class RowErrorOut(BaseModel):
    row: int
    field: str
    value: str
    message: str


class PreviewRowOut(BaseModel):
    row: int
    date: date
    product_id: int
    product_name: str
    kind: str
    shares: Decimal
    amount_eur: Decimal
    fee_eur: Decimal | None

    @field_serializer("shares")
    def _plain_shares(self, value: Decimal) -> str:
        return _plain(value)


class ImportOut(BaseModel):
    read: int
    new: int
    duplicates: int
    saved: bool
    errors: list[RowErrorOut]
    operations: list[PreviewRowOut]


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


def _own_investment_account(db: Session, user: User, account_id: int) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=ACCOUNT_NOT_FOUND)
    if account.kind not in INVESTMENT_ACCOUNTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=NOT_AN_INVESTMENT_ACCOUNT)
    return account


def _check_refs(db: Session, user: User, account_id: int, product_id: int) -> None:
    """Cuenta de inversión y producto, los dos del usuario (si son de otro: 404)."""
    _own_investment_account(db, user, account_id)
    if (
        db.scalar(select(Product.id).where(Product.id == product_id, Product.user_id == user.id))
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=PRODUCT_NOT_FOUND)


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
                    f"{shortfall.date:%d/%m/%Y} quedarían {format_shares(shortfall.shares)}"
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
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=first_error(error)
        ) from None
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


@router.get("/template")
def download_template(
    format: Literal["xlsx", "csv"] = "xlsx", _: User = Depends(current_user)
) -> Response:
    media = XLSX if format == "xlsx" else "text/csv; charset=utf-8"
    return Response(
        content=build_template(format),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="plantilla_inversiones.{format}"'},
    )


@router.post("/import")
def import_file(
    account_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    background: BackgroundTasks,
    confirm: Annotated[bool, Form()] = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ImportOut:
    """Sin `confirm`: vista previa (no guarda). Con `confirm=true`: guarda todo o nada; mira
    `saved` en la respuesta."""
    account = _own_investment_account(db, user, account_id)
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, detail="El archivo es demasiado grande (máximo 2 MB)"
        )
    if not data.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El archivo está vacío")
    try:
        result = import_template(db, user, account, data, confirm)
    except ImportFormatError as error:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    if result.saved and result.new > 0:
        background.add_task(auto_backup.run_quietly, "import")  # como al importar extractos
    # El archivo no se guarda en ningún sitio: se descarta al acabar la petición
    return ImportOut(
        read=result.read,
        new=result.new,
        duplicates=result.duplicates,
        saved=result.saved,
        errors=[RowErrorOut(**vars(e)) for e in result.errors],
        operations=[PreviewRowOut(**vars(o)) for o in result.operations],
    )
