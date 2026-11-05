"""Qué hacer al abrir Caudal, según la versión de este equipo y el candado (DISENO §15).

Cada versión tiene un identificador único y la lista de versiones de las que viene (`lineage`).
Así se sabe si una copia CONTIENE lo que hay en este equipo (se puede restaurar sin perder
nada) o si los dos equipos han cambiado cosas por separado (hay que preguntar).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.sync.lock import SyncLock
from app.sync.state import LocalState


class Action(StrEnum):
    OPEN = "open"  # seguir con lo que hay en este equipo
    RESTORE = "restore"  # la copia del otro equipo es más nueva y contiene la de aquí
    CONFLICT = "conflict"  # los dos equipos tienen cambios: preguntar cuál se queda
    BLOCKED = "blocked"  # Caudal está abierto en el otro equipo
    UPDATE_CODE = "update_code"  # la copia es de un código más nuevo: hay que hacer git pull


@dataclass(frozen=True)
class Decision:
    action: Action
    message: str
    # La última sesión en este equipo no se cerró con «Cerrar Caudal» (para avisar)
    unclean_local: bool = False


def decide(
    local: LocalState,
    lock: SyncLock | None,
    device: str,
    known_revisions: set[str],
    force: bool = False,
) -> Decision:
    unclean = local.session_open
    if lock is None:
        return Decision(Action.OPEN, "Todavía no hay ninguna copia sincronizada", unclean)

    if lock.state == "open" and lock.device != device and not force:
        return Decision(
            Action.BLOCKED,
            f"Caudal está abierto en el {lock.device} desde el "
            f"{lock.at:%d/%m/%Y a las %H:%M}. Ciérralo allí con «Cerrar Caudal».",
        )

    if not lock.version_id:
        # El otro equipo abrió antes de que hubiera ninguna versión: no hay nada que traer
        return Decision(Action.OPEN, "Todavía no hay ninguna versión guardada", unclean)
    if lock.version_id == local.version_id:
        return Decision(Action.OPEN, f"Ya tienes la última versión ({lock.version})", unclean)
    if lock.version_id in local.lineage:
        return Decision(
            Action.OPEN, "Este equipo tiene una versión más nueva que la del candado", unclean
        )

    contains_local = local.is_empty or (
        local.version_id is not None and local.version_id in lock.lineage
    )
    if lock.schema not in known_revisions:
        return Decision(
            Action.UPDATE_CODE,
            f"La copia del {lock.device} es de una versión de Caudal más nueva "
            f"(migración {lock.schema}). Actualiza el código con «git pull» y vuelve a abrir.",
        )
    if contains_local and not local.session_open:
        return Decision(
            Action.RESTORE,
            f"Hay una versión más nueva, la {lock.version}, del {lock.device} "
            f"({lock.at:%d/%m/%Y %H:%M})",
        )
    if local.session_open:
        detail = f"este equipo (versión {local.version}) no se cerró con «Cerrar Caudal»"
    else:
        detail = f"este equipo (versión {local.version}) tiene cambios que el otro no tiene"
    return Decision(
        Action.CONFLICT,
        f"Los dos equipos tienen cambios: el {lock.device} guardó la versión {lock.version} "
        f"({lock.at:%d/%m/%Y %H:%M}) y {detail}",
        unclean,
    )
