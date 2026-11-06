"""Abrir y cerrar Caudal sincronizando con el otro equipo (Fase R, DISENO §15).

- Al ABRIR (antes de arrancar la app): se migra la base, se lee el candado de Google Drive y se
  decide (app/sync/decide.py). Si hay una versión más nueva que contiene la de aquí, se
  restaura sola; si los dos equipos tienen cambios, se pregunta y se guardan las dos en
  `conflictos/`. Al final se marca la sesión como abierta aquí y en el candado.
- Al CERRAR (con la app aún en marcha): versión nueva → backup → candado «cerrado en este
  equipo, versión N», con el nombre, el tamaño y el SHA-256 de la copia de Google Drive.

Todo lo que necesita de fuera (preguntar, escribir, esperar, la hora) llega en `SyncContext`,
para poder probarlo sin terminal.
"""

import re
import shutil
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from app.backup.crypto import BackupDecryptError
from app.backup.restore import CONFLICTS_DIR, restore_backup
from app.backup.service import (
    LABELS,
    TZ,
    BackupBusyError,
    BackupError,
    BackupResult,
    is_available,
    run_backup,
)
from app.config import Settings
from app.sync.decide import Action, decide
from app.sync.lock import (
    FileStatus,
    LastCopy,
    LockError,
    SyncLock,
    last_copy,
    read_lock,
    remote_file_status,
    sha256_file,
    write_lock,
)
from app.sync.schema import ALEMBIC_INI, head_revision, known_revisions
from app.sync.state import LocalState, extend_lineage, read_local_state, write_local_state

# Códigos de salida (los usan los scripts de abrir y cerrar)
OK = 0
ERROR = 1
CANCELLED = 2
BLOCKED = 3
UPDATE_CODE = 4

DEVICE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,19}$")
BUSY_RETRIES = 12  # si hay otra copia en marcha al cerrar: hasta 12 × 5 s
BUSY_WAIT_S = 5.0


def migrate(db_engine: Engine) -> None:
    """alembic upgrade head sobre la base de `db_engine`."""
    config = Config(str(ALEMBIC_INI))
    with db_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def _now() -> datetime:
    return datetime.now(TZ)


@dataclass
class SyncContext:
    settings: Settings
    engine: Engine
    ask: Callable[[str], str]
    out: Callable[[str], None] = print
    sleep: Callable[[float], None] = time.sleep
    now: Callable[[], datetime] = _now
    wait_timeout_s: float = 300.0  # cuánto se espera a que baje la copia del otro equipo
    wait_poll_s: float = 5.0
    migrate: Callable[[Engine], None] = field(default=migrate)

    @property
    def device(self) -> str:
        return self.settings.device_name.strip().lower()

    @property
    def cloud_dir(self) -> Path:
        return self.settings.backup_cloud_dir


def _yes(answer: str) -> bool:
    return answer.strip().lower() in ("s", "si", "sí")


def _check_device(ctx: SyncContext) -> bool:
    if DEVICE_RE.match(ctx.device):
        return True
    if not ctx.device:
        ctx.out("ERROR: falta DEVICE_NAME en el .env (por ejemplo, DEVICE_NAME=mac o pc)")
    else:
        ctx.out(
            f"ERROR: DEVICE_NAME «{ctx.settings.device_name}» no vale: solo minúsculas, "
            "números y guiones (máx. 20)"
        )
    return False


def _password(ctx: SyncContext) -> str:
    secret = ctx.settings.backup_password
    return secret.get_secret_value() if secret else ""


# --------------------------------------------------------------------------- abrir


