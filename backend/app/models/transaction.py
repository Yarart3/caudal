from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Transaction(Base):
    """Movimiento. Negativo = gasto, positivo = ingreso. El usuario se obtiene por la cuenta."""

    __tablename__ = "transactions"
    __table_args__ = (
        # Anti-duplicados al importar. Los movimientos a mano no llevan huella (NULL no choca).
        UniqueConstraint("account_id", "fingerprint"),
        CheckConstraint("category_status IN ('auto', 'manual', 'review')", name="category_status"),
        Index("ix_transactions_account_id_date", "account_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    category_status: Mapped[str] = mapped_column(
        String(10), default="review", server_default="review"
    )
    is_internal_transfer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
