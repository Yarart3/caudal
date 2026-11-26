"""Importar extractos: POST /api/imports (multipart con account_id + archivo).

Fase 5: GET /api/imports lista las últimas importaciones del usuario y DELETE /api/imports/{id}
deshace una entera (app/importers/undo.py).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.accounts import get_own_account
from app.auth.deps import current_user
from app.backup.auto import auto_backup
from app.db import get_db
from app.importers.base import ImportFormatError
from app.importers.service import import_statement
from app.importers.undo import undo_import
from app.models import Account, Import, Transaction, User

router = APIRouter(prefix="/api/imports", tags=["imports"])

# Un extracto de un año de imagin ocupa unos pocos cientos de KB. 5 MB deja margen de sobra y
# evita que un archivo enorme (o un .xlsx malicioso muy comprimido) llene la memoria.
MAX_BYTES = 5 * 1024 * 1024
NOT_FOUND = "Importación no encontrada"


class RowErrorOut(BaseModel):
    row: int
    field: str
    value: str
    message: str


class ImportOut(BaseModel):
    read: int
    new: int
    duplicates: int
    review: int
    internal: int
    categorized: int
    errors: list[RowErrorOut]
    warnings: list[str]
    closing_balance: Decimal | None
    closing_date: date | None
    import_id: int | None  # para deshacerla; null si no ha entrado nada nuevo


class ImportRecordOut(BaseModel):
    id: int
    account_id: int
    created_at: datetime
    first_date: date | None
    last_date: date | None
    new: int  # movimientos que entraron
    remaining: int  # los que siguen ahí (se pueden haber borrado a mano)


class UndoOut(BaseModel):
    deleted: int
    unpaired: int
    balance_restored: bool


@router.get("")
def list_imports(
    account_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ImportRecordOut]:
    """Últimas importaciones del usuario (las que trajeron algo nuevo), la más reciente primero."""
    remaining = (
        select(func.count())
        .where(Transaction.import_id == Import.id)
        .correlate(Import)
        .scalar_subquery()
    )
    query = (
        select(Import, remaining)
        .join(Account, Account.id == Import.account_id)
        .where(Account.user_id == user.id)  # nunca las de otro usuario
        .order_by(Import.created_at.desc(), Import.id.desc())
        .limit(limit)
    )
    if account_id is not None:
        query = query.where(Import.account_id == account_id)
    return [
        ImportRecordOut(
            id=batch.id,
            account_id=batch.account_id,
            created_at=batch.created_at,
            first_date=batch.first_date,
            last_date=batch.last_date,
            new=batch.new_count,
            remaining=count,
        )
        for batch, count in db.execute(query)
    ]


@router.delete("/{import_id}")
def delete_import(
    import_id: int,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> UndoOut:
    """Deshace la importación: borra sus movimientos y deja la cuenta como estaba."""
    batch = db.scalar(
        select(Import)
        .join(Account, Account.id == Import.account_id)
        .where(Import.id == import_id, Account.user_id == user.id)
    )
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    result = undo_import(db, batch, user.id)
    db.commit()
    if result.deleted > 0:
        background.add_task(auto_backup.run_quietly, "import")
    return UndoOut(
        deleted=result.deleted,
        unpaired=result.unpaired,
        balance_restored=result.balance_restored,
    )


@router.post("")
def import_file(
    account_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ImportOut:
    account = get_own_account(db, user, account_id)  # 404 si la cuenta es de otro
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, detail="El archivo es demasiado grande (máximo 5 MB)"
        )
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El archivo está vacío")
    try:
        summary = import_statement(db, account, data)
    except ImportFormatError as error:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    # Backup tras importar (DISENO §12), después de responder: el usuario no espera
    if summary.new > 0:
        background.add_task(auto_backup.run_quietly, "import")
    # El archivo no se guarda en ningún sitio (DISENO 8.3): se descarta al acabar la petición
    return ImportOut(
        read=summary.read,
        new=summary.new,
        duplicates=summary.duplicates,
        review=summary.review,
        internal=summary.internal,
        categorized=summary.categorized,
        errors=[RowErrorOut(**vars(e)) for e in summary.errors],
        warnings=summary.warnings,
        closing_balance=summary.closing_balance,
        closing_date=summary.closing_date,
        import_id=summary.import_id,
    )
