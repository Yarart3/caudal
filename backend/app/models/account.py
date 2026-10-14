from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ACCOUNT_KINDS = ("spending", "investment", "mixed")
LIQUIDITY_TYPES = ("cash", "money_market")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("kind IN ('spending', 'investment', 'mixed')", name="kind"),
        CheckConstraint("liquidity_type IN ('cash', 'money_market')", name="liquidity_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))
    # Banco del extracto ("imagin", "wise"...). Vacío = cuenta a mano. Se usa desde la Fase 1b.
    import_format: Mapped[str | None] = mapped_column(String(40))
    liquidity_type: Mapped[str] = mapped_column(String(20), default="cash", server_default="cash")
    reference_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    reference_balance_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
