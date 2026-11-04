from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ExchangeRate(Base):
    """Tipo de cambio a euros de un día: 1 unidad de `currency` = `rate` EUR.

    Son datos públicos de mercado (no de ningún usuario): se guardan una vez para todos.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        CheckConstraint("rate > 0", name="rate"),
        CheckConstraint("currency <> 'EUR'", name="currency"),
    )

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    source: Mapped[str] = mapped_column(String(12))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