def open_sync(ctx: SyncContext, force: bool = False) -> int:
    if not _check_device(ctx):
        return ERROR
    ctx.migrate(ctx.engine)
    local = read_local_state(ctx.engine)

    if not is_available(ctx.cloud_dir):
        ctx.out("No se ve la carpeta de Google Drive: no se puede saber si el otro equipo")
        ctx.out("tiene algo más nuevo.")
        if not _yes(ctx.ask("¿Abrir con lo que hay en este equipo? (s/N): ")):
            return CANCELLED
        _mark_open(ctx, local, None, write=False)
        return OK

    try:
        lock = read_lock(ctx.cloud_dir)
    except LockError as error:
        ctx.out(str(error))
        if not _yes(ctx.ask("¿Abrir con lo que hay en este equipo? (s/N): ")):
            return CANCELLED
        _mark_open(ctx, local, None)
        return OK

    decision = decide(local, lock, ctx.device, known_revisions(), force=force)
    if decision.action is Action.BLOCKED:
        ctx.out(decision.message)
        ctx.out("Si allí se apagó sin cerrar y no hiciste cambios, puedes abrir igualmente.")
        if not _yes(ctx.ask("¿Abrir igualmente aquí? (s/N): ")):
            return BLOCKED
        decision = decide(local, lock, ctx.device, known_revisions(), force=True)

    if decision.action is Action.UPDATE_CODE:
        ctx.out(decision.message)
        return UPDATE_CODE

    if decision.action is Action.OPEN or lock is None:
        if decision.unclean_local:
            ctx.out("Aviso: la última vez Caudal no se cerró con «Cerrar Caudal» en este equipo.")
            ctx.out("Lo que hiciste sigue aquí y se guardará al cerrar.")
        _mark_open(ctx, local, lock)
        ctx.out(decision.message)
        return OK

    ctx.out(decision.message)
    ready = _wait_for_file(ctx, lock)
    if decision.action is Action.RESTORE:
        if not ready:
            return _open_local_without_remote(ctx, local, lock)
        return _restore_remote(ctx, lock)
    return _resolve_conflict(ctx, local, lock, ready)


def _wait_for_file(ctx: SyncContext, lock: SyncLock) -> bool:
    """Espera a que baje de Google Drive la copia que dice el candado. True si ha llegado."""
    status = remote_file_status(ctx.cloud_dir, lock)
    if status is FileStatus.READY:
        return True
    ctx.out(f"Esperando a que baje de Google Drive la copia del {lock.device}…")
    waited = 0.0
    while waited < ctx.wait_timeout_s:
        ctx.sleep(ctx.wait_poll_s)
        waited += ctx.wait_poll_s
        status = remote_file_status(ctx.cloud_dir, lock)
        if status is FileStatus.READY:
            ctx.out("  Ha llegado.")
            return True
    ctx.out(
        f"La copia del {lock.device} ({lock.file or 'sin nombre'}) no ha llegado en "
        f"{int(ctx.wait_timeout_s // 60)} min. Comprueba que Google Drive está sincronizando."
    )
    return False


def _open_local_without_remote(ctx: SyncContext, local: LocalState, lock: SyncLock) -> int:
    ctx.out("Puedes esperar y volver a abrir, o abrir ahora con lo de este equipo (la versión")
    ctx.out(f"del {lock.device} no se pierde: al volver a abrir se te preguntará cuál quedarte).")
    if not _yes(ctx.ask("¿Abrir ahora con lo de este equipo? (s/N): ")):
        return CANCELLED
    # No se escribe el candado: sigue diciendo lo del otro equipo y así no se pierde
    _mark_open(ctx, local, None, write=False)
    return OK


