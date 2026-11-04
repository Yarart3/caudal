"""Participaciones de un producto en una cuenta a lo largo del tiempo.

Regla: en ninguna fecha se puede haber vendido más de lo comprado **en esa cuenta** (un ETF
comprado en Scalable no se vende desde Trade Republic). El mismo día, las compras cuentan antes
que las ventas, porque no se sabe la hora.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import InvestmentOperation


@dataclass(frozen=True)
class Shortfall:
    """Primera fecha en la que se habría vendido de más, y cuántas participaciones quedarían."""

    date: date
    shares: Decimal


def _timeline(db: Session, account_id: int, product_id: int):
    op = InvestmentOperation
    return db.execute(
        select(op.date, op.kind, op.shares)
        .where(
            op.account_id == account_id,
            op.product_id == product_id,
            op.kind.in_(("buy", "sell")),
        )
        .order_by(op.date, case((op.kind == "buy", 0), else_=1), op.id)
    ).all()


def first_shortfall(db: Session, account_id: int, product_id: int) -> Shortfall | None:
    running = Decimal(0)
    for day, kind, shares in _timeline(db, account_id, product_id):
        running += shares if kind == "buy" else -shares
        if running < 0:
            return Shortfall(day, running)
    return None


def shares_held(db: Session, account_id: int, product_id: int, on: date | None = None) -> Decimal:
    """Participaciones al final del día `on` (o hoy, con todas las operaciones)."""
    running = Decimal(0)
    for day, kind, shares in _timeline(db, account_id, product_id):
        if on is not None and day > on:
            break
        running += shares if kind == "buy" else -shares
    return running
