from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

PRODUCT_KINDS = ("etf", "stock", "fund", "crypto", "pension", "commodity", "other")
PRICE_SOURCES = ("yahoo", "morningstar", "coingecko", "manual")


class Product(Base):
    """Producto de inversión de un usuario (ETF, acción, fondo, cripto, ETC de oro…).

    Es por usuario: el mismo ISIN en dos brokers es un solo producto y dos grupos de operaciones.
    """

    __tablename__ = "products"
    __table_args__ = (
        # Un ISIN solo una vez por usuario (los productos sin ISIN, como la cripto, no chocan)
        UniqueConstraint("user_id", "isin"),
        CheckConstraint(
            "kind IN ('etf', 'stock', 'fund', 'crypto', 'pension', 'commodity', 'other')",
            name="kind",
        ),
        CheckConstraint(
            "price_source IN ('yahoo', 'morningstar', 'coingecko', 'manual')", name="price_source"
        ),
        CheckConstraint("ter IS NULL OR (ter >= 0 AND ter < 1)", name="ter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    isin: Mapped[str | None] = mapped_column(String(12))
    ticker: Mapped[str | None] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(12))
    currency: Mapped[str] = mapped_column(String(3), default="EUR", server_default="EUR")
    price_source: Mapped[str] = mapped_column(String(12))
    # Identificador en la fuente de precios (ticker de Yahoo con su bolsa, id de Morningstar…)
    source_id: Mapped[str | None] = mapped_column(String(60))
    # Comisión anual como fracción: 0,12 % = 0.00120 (NUMERIC(7,5))
    ter: Mapped[Decimal | None] = mapped_column(Numeric(7, 5))
    long_term: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
