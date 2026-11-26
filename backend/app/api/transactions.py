"""Movimientos del usuario de la sesión: listar con filtros, alta, edición y borrado.

Fase 5: cada movimiento puede llevar una nota y etiquetas (`GET /api/transactions/tags` da las
del usuario con cuántos movimientos tiene cada una).
"""

import datetime as dt
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.api.accounts import get_own_account
from app.api.categories import get_own_category
from app.auth.deps import current_user
from app.categories import apply_rules
from app.db import get_db
from app.exports import STATUS_LABELS, XLSX, ExportRow, build_transactions_xlsx
from app.models import Account, Category, Transaction, User
from app.transfers import match_internal_transfers
from app.transfers.matcher import mark_internal

router = APIRouter(prefix="/api/transactions", tags=["transactions"])

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]
# Estado que se ve en la tabla: los de la BD + «internal» (las transferencias internas)
StatusFilter = Literal["auto", "manual", "review", "internal"]

TZ = ZoneInfo("Europe/Madrid")
NOT_FOUND = "Movimiento no encontrado"
MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MAX_LIMIT = 1000
MAX_TAGS = 10
TAG_MAX_LENGTH = 30
NOTE_MAX_LENGTH = 500

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=NOTE_MAX_LENGTH)]
Tags = Annotated[list[str], Field(max_length=MAX_TAGS)]


class TransactionCreate(BaseModel):
    account_id: int
    date: date
    description: Description
    amount: Money  # negativo = gasto, positivo = ingreso
    note: Note | None = None
    tags: Tags = []


class TransactionUpdate(BaseModel):
    """PATCH: solo cambia lo que se envía.

    - `category_id` con un id → categoría puesta a mano (`manual`); con null → por revisar.
    - `is_internal_transfer` marca o desmarca la transferencia interna a mano.
    - `note` vacía o null → sin nota. `tags` sustituye la lista entera ([] = sin etiquetas).
    """

    account_id: int | None = None
    # dt.date: con «date: date | None = None» el nombre del campo tapa el tipo
    date: dt.date | None = None
    description: Description | None = None
    amount: Money | None = None
    category_id: int | None = None
    is_internal_transfer: bool | None = None
    note: Note | None = None
    tags: Tags | None = None


class TransactionOut(BaseModel):
    id: int
    account_id: int
    date: date
    description: str
    amount: Decimal
    category_id: int | None
    category_status: str
    is_internal_transfer: bool
    note: str | None
    tags: list[str]


class TagCount(BaseModel):
    name: str
    transactions: int


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int  # cuántos cumplen los filtros (aunque `limit` corte la lista)


def _out(tx: Transaction) -> TransactionOut:
    return TransactionOut.model_validate(tx, from_attributes=True)


def get_own_transaction(db: Session, user: User, transaction_id: int) -> Transaction:
    """El movimiento, solo si es de una cuenta del usuario. Si no, 404."""
    tx = db.scalar(
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .where(Transaction.id == transaction_id, Account.user_id == user.id)
    )
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return tx


def _month_range(month: str) -> tuple[date, date]:
    match = MONTH_RE.match(month)
    if match is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El mes tiene que ser AAAA-MM"
        )
    year, number = int(match.group(1)), int(match.group(2))
    start = date(year, number, 1)
    end = date(year + 1, 1, 1) if number == 12 else date(year, number + 1, 1)
    return start, end


def _user_tags(db: Session, user: User) -> list[tuple[str, int]]:
    """Etiquetas del usuario con cuántos movimientos tiene cada una, por orden alfabético."""
    tag = func.unnest(Transaction.tags).label("tag")
    inner = (
        select(tag)
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.user_id == user.id)
        .subquery()
    )
    rows = db.execute(
        select(inner.c.tag, func.count())
        .group_by(inner.c.tag)
        .order_by(func.lower(inner.c.tag), inner.c.tag)
    )
    return [(name, count) for name, count in rows]


def _clean_note(note: str | None) -> str | None:
    return note or None  # ya viene sin espacios a los lados; vacía = sin nota


