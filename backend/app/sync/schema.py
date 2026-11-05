"""Revisiones de Alembic que conoce el código de este equipo."""

from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

# backend/alembic.ini (en el contenedor, /app/alembic.ini)
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@lru_cache
def _script() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))


def known_revisions() -> set[str]:
    return {rev.revision for rev in _script().walk_revisions()}


def head_revision() -> str:
    head = _script().get_current_head()
    if head is None:
        raise RuntimeError("No hay migraciones de Alembic")
    return head
