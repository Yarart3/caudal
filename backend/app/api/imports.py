"""Importar extractos: POST /api/imports (multipart con account_id + archivo)."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.accounts import get_own_account
from app.auth.deps import current_user
from app.db import get_db
from app.importers.base import ImportFormatError
from app.importers.service import import_statement
from app.models import User

router = APIRouter(prefix="/api/imports", tags=["imports"])

# Un extracto de un año de imagin ocupa unos pocos cientos de KB. 5 MB deja margen de sobra y
# evita que un archivo enorme (o un .xlsx malicioso muy comprimido) llene la memoria.
MAX_BYTES = 5 * 1024 * 1024


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


@router.post("")
def import_file(
    account_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
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
    )
