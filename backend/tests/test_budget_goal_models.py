"""Fase 2, parte 2.1: restricciones de presupuestos (categories.monthly_budget) y objetivos."""

from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Goal, User


def _category(db: Session, user: User, kind: str, budget: str | None) -> Category:
    category = Category(
        user_id=user.id,
        name=f"Prueba {kind}",
        kind=kind,
        monthly_budget=Decimal(budget) if budget is not None else None,
    )
    db.add(category)
    db.commit()
    return category


def test_expense_category_accepts_budget(db: Session, make_user) -> None:
    category = _category(db, make_user("gerard"), "expense", "250.00")
    db.refresh(category)
    assert category.monthly_budget == Decimal("250.00")


def test_category_without_budget_is_allowed(db: Session, make_user) -> None:
    assert _category(db, make_user("gerard"), "income", None).monthly_budget is None


@pytest.mark.parametrize(
    ("kind", "budget"), [("income", "100.00"), ("expense", "0"), ("expense", "-5")]
)
def test_invalid_budget_is_rejected(db: Session, make_user, kind: str, budget: str) -> None:
    user = make_user("gerard")
    with pytest.raises(IntegrityError):
        _category(db, user, kind, budget)
    db.rollback()


def test_one_goal_per_user(db: Session, make_user) -> None:
    user = make_user("gerard")
    db.add(Goal(user_id=user.id, name="Meta", target_amount=Decimal("50000.00")))
    db.commit()
    db.add(Goal(user_id=user.id, name="Otra", target_amount=Decimal("100000.00")))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_goal_amount_must_be_positive(db: Session, make_user) -> None:
    user = make_user("gerard")
    db.add(Goal(user_id=user.id, name="Meta", target_amount=Decimal("0")))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_goal_is_deleted_with_its_user(db: Session, make_user) -> None:
    user = make_user("gerard")
    db.add(Goal(user_id=user.id, name="Meta", target_amount=Decimal("25000.00")))
    db.commit()
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    assert db.scalar(select(Goal)) is None
