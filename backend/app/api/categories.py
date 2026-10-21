"""Categorías del usuario de la sesión: listar, crear, editar y borrar (Ajustes)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.categories import apply_rules
from app.db import get_db
from app.models import Account, Category, Rule, Transaction, User

router = APIRouter(prefix="/api/categories", tags=["categories"])

CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
CategoryKind = Literal["expense", "income"]

DEFAULT_COLOR = "#5B616B"
NOT_FOUND = "Categoría no encontrada"
DUPLICATE_NAME = "Ya tienes una categoría con ese nombre"


class CategoryCreate(BaseModel):
    name: CategoryName
    kind: CategoryKind
    color: Color = DEFAULT_COLOR


class CategoryUpdate(BaseModel):
    name: CategoryName | None = None
    kind: CategoryKind | None = None
    color: Color | None = None


class CategoryOut(BaseModel):
    id: int
    name: str
    kind: str
    color: str
    transactions: int  # movimientos con esta categoría (para avisar antes de borrar)
    rules: int  # reglas que mandan a esta categoría


def get_own_category(db: Session, user: User, category_id: int) -> Category:
    """La categoría, solo si es del usuario. Si es de otro, 404 (como si no existiera)."""
    category = db.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return category


def _counts(db: Session, user: User) -> tuple[dict[int, int], dict[int, int]]:
    tx_counts = dict(
        db.execute(
            select(Transaction.category_id, func.count())
            .join(Account, Account.id == Transaction.account_id)
            .where(Account.user_id == user.id, Transaction.category_id.is_not(None))
            .group_by(Transaction.category_id)
        ).all()
    )
    rule_counts = dict(
        db.execute(
            select(Rule.category_id, func.count())
            .where(Rule.user_id == user.id, Rule.category_id.is_not(None))
            .group_by(Rule.category_id)
        ).all()
    )
    return tx_counts, rule_counts


def _out(category: Category, tx_counts: dict[int, int], rule_counts: dict[int, int]):
    return CategoryOut(
        id=category.id,
        name=category.name,
        kind=category.kind,
        color=category.color or DEFAULT_COLOR,
        transactions=tx_counts.get(category.id, 0),
        rules=rule_counts.get(category.id, 0),
    )


def _commit_or_duplicate(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_NAME) from None


@router.get("")
def list_categories(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[CategoryOut]:
    """Primero las de gasto y después las de ingreso, por orden alfabético."""
    categories = db.scalars(
        select(Category)
        .where(Category.user_id == user.id)
        .order_by(Category.kind, Category.name)  # 'expense' < 'income'
    )
    tx_counts, rule_counts = _counts(db, user)
    return [_out(c, tx_counts, rule_counts) for c in categories]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> CategoryOut:
    category = Category(user_id=user.id, **body.model_dump())
    db.add(category)
    _commit_or_duplicate(db)
    return _out(category, {}, {})


@router.patch("/{category_id}")
def update_category(
    category_id: int,
    body: CategoryUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CategoryOut:
    category = get_own_category(db, user, category_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"El campo {field} no puede ir vacío"
            )
        setattr(category, field, value)
    _commit_or_duplicate(db)
    tx_counts, rule_counts = _counts(db, user)
    return _out(category, tx_counts, rule_counts)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    """Borra la categoría y sus reglas. Sus movimientos vuelven a «por revisar» y se les pasan
    las demás reglas (alguna puede encajar)."""
    category = get_own_category(db, user, category_id)
    affected = list(
        db.scalars(select(Transaction.id).where(Transaction.category_id == category.id))
    )
    if affected:
        db.execute(
            update(Transaction)
            .where(Transaction.id.in_(affected))
            .values(category_id=None, category_status="review")
        )
    db.delete(category)  # las reglas se borran solas (ON DELETE CASCADE)
    db.flush()
    apply_rules(db, user.id, affected)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