def _clean_tags(db: Session, user: User, tags: list[str]) -> list[str]:
    """Quita espacios de más y repetidas (sin mirar mayúsculas) y, si el usuario ya tiene la
    etiqueta escrita de otra forma («Viaje» / «viaje»), usa la que ya tiene."""
    known = {name.lower(): name for name, _ in _user_tags(db, user)}
    result: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        name = " ".join(raw.split())
        if not name:
            continue
        if len(name) > TAG_MAX_LENGTH:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Una etiqueta puede tener como mucho {TAG_MAX_LENGTH} caracteres",
            )
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(known.get(key, name))
    return result


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class Filters:
    """Filtros de la lista de movimientos (los usan la lista y la exportación a Excel)."""

    month: str | None = None
    q: str | None = None
    category: int | None = None
    tag: str | None = None
    status: StatusFilter | None = None
    account: int | None = None


def transaction_filters(
    month: str | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: int | None = None,
    tag: Annotated[str | None, Query(max_length=TAG_MAX_LENGTH)] = None,
    status_: Annotated[StatusFilter | None, Query(alias="status")] = None,
    account: int | None = None,
) -> Filters:
    """Filtros desde la URL.

    - `month=2026-09`: solo ese mes. `q`: busca en el concepto, en la nota y en el nombre de la
      categoría (sin distinguir mayúsculas; los acentos sí cuentan). `category`, `account`: por
      id. `tag`: los que llevan esa etiqueta.
    - `status`: `review` (por revisar), `auto`, `manual` o `internal` (transferencias internas,
      que no salen en los otros tres).
    """
    if month is not None:
        _month_range(month)  # 422 si no es AAAA-MM
    return Filters(month, q, category, tag, status_, account)


def filtered_query(filters: Filters, user: User) -> Select[tuple[Transaction]]:
    """Movimientos del usuario que cumplen los filtros (sin orden ni límite)."""
    query = (
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Account.user_id == user.id)  # nunca movimientos de otro usuario
    )
    if filters.month is not None:
        start, end = _month_range(filters.month)
        query = query.where(Transaction.date >= start, Transaction.date < end)
    if filters.q is not None and filters.q.strip():
        pattern = f"%{_escape_like(filters.q.strip())}%"
        query = query.where(
            or_(
                Transaction.description.ilike(pattern, escape="\\"),
                Transaction.note.ilike(pattern, escape="\\"),
                Category.name.ilike(pattern, escape="\\"),
            )
        )
    if filters.category is not None:
        query = query.where(Transaction.category_id == filters.category)
    if filters.account is not None:
        query = query.where(Transaction.account_id == filters.account)
    if filters.tag is not None and filters.tag.strip():
        query = query.where(Transaction.tags.contains([" ".join(filters.tag.split())]))
    if filters.status == "internal":
        query = query.where(Transaction.is_internal_transfer.is_(True))
    elif filters.status is not None:
        query = query.where(
            Transaction.category_status == filters.status,
            Transaction.is_internal_transfer.is_(False),
        )
    return query


NEWEST_FIRST = (Transaction.date.desc(), Transaction.id.desc())