def _restore_remote(ctx: SyncContext, lock: SyncLock, source: Path | None = None) -> int:
    path = source or ctx.cloud_dir / str(lock.file)
    ctx.out(f"Restaurando la versión {lock.version} del {lock.device}…")
    ctx.engine.dispose()  # cierra las conexiones antes de borrar la base
    try:
        restore_backup(path, _password(ctx), ctx.settings, ctx.settings.postgres_db)
    except BackupDecryptError:
        ctx.out(
            f"ERROR: la BACKUP_PASSWORD de este equipo no abre la copia del {lock.device}. "
            "Tiene que ser la misma en los dos .env. No se ha tocado nada."
        )
        return ERROR
    except BackupError as error:
        ctx.out(f"ERROR: {error}")
        ctx.out("La base puede haber quedado vacía: usa «Restaurar backup».")
        return ERROR
    ctx.engine.dispose()
    ctx.migrate(ctx.engine)  # si la copia es de un código anterior
    _mark_open(ctx, read_local_state(ctx.engine), lock)
    ctx.out(f"Listo: tienes la versión {lock.version} del {lock.device}.")
    return OK


def _keep_copy(ctx: SyncContext, source: Path, device: str, version: int) -> Path | None:
    """Copia un backup a `conflictos/` como «<equipo>-v<versión>_<nombre>». None si no se puede."""
    folder = ctx.cloud_dir / CONFLICTS_DIR
    target = folder / f"{device}-v{version}_{source.name}"
    try:
        folder.mkdir(exist_ok=True)
        if not target.exists():
            shutil.copy2(source, target)
    except OSError as error:
        ctx.out(f"  No se ha podido guardar {source.name} en {CONFLICTS_DIR}/: {error}")
        return None
    return target


def _resolve_conflict(ctx: SyncContext, local: LocalState, lock: SyncLock, ready: bool) -> int:
    ctx.out("")
    ctx.out("Elige con qué versión seguir. La otra se guarda en Google Drive, en conflictos/:")
    if ready:
        ctx.out(f"  1) La del {lock.device}: versión {lock.version}, del {lock.at:%d/%m/%Y %H:%M}")
    else:
        ctx.out(f"  1) (no disponible: la copia del {lock.device} no ha llegado)")
    state = "sin cerrar bien" if local.session_open else "con cambios propios"
    ctx.out(f"  2) La de este equipo ({ctx.device}): versión {local.version}, {state}")
    choice = ctx.ask("Escribe 1 o 2 (Enter = no abrir): ").strip()

    if choice == "1" and ready:
        remote = _keep_copy(ctx, ctx.cloud_dir / str(lock.file), lock.device, lock.version)
        if remote is None:
            return ERROR
        ctx.out("Guardando antes una copia de lo de este equipo…")
        mine = _backup(ctx, "pre_restore")
        saved = (
            mine is not None
            and _keep_copy(ctx, _result_path(ctx, mine), ctx.device, local.version) is not None
        )
        if not saved and not _yes(
            ctx.ask("No se ha podido guardar lo de este equipo. ¿Seguir igualmente? (s/N): ")
        ):
            return CANCELLED
        # Se restaura desde la copia de conflictos/: aunque otra copia pisara la original
        return _restore_remote(ctx, lock, source=remote)

    if choice == "2":
        remote_file = ctx.cloud_dir / str(lock.file)
        if ready and _keep_copy(ctx, remote_file, lock.device, lock.version) is None:
            return ERROR
        # Si su copia ha llegado (y está guardada), la versión del otro equipo pasa a ser «de las
        # que viene esta»: al cerrar aquí, el otro verá que la nueva la contiene y la restaurará
        # sin volver a preguntar. Si no ha llegado, se volverá a preguntar más adelante.
        chosen = local
        if ready:
            ids = [lock.version_id] + ([local.version_id] if local.version_id else [])
            chosen = replace(local, lineage=extend_lineage(local.lineage, *ids))
        _mark_open(ctx, chosen, lock if ready else None, write=ready)
        ctx.out("Sigues con la versión de este equipo. Al cerrar, será la que vea el otro.")
        return OK

    ctx.out("No se ha abierto nada.")
    return CANCELLED


