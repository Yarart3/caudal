from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

OPERATION_KINDS = ("buy", "sell", "dividend", "fee")


class InvestmentOperation(Base):
    """Operación de inversión. El usuario se obtiene por la cuenta (como en transactions).

    `amount_eur` va siempre en positivo; el sentido lo da `kind`: en una compra es lo que salió
    de la cuenta (comisiones incluidas), en una venta o un dividendo, lo que entró.
    La API (parte 3.3) comprueba que cuenta y producto son del mismo usuario.
    """

    __tablename__ = "investment_operations"
    __table_args__ = (
        UniqueConstraint("account_id", "fingerprint"),
        CheckConstraint("kind IN ('buy', 'sell', 'dividend', 'fee')", name="kind"),
        CheckConstraint("shares >= 0", name="shares"),
        CheckConstraint("kind NOT IN ('buy', 'sell') OR shares > 0", name="shares_buy_sell"),
        CheckConstraint("amount_eur > 0", name="amount_eur"),
        CheckConstraint("fee_eur IS NULL OR fee_eur >= 0", name="fee_eur"),
        Index("ix_investment_operations_account_id_date", "account_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(10))
    shares: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(0), server_default="0")
    amount_eur: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fee_eur: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # Solo las operaciones importadas llevan huella; las hechas a mano no (NULL no choca)
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
