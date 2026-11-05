from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BenchmarkPrice(Base):
    """Cierre diario de un índice de referencia (comparativa «¿Y si todo fuera a un indexado?»).

    Son datos públicos de mercado (no de ningún usuario): se guardan una vez para todos, como
    los tipos de cambio. `currency` va ya en la unidad principal (GBp → GBP).
    """

    __tablename__ = "benchmark_prices"
    __table_args__ = (CheckConstraint("price > 0", name="price"),)

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(12))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
