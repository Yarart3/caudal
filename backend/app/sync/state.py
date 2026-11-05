"""Versión de los datos de ESTA base (tabla sync_state)."""

from dataclasses import dataclass

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import engine as default_engine
from app.models import SyncState, User

LINEAGE_MAX = 200  # versiones que se recuerdan: de sobra para saber si una viene de otra


@dataclass(frozen=True)
class LocalState:
    version: int = 0
    version_id: str | None = None
    lineage: tuple[str, ...] = ()
    session_open: bool = False
    device: str | None = None
    has_data: bool = False  # hay usuarios (se ha pasado el asistente de primer arranque)

    @property
    def is_empty(self) -> bool:
        """Base recién creada: nunca ha tenido datos ni ha recibido ninguna copia."""
        return self.version_id is None and not self.has_data


def extend_lineage(lineage: tuple[str, ...], *ids: str) -> tuple[str, ...]:
    """Añade versiones al final (sin repetir) y se queda con las LINEAGE_MAX últimas."""
    result = [i for i in lineage if i not in ids] + list(dict.fromkeys(ids))
    return tuple(result[-LINEAGE_MAX:])


def read_local_state(db_engine: Engine | None = None) -> LocalState:
    with Session(db_engine or default_engine) as db:
        has_data = db.scalar(select(User.id).limit(1)) is not None
        row = db.get(SyncState, 1)
        if row is None:
            # Sin fila (no debería pasar fuera de los tests): si hay datos, no se sabe si están
            # en alguna copia, así que se tratan como cambios sin guardar
            return LocalState(session_open=has_data, has_data=has_data)
        return LocalState(
            version=row.version,
            version_id=row.version_id,
            lineage=tuple(row.lineage or ()),
            session_open=row.session_open,
            device=row.device,
            has_data=has_data,
        )


def write_local_state(state: LocalState, db_engine: Engine | None = None) -> None:
    values = {
        "version": state.version,
        "version_id": state.version_id,
        "lineage": list(state.lineage),
        "session_open": state.session_open,
        "device": state.device,
    }
    stmt = (
        insert(SyncState)
        .values(id=1, **values)
        .on_conflict_do_update(index_elements=[SyncState.id], set_=values)
    )
    with Session(db_engine or default_engine) as db:
        db.execute(stmt)
        db.commit()