@router.get("")
def list_transactions(
    filters: Annotated[Filters, Depends(transaction_filters)],
    limit: Annotated[int, Query(ge=0, le=MAX_LIMIT)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TransactionPage:
    """Movimientos del usuario, del más reciente al más antiguo (filtros en
    `transaction_filters`). `limit=0` devuelve solo el total (para el contador de «por
    revisar»)."""
    query = filtered_query(filters, user)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items: list[Transaction] = []
    if limit > 0:
        items = list(db.scalars(query.order_by(*NEWEST_FIRST).limit(limit).offset(offset)))
    return TransactionPage(items=[_out(tx) for tx in items], total=total)


@router.get("/export")
def export_transactions(
    filters: Annotated[Filters, Depends(transaction_filters)],
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Los movimientos con los filtros de la lista, en Excel (Fase 5). Sin límite."""
    rows = db.execute(
        filtered_query(filters, user)
        .add_columns(Account.name, Category.name)
        .order_by(*NEWEST_FIRST)
    ).all()
    content = build_transactions_xlsx(
        [ExportRow(tx, account_name, category_name) for tx, account_name, category_name in rows],
        describe_filters(filters, db, user),
    )
    stamp = dt.datetime.now(TZ).strftime("%Y-%m-%d")
    name = f"caudal_movimientos_{filters.month or 'todos'}_{stamp}.xlsx"
    return Response(
        content=content,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def describe_filters(filters: Filters, db: Session, user: User) -> list[str]:
    """Los filtros en castellano, para la hoja «Resumen»."""
    parts: list[str] = []
    if filters.month:
        parts.append(f"Mes: {filters.month}")
    if filters.q and filters.q.strip():
        parts.append(f"Buscar: «{filters.q.strip()}»")
    if filters.category is not None:
        category = db.scalar(
            select(Category).where(Category.id == filters.category, Category.user_id == user.id)
        )
        parts.append(f"Categoría: {category.name if category else '(no existe)'}")
    if filters.account is not None:
        account = db.scalar(
            select(Account).where(Account.id == filters.account, Account.user_id == user.id)
        )
        parts.append(f"Cuenta: {account.name if account else '(no existe)'}")
    if filters.tag and filters.tag.strip():
        parts.append(f"Etiqueta: {filters.tag.strip()}")
    if filters.status:
        parts.append(f"Estado: {STATUS_LABELS[filters.status]}")
    return parts


@router.get("/tags")
def list_tags(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[TagCount]:
    """Etiquetas del usuario (para sugerirlas y para el filtro), con su número de movimientos."""
    return [TagCount(name=name, transactions=count) for name, count in _user_tags(db, user)]


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
        note=_clean_note(body.note),
        tags=_clean_tags(db, user, body.tags),
        category_status="review",
        fingerprint=None,  # a mano: sin huella (los NULL no chocan con la restricción única)
    )
    db.add(tx)
    db.flush()
    # Un ingreso apuntado a mano (por ejemplo, en Trade Republic) se empareja igual que uno
    # importado con la salida de imagin (DISENO 9.3)
    match_internal_transfers(db, user.id, [tx.id], {})
    apply_rules(db, user.id, [tx.id])  # si no es interna, como uno importado
    db.commit()
    return _out(tx)


@router.patch("/{transaction_id}")
def update_transaction(
    transaction_id: int,
    body: TransactionUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TransactionOut:
    """Editar un movimiento. Si es importado, la huella no cambia: volver a importar el mismo
    extracto no lo duplica ni deshace la edición."""
    tx = get_own_transaction(db, user, transaction_id)
    changes = body.model_dump(exclude_unset=True)
    for field in ("account_id", "date", "description", "amount", "is_internal_transfer"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"El campo {field} no puede ir vacío"
            )

    if "note" in changes:
        tx.note = _clean_note(changes["note"])
    if "tags" in changes:
        tx.tags = _clean_tags(db, user, changes["tags"] or [])

    if "account_id" in changes:
        tx.account_id = get_own_account(db, user, changes["account_id"]).id
    for field in ("date", "description", "amount"):
        if field in changes:
            setattr(tx, field, changes[field])

    if "is_internal_transfer" in changes:
        if changes["is_internal_transfer"]:
            mark_internal(tx)
        else:
            tx.is_internal_transfer = False
            if tx.category_id is None:
                tx.category_status = "review"

    if "category_id" in changes:
        if changes["category_id"] is None:
            tx.category_id = None
            tx.category_status = "review"
        else:
            tx.category_id = get_own_category(db, user, changes["category_id"]).id
            tx.category_status = "manual"

    db.flush()
    if tx.category_status == "review":
        # Por ejemplo, al corregir el concepto o al desmarcar una transferencia
        apply_rules(db, user.id, [tx.id])
    db.commit()
    db.refresh(tx)
    return _out(tx)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    """Ojo: si el movimiento es importado y se vuelve a importar el mismo extracto, vuelve a
    entrar (su huella se borra con él)."""
    db.delete(get_own_transaction(db, user, transaction_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
