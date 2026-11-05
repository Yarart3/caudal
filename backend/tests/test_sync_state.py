"""Versión de los datos de esta base (tabla sync_state, Fase R)."""

from alembic import command
from alembic.config import Config

from app.sync.schema import head_revision, known_revisions
from app.sync.state import (
    LINEAGE_MAX,
    LocalState,
    extend_lineage,
    read_local_state,
    write_local_state,
)


def test_sin_fila_ni_datos_es_una_base_vacia() -> None:
    state = read_local_state()
    assert state == LocalState()
    assert state.is_empty


def test_sin_fila_con_datos_se_trata_como_cambios_sin_copia(make_user) -> None:
    make_user("gerard")
    state = read_local_state()
    assert state.has_data
    assert state.session_open
    assert not state.is_empty


def test_ida_y_vuelta() -> None:
    state = LocalState(
        version=4, version_id="id-4", lineage=("id-3", "id-4"), session_open=True, device="mac"
    )
    write_local_state(state)
    assert read_local_state() == state
    # Escribir otra vez actualiza la misma fila
    write_local_state(LocalState(version=5, version_id="id-5", lineage=("id-5",), device="pc"))
    assert read_local_state().version == 5


def test_extend_lineage_sin_repetir_y_con_limite() -> None:
    assert extend_lineage(("a", "b"), "c") == ("a", "b", "c")
    assert extend_lineage(("a", "b"), "a", "c") == ("b", "a", "c")
    long = tuple(str(i) for i in range(LINEAGE_MAX))
    result = extend_lineage(long, "nuevo")
    assert len(result) == LINEAGE_MAX
    assert result[-1] == "nuevo"
    assert result[0] == "1"


def test_revisiones_conocidas() -> None:
    assert head_revision() == "0008"
    assert {"0001", "0007", "0008"} <= known_revisions()


def test_migracion_marca_como_sin_copia_una_base_con_datos(make_user) -> None:
    make_user("gerard")
    config = Config("alembic.ini")
    command.downgrade(config, "0007")
    try:
        command.upgrade(config, "head")
        state = read_local_state()
        assert state.session_open
        assert state.version_id is None
    finally:
        command.upgrade(config, "head")


def test_migracion_en_base_vacia_no_marca_nada() -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "0007")
    try:
        command.upgrade(config, "head")
        state = read_local_state()
        assert not state.session_open
        assert state.is_empty
    finally:
        command.upgrade(config, "head")
