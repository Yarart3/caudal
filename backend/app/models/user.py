from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, false, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    display_name: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(7))  # color del avatar, "#0E6B58"
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Desactivado (Fase 4): no sale en «¿Quién entra?» ni puede entrar; sus datos se quedan
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
