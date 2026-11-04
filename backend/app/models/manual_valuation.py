from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ManualValuation(Base):
    """Valor anotado a mano de un producto sin precio en internet (plan de pensiones, depósito)."""

    __tablename__ = "manual_valuations"
    __table_args__ = (
        UniqueConstraint("product_id", "date"),
        CheckConstraint("value_eur >= 0", name="value_eur"),
        CheckConstraint("contributed_eur IS NULL OR contributed_eur >= 0", name="contributed_eur"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    value_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    contributed_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
