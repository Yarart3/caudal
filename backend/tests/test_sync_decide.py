"""Qué hace Caudal al abrir, caso por caso (Fase R, DISENO §15)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.sync.decide import Action, decide
from app.sync.lock import SyncLock
from app.sync.state import LocalState

TZ = ZoneInfo("Europe/Madrid")
REVS = {"0007", "0008"}


def lock(
    version_id: str,
    lineage: tuple[str, ...],
    state: str = "closed",
    device: str = "pc",
    schema: str = "0008",
) -> SyncLock:
    return SyncLock(
        state=state,
        device=device,
        version=len(lineage),
        version_id=version_id,
        lineage=lineage,
        schema=schema,
        at=datetime(2026, 11, 5, 22, 30, tzinfo=TZ),
        file="caudal_2026-11-05_2230.dump.enc",
        size=10,
        sha256="0" * 64,
    )


def local(version_id: str | None, lineage: tuple[str, ...], open_: bool = False) -> LocalState:
    return LocalState(
        version=len(lineage),
        version_id=version_id,
        lineage=lineage,
        session_open=open_,
        device="mac",
        has_data=version_id is not None,
    )


def test_sin_candado_abre_lo_local() -> None:
    d = decide(local("a", ("a",)), None, "mac", REVS)
    assert d.action is Action.OPEN


def test_candado_sin_version_no_trae_nada() -> None:
    # El otro equipo abrió y se cerró sin llegar a guardar ninguna versión
    d = decide(LocalState(), lock("", (), device="mac"), "pc", REVS)
    assert d.action is Action.OPEN


def test_misma_version_abre() -> None:
    d = decide(local("b", ("a", "b")), lock("b", ("a", "b")), "mac", REVS)
    assert d.action is Action.OPEN
    assert not d.unclean_local


def test_misma_version_sin_cerrar_bien_abre_y_avisa() -> None:
    # La última sesión aquí se cortó, pero nadie más ha cambiado nada: se sigue y se avisa
    d = decide(local("b", ("a", "b"), open_=True), lock("b", ("a", "b")), "mac", REVS)
    assert d.action is Action.OPEN
    assert d.unclean_local


def test_version_mas_nueva_que_contiene_la_local_se_restaura() -> None:
    d = decide(local("b", ("a", "b")), lock("d", ("a", "b", "c", "d")), "mac", REVS)
    assert d.action is Action.RESTORE


def test_base_vacia_restaura_sin_preguntar() -> None:
    # Primer arranque en el otro equipo: base recién creada, sin usuarios
    empty = LocalState()
    d = decide(empty, lock("d", ("a", "b", "c", "d")), "mac", REVS)
    assert d.action is Action.RESTORE


def test_base_con_datos_pero_sin_version_pregunta() -> None:
    # Se pasó el asistente en este equipo antes de sincronizar: no se pisa sin preguntar
    with_data = LocalState(has_data=True, session_open=True)
    d = decide(with_data, lock("d", ("a", "d")), "mac", REVS)
    assert d.action is Action.CONFLICT


def test_version_mas_nueva_pero_aqui_hay_cambios_sin_copia() -> None:
    d = decide(local("b", ("a", "b"), open_=True), lock("c", ("a", "b", "c")), "mac", REVS)
    assert d.action is Action.CONFLICT
    assert d.unclean_local


def test_versiones_que_se_han_separado() -> None:
    # Los dos partieron de "a" y cada uno guardó la suya (p. ej., abriendo a la fuerza)
    d = decide(local("m", ("a", "m")), lock("p", ("a", "p")), "mac", REVS)
    assert d.action is Action.CONFLICT
    assert not d.unclean_local


def test_este_equipo_va_por_delante() -> None:
    # El candado se quedó atrás (no se pudo escribir al cerrar): lo de aquí ya lo contiene
    d = decide(local("c", ("a", "b", "c")), lock("b", ("a", "b")), "mac", REVS)
    assert d.action is Action.OPEN


def test_abierto_en_el_otro_equipo_no_arranca() -> None:
    d = decide(local("b", ("a", "b")), lock("b", ("a", "b"), state="open"), "mac", REVS)
    assert d.action is Action.BLOCKED
    assert "pc" in d.message


def test_abierto_en_el_otro_equipo_forzando_sigue_las_reglas() -> None:
    same = decide(
        local("b", ("a", "b")), lock("b", ("a", "b"), state="open"), "mac", REVS, force=True
    )
    assert same.action is Action.OPEN
    newer = decide(local("a", ("a",)), lock("b", ("a", "b"), state="open"), "mac", REVS, force=True)
    assert newer.action is Action.RESTORE


def test_abierto_en_este_mismo_equipo_no_bloquea() -> None:
    # Se apagó el Mac sin «Cerrar Caudal»: el candado dice «abierto en el mac»
    d = decide(
        local("b", ("a", "b"), open_=True),
        lock("b", ("a", "b"), state="open", device="mac"),
        "mac",
        REVS,
    )
    assert d.action is Action.OPEN
    assert d.unclean_local


@pytest.mark.parametrize("open_", [False, True])
def test_copia_de_un_codigo_mas_nuevo_pide_git_pull(open_: bool) -> None:
    d = decide(
        local("b", ("a", "b"), open_=open_), lock("c", ("a", "b", "c"), schema="0009"), "mac", REVS
    )
    assert d.action is Action.UPDATE_CODE
    assert "git pull" in d.message


def test_esquema_desconocido_no_importa_si_no_hay_que_restaurar() -> None:
    d = decide(local("c", ("a", "b", "c")), lock("c", ("a", "b", "c"), schema="0009"), "mac", REVS)
    assert d.action is Action.OPEN
