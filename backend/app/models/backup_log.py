from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BackupLog(Base):
    """Registro de backups (Fase 1d). Es global: el backup incluye la BD entera."""

    __tablename__ = "backup_log"
    __table_args__ = (
        CheckConstraint("destination IN ('usb', 'onedrive')", name="destination"),
        CheckConstraint("result IN ('ok', 'error')", name="result"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    destination: Mapped[str] = mapped_column(String(10))
    result: Mapped[str] = mapped_column(String(10))
    message: Mapped[str | None] = mapped_column(Text)
