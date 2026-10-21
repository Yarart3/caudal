"""Reglas de categorización del usuario de la sesión (DISENO 9.4).

- POST /api/rules crea una regla o, si ya hay una con el mismo texto, la sustituye. Es lo
  que usa «¿Aplicar siempre a 'X'?» después de cambiar la categoría de un movimiento.
- POST /api/rules/apply vuelve a pasar las reglas a los movimientos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.categories import get_own_category
from app.auth.deps import current_user
from app.categories import apply_rules, compile_rules
from app.categories.seed import PRIORITY_REVIEW, PRIORITY_USER
from app.db import get_db
from app.importers.base import normalize_text
from app.models import Account, Rule, Transaction, User

router = APIRouter(prefix="/api/rules", tags=["rules"])

Pattern = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Priority = Annotated[int, Field(ge=1, le=1000)]

NOT_FOUND = "Regla no encontrada"
EMPTY_PATTERN = "Escribe el texto que tiene que contener el concepto"


class RuleCreate(BaseModel):
    pattern: Pattern
    category_id: int | None  # None = dejar por revisar (como Bizum)
    apply: bool = True  # reaplicar a los movimientos por revisar


class RuleUpdate(BaseModel):
    pattern: Pattern | None = None
    category_id: int | None = None
    priority: Priority | None = None


class RuleOut(BaseModel):
    id: int
    pattern: str
    category_id: int | None
    priority: int
    created_by: str


class RuleSaved(BaseModel):
    rule: RuleOut
    replaced: bool  # ya había una regla con ese texto y se ha sustituido
    categorized: int  # movimientos por revisar que han quedado categorizados


class ApplyOut(BaseModel):
    categorized: int
    review: int  # los que siguen por revisar después de aplicar


def _out(rule: Rule) -> RuleOut:
    return RuleOut.model_validate(rule, from_attributes=True)


def _clean_pattern(pattern: str) -> str:
    """Se guarda normalizado (mayúsculas, sin acentos): así se ve igual que se compara."""
    text = normalize_text(pattern)
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=EMPTY_PATTERN)
    return text


def _get_own_rule(db: Session, user: User, rule_id: int) -> Rule:
    rule = db.scalar(select(Rule).where(Rule.id == rule_id, Rule.user_id == user.id))
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return rule


def _pending(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user.id,
            Transaction.category_status == "review",
            Transaction.is_internal_transfer.is_(False),
        )
    )


@router.get("")
def list_rules(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[RuleOut]:
    """En el mismo orden en que las mira el motor: la primera que encaja, gana."""
    rules = {r.id: r for r in db.scalars(select(Rule).where(Rule.user_id == user.id))}
    return [_out(rules[c.id]) for c in compile_rules(rules.values())]


@router.post("")
def save_rule(
    body: RuleCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> RuleSaved:
    pattern = _clean_pattern(body.pattern)
    if body.category_id is not None:
        get_own_category(db, user, body.category_id)  # 404 si es de otro
    priority = PRIORITY_USER if body.category_id is not None else PRIORITY_REVIEW

    existing = next(
        (
            r
            for r in db.scalars(select(Rule).where(Rule.user_id == user.id))
            if normalize_text(r.pattern) == pattern
        ),
        None,
    )
    if existing is None:
        rule = Rule(user_id=user.id, pattern=pattern, created_by="user")
        db.add(rule)
    else:
        rule = existing
    rule.category_id = body.category_id
    rule.priority = priority
    rule.created_by = "user"
    db.flush()
    categorized = apply_rules(db, user.id) if body.apply else 0
    db.commit()
    return RuleSaved(rule=_out(rule), replaced=existing is not None, categorized=categorized)


@router.patch("/{rule_id}")
def update_rule(
    rule_id: int,
    body: RuleUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> RuleOut:
    rule = _get_own_rule(db, user, rule_id)
    changes = body.model_dump(exclude_unset=True)
    if "pattern" in changes:
        if changes["pattern"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=EMPTY_PATTERN)
        rule.pattern = _clean_pattern(changes["pattern"])
    if "category_id" in changes:
        if changes["category_id"] is not None:
            get_own_category(db, user, changes["category_id"])
        rule.category_id = changes["category_id"]
    if "priority" in changes:
        if changes["priority"] is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La prioridad no puede ir vacía"
            )
        rule.priority = changes["priority"]
    db.commit()
    return _out(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    """Los movimientos que ya categorizó se quedan como están (usa «Reaplicar» si no)."""
    db.delete(_get_own_rule(db, user, rule_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/apply")
def apply_all(
    include_auto: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ApplyOut:
    """Pasa las reglas a los movimientos por revisar. Con `include_auto=true`, también a los
    categorizados automáticamente (nunca a los puestos a mano ni a las internas)."""
    categorized = apply_rules(db, user.id, include_auto=include_auto)
    db.commit()
    return ApplyOut(categorized=categorized, review=_pending(db, user))