def _mark_open(
    ctx: SyncContext, local: LocalState, previous: SyncLock | None, write: bool = True
) -> None:
    """Marca la sesión como abierta aquí y, si se puede, en el candado de Google Drive."""
    opened = replace(local, session_open=True, device=ctx.device)
    write_local_state(opened, ctx.engine)
    if not write:
        return
    # La copia del candado anterior sigue valiendo si es de esta misma versión
    base = previous if previous and previous.version_id == (local.version_id or "") else None
    copy = last_copy(base)
    lock = SyncLock(
        state="open",
        device=ctx.device,
        version=local.version,
        version_id=local.version_id or "",
        lineage=local.lineage,
        schema=head_revision(),
        at=ctx.now(),
        file=base.file if base else None,
        size=base.size if base else None,
        sha256=base.sha256 if base else None,
        closed_by=copy.device if copy else None,
        closed_at=copy.at if copy else None,
    )
    try:
        write_lock(ctx.cloud_dir, lock)
    except OSError as error:
        ctx.out(f"Aviso: no se ha podido escribir el candado en Google Drive ({error}).")
        ctx.out("El otro equipo no sabrá que Caudal está abierto aquí.")


# --------------------------------------------------------------------------- cerrar


def _backup(ctx: SyncContext, trigger: str) -> BackupResult | None:
    """Backup con reintentos si hay otro en marcha. None si no se ha podido hacer."""
    for attempt in range(BUSY_RETRIES + 1):
        try:
            result = run_backup(trigger, ctx.settings, ctx.engine)
        except BackupBusyError:
            if attempt == BUSY_RETRIES:
                ctx.out("ERROR: hay otra copia en marcha que no termina")
                return None
            ctx.out("  Esperando a que termine la otra copia…")
            ctx.sleep(BUSY_WAIT_S)
            continue
        except BackupError as error:
            ctx.out(f"ERROR: {error}")
            return None
        for r in result.results:
            ctx.out(f"  {LABELS[r.destination]:12} {'✓' if r.ok else '✗'}  {r.message}")
        return result if result.ok else None
    return None


def _result_path(ctx: SyncContext, result: BackupResult) -> Path:
    """Dónde ha quedado la copia: en Google Drive si ha llegado, si no en el pendrive."""
    ok = {r.destination for r in result.results if r.ok}
    folder = ctx.cloud_dir if "cloud" in ok else ctx.settings.backup_usb_dir
    return folder / result.filename


def close_sync(ctx: SyncContext) -> int:
    if not _check_device(ctx):
        return ERROR
    try:
        lock = read_lock(ctx.cloud_dir) if is_available(ctx.cloud_dir) else None
    except LockError as error:
        ctx.out(f"Aviso: {error}. Se escribirá uno nuevo.")
        lock = None

    local = read_local_state(ctx.engine)
    new_id = str(uuid.uuid4())
    closed = replace(
        local,
        version=max(local.version, lock.version if lock else 0) + 1,
        version_id=new_id,
        lineage=extend_lineage(local.lineage, new_id),
        session_open=False,
        device=ctx.device,
    )
    # La fila se escribe ANTES del volcado: así la copia lleva su propia versión
    write_local_state(closed, ctx.engine)
    result = _backup(ctx, "close")
    if result is None:
        write_local_state(local, ctx.engine)  # sin copia, nada ha cambiado
        ctx.out("ERROR: la copia final no se ha guardado en ningún sitio")
        return ERROR

    cloud_ok = any(r.destination == "cloud" and r.ok for r in result.results)
    if not cloud_ok:
        ctx.out("La copia no ha llegado a Google Drive: el otro equipo no verá esta versión.")
        ctx.out("Se ha guardado en el pendrive. Al volver a abrir aquí, todo seguirá igual.")
        return ERROR

    if lock is not None and lock.state == "open" and lock.device != ctx.device:
        # Se abrió a la fuerza en el otro equipo mientras estaba abierto aquí: no se pisa su
        # candado. Al abrir después, se preguntará con qué versión seguir.
        ctx.out(f"Aviso: Caudal sigue abierto en el {lock.device} (se abrió a la fuerza).")
        ctx.out("Tu versión está guardada; la próxima vez se te preguntará cuál quedarte.")
        return OK

    path = ctx.cloud_dir / result.filename
    try:
        write_lock(
            ctx.cloud_dir,
            SyncLock(
                state="closed",
                device=ctx.device,
                version=closed.version,
                version_id=new_id,
                lineage=closed.lineage,
                schema=head_revision(),
                at=ctx.now(),
                file=result.filename,
                size=path.stat().st_size,
                sha256=sha256_file(path),
            ),
        )
    except OSError as error:
        ctx.out(f"ERROR: la copia está hecha, pero no se ha podido escribir el candado: {error}")
        return ERROR
    ctx.out(f"Versión {closed.version} guardada en Google Drive.")
    return OK


