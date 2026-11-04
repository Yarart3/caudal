from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Price(Base):
    """Último precio conocido de un producto en un día (histórico: una fila por día).

    Si se actualiza varias veces el mismo día, se sustituye la fila. `fetched_at` dice cuándo se
    descargó, para avisar de precios desactualizados (DISENO 7.3).
    """

    __tablename__ = "prices"
    __table_args__ = (CheckConstraint("price > 0", name="price"),)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(12))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
