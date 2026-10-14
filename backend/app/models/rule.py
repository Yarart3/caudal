from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Rule(Base):
    """Regla de categorización: si el concepto contiene `pattern`, va a `category_id`."""

    __tablename__ = "rules"
    __table_args__ = (CheckConstraint("created_by IN ('system', 'user')", name="created_by"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pattern: Mapped[str] = mapped_column(String(120))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    created_by: Mapped[str] = mapped_column(String(10), default="user", server_default="user")