# --------------------------------------------------------------------------- estado


def status_lines(ctx: SyncContext) -> list[str]:
    local = read_local_state(ctx.engine)
    lines = [
        f"Este equipo ({ctx.device or 'sin DEVICE_NAME'}): versión {local.version}"
        + (", abierto" if local.session_open else ", cerrado")
    ]
    if not is_available(ctx.cloud_dir):
        return [*lines, "Google Drive: carpeta no disponible"]
    try:
        lock = read_lock(ctx.cloud_dir)
    except LockError as error:
        return [*lines, f"Google Drive: {error}"]
    if lock is None:
        return [*lines, "Google Drive: todavía no hay ninguna versión sincronizada"]
    what = "abierto en el" if lock.state == "open" else "cerrado en el"
    return [
        *lines,
        f"Google Drive: {what} {lock.device}, versión {lock.version}, "
        f"{lock.at.astimezone(TZ):%d/%m/%Y %H:%M}",
    ]


# --------------------------------------------------------------------------- restaurar a mano


def adopt_restored(ctx: SyncContext) -> int:
    """Tras «Restaurar backup»: lo restaurado pasa a ser la versión con la que se sigue.

    Sin esto, al abrir se vería como una versión antigua y se cambiaría sola por la última del
    candado, deshaciendo la restauración. Se le da una versión nueva que «contiene» todas las
    del candado; al cerrar, el otro equipo la recibirá como cualquier otra.
    """
    if not _check_device(ctx):
        return ERROR
    ctx.migrate(ctx.engine)  # el backup puede ser de antes de la migración 0008
    lock = None
    if is_available(ctx.cloud_dir):
        try:
            lock = read_lock(ctx.cloud_dir)
        except LockError as error:
            ctx.out(f"Aviso: {error}")
    local = read_local_state(ctx.engine)
    new_id = str(uuid.uuid4())
    remote = lock.lineage if lock else ()
    adopted = replace(
        local,
        version=max(local.version, lock.version if lock else 0),
        version_id=new_id,
        lineage=extend_lineage(local.lineage, *remote, new_id),
        session_open=True,  # todavía no está en ninguna copia: al cerrar se guardará
        device=ctx.device,
    )
    write_local_state(adopted, ctx.engine)
    ctx.out("Lo restaurado es ahora la versión de Caudal; al cerrar, la recibirá el otro equipo.")
    return OK


# --------------------------------------------------------------------------- «Última copia»


@dataclass(frozen=True)
class SyncInfo:
    this_device: str
    local_version: int
    cloud_available: bool
    last_copy: LastCopy | None


def sync_info(settings: Settings, db_engine: Engine) -> SyncInfo:
    """Lo que enseña la pantalla de inicio: «Última copia: equipo, fecha y hora»."""
    local = read_local_state(db_engine)
    device = settings.device_name.strip().lower()
    cloud = settings.backup_cloud_dir
    if not is_available(cloud):
        return SyncInfo(device, local.version, False, None)
    try:
        lock = read_lock(cloud)
    except LockError:
        lock = None
    return SyncInfo(device, local.version, True, last_copy(lock))
