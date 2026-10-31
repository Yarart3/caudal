from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("kind IN ('expense', 'income')", name="kind"),
        CheckConstraint(
            "monthly_budget IS NULL OR (monthly_budget > 0 AND kind = 'expense')",
            name="monthly_budget",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(10))
    color: Mapped[str | None] = mapped_column(String(7))
    # Presupuesto mensual fijo (Fase 2). Vacío = sin presupuesto. Solo en categorías de gasto.
    monthly_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
