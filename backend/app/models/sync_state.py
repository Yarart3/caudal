from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SyncState(Base):
    """Versión de los datos que tiene ESTA base (Fase R, DISENO §15). Una sola fila (id = 1).

    Viaja dentro de los backups: al restaurar la copia del otro equipo, esta fila pasa a ser la
    suya y así se sabe de qué versión vienen los datos.
    """

    __tablename__ = "sync_state"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Número de versión para enseñarlo («versión 12») y su identificador único (uuid4)
    version: Mapped[int] = mapped_column(default=0, server_default="0")
    version_id: Mapped[str | None] = mapped_column(String(36))
    # Identificadores de las versiones de las que vienen estos datos, la última al final
    lineage: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    # True mientras Caudal está abierto en este equipo: si sigue en True al abrir, la última
    # sesión no se cerró con «Cerrar Caudal» y puede haber cambios que no están en ninguna copia
    session_open: Mapped[bool] = mapped_column(default=False, server_default="false")
    device: Mapped[str | None] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
