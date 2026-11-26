from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Import(Base):
    """Una importación de un extracto (Fase 5), para poder deshacerla entera.

    Solo se guarda si entró algún movimiento nuevo. No se guarda el nombre del archivo: el de
    Wise lleva el número del extracto (DISENO 8.3, mínimo de datos). El usuario se obtiene por
    la cuenta. Los movimientos nuevos llevan `transactions.import_id`.
    """

    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Fechas del primer y del último movimiento nuevo (para reconocer la importación)
    first_date: Mapped[date | None] = mapped_column(Date)
    last_date: Mapped[date | None] = mapped_column(Date)
    new_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Saldo de referencia de la cuenta antes de importar y el que puso esta importación: al
    # deshacerla se vuelve al de antes si nadie lo ha cambiado después
    previous_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    previous_balance_date: Mapped[date | None] = mapped_column(Date)
    set_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    set_balance_date: Mapped[date | None] = mapped_column(Date)
