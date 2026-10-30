"""Hacer un backup: pg_dump → cifrado → pendrive y OneDrive → rotación → backup_log.

- El volcado se hace UNA vez y el mismo archivo cifrado se escribe en cada destino.
- Un destino solo se usa si contiene el marcador `.caudal-backups`, que crean los scripts de
  arranque fuera del contenedor. Así, si el pendrive no está (o se ha desconectado con la app
  abierta y Docker ve una carpeta vacía), no se escribe en una carpeta que no es la buena.
- Si un destino falla, se escribe igualmente en el otro (DISENO §12).
- Un bloqueo de PostgreSQL (advisory lock) evita dos backups a la vez, aunque uno lo lance la
  app y otro el script de cierre desde otro proceso.
"""

import logging
import os
import re
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.backup.crypto import encrypt
from app.config import Settings, get_settings
from app.db import engine as default_engine
from app.models import BackupLog

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Madrid")
MARKER = ".caudal-backups"
FILENAME_RE = re.compile(r"^caudal_\d{4}-\d{2}-\d{2}_\d{4}\.dump\.enc$")
PARTIAL_SUFFIX = ".partial"
LOCK_KEY = 7_141_521_001  # número cualquiera, fijo: identifica el bloqueo "backup de Caudal"
DUMP_TIMEOUT_S = 600

DESTINATIONS = ("usb", "onedrive")
LABELS = {"usb": "Pendrive", "onedrive": "OneDrive"}
NOT_AVAILABLE = {
    "usb": "Pendrive no conectado",
    "onedrive": "Carpeta de OneDrive no disponible",
}
TRIGGERS = {
    "import": "tras importar",
    "interval": "periódica",
    "close": "al cerrar",
    "startup": "al arrancar",
    "manual": "manual",
    "pre_restore": "antes de restaurar",
}


class BackupError(Exception):
    """No se ha podido hacer el backup en ningún destino. Mensaje en castellano."""


class BackupBusyError(BackupError):
    """Ya hay otro backup en marcha."""


@dataclass
class DestinationResult:
    destination: str
    ok: bool
    message: str


@dataclass
class BackupResult:
    filename: str
    created_at: datetime
    results: list[DestinationResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True si la copia se ha guardado en al menos un destino."""
        return any(r.ok for r in self.results)


def destination_dirs(settings: Settings) -> dict[str, Path]:
    return {"usb": settings.backup_usb_dir, "onedrive": settings.backup_onedrive_dir}


def is_available(directory: Path) -> bool:
    try:
        return (directory / MARKER).is_file()
    except OSError:
        return False


def backup_filename(moment: datetime) -> str:
    return moment.strftime("caudal_%Y-%m-%d_%H%M.dump.enc")


def list_backup_files(directory: Path) -> list[Path]:
    """Backups de Caudal de una carpeta, del más antiguo al más reciente (por el nombre)."""
    return sorted(p for p in directory.iterdir() if p.is_file() and FILENAME_RE.match(p.name))


def rotate(directory: Path, keep: int) -> list[Path]:
    """Borra los backups más antiguos y deja los `keep` últimos. Solo toca archivos de Caudal."""
    files = list_backup_files(directory)
    removed = files[:-keep] if keep > 0 else []
    for path in removed:
        path.unlink(missing_ok=True)
    return removed


def write_atomic(directory: Path, filename: str, blob: bytes) -> Path:
    """Escribe en un archivo temporal y lo renombra: nunca queda un backup a medias con su
    nombre definitivo (importante en OneDrive, que sube lo que ve)."""
    final = directory / filename
    tmp = directory / f".{filename}{PARTIAL_SUFFIX}"
    try:
        with tmp.open("wb") as fh:
            fh.write(blob)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
    finally:
        tmp.unlink(missing_ok=True)
    return final


def pg_env(settings: Settings) -> dict[str, str]:
    """Entorno para pg_dump / pg_restore: la contraseña va por variable, no en la línea de
    órdenes (que se ve con `ps`)."""
    return {**os.environ, "PGPASSWORD": settings.postgres_password}


def pg_connection_args(settings: Settings, dbname: str | None = None) -> list[str]:
    return [
        "--host",
        settings.database_host,
        "--port",
        str(settings.database_port),
        "--username",
        settings.postgres_user,
        "--dbname",
        dbname or settings.postgres_db,
    ]


def find_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise BackupError(f"No se encuentra {name} en la imagen de la app")
    return path


def dump_database(settings: Settings) -> bytes:
    """pg_dump en formato custom (-Fc): comprimido y el que entiende pg_restore."""
    cmd = [find_tool("pg_dump"), "--format=custom", *pg_connection_args(settings)]
    try:
        proc = subprocess.run(  # noqa: S603  (argumentos fijos, sin shell)
            cmd,
            capture_output=True,
            env=pg_env(settings),
            timeout=DUMP_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise BackupError("pg_dump ha tardado demasiado") from None
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:500]
        raise BackupError(f"pg_dump ha fallado: {detail}")
    return proc.stdout


@contextmanager
def backup_lock(db_engine: Engine) -> Iterator[None]:
    with db_engine.connect() as conn:
        if not conn.scalar(select(func.pg_try_advisory_lock(LOCK_KEY))):
            raise BackupBusyError("Ya se está haciendo una copia de seguridad")
        try:
            yield
        finally:
            conn.scalar(select(func.pg_advisory_unlock(LOCK_KEY)))


def _save_log(db_engine: Engine, results: list[DestinationResult]) -> None:
    with Session(db_engine) as db:
        for r in results:
            db.add(
                BackupLog(
                    destination=r.destination,
                    result="ok" if r.ok else "error",
                    message=r.message[:1000],
                )
            )
        db.commit()


def run_backup(
    trigger: str,
    settings: Settings | None = None,
    db_engine: Engine | None = None,
) -> BackupResult:
    """Hace un backup completo. Devuelve el resultado de cada destino y lo apunta en backup_log.

    Lanza BackupBusyError si ya hay otro en marcha y BackupError si falta la contraseña.
    Los fallos de pg_dump o de un destino no lanzan excepción: van en el resultado y en el log.
    """
    settings = settings or get_settings()
    db_engine = db_engine or default_engine
    if trigger not in TRIGGERS:
        raise ValueError(f"Disparador desconocido: {trigger}")
    password = settings.backup_password.get_secret_value() if settings.backup_password else ""
    if not password:
        raise BackupError("Falta BACKUP_PASSWORD en el .env: no se pueden hacer copias")

    with backup_lock(db_engine):
        now = datetime.now(TZ)
        result = BackupResult(filename=backup_filename(now), created_at=now)
        suffix = f" ({TRIGGERS[trigger]})"
        try:
            blob = encrypt(dump_database(settings), password)
        except (BackupError, ValueError) as error:
            log.error("Backup fallido: %s", error)
            result.results = [DestinationResult(d, False, f"{error}{suffix}") for d in DESTINATIONS]
            _save_log(db_engine, result.results)
            return result

        for dest, directory in destination_dirs(settings).items():
            if not is_available(directory):
                result.results.append(DestinationResult(dest, False, NOT_AVAILABLE[dest] + suffix))
                continue
            try:
                write_atomic(directory, result.filename, blob)
                rotate(directory, settings.backup_keep)
            except OSError as error:
                log.exception("No se ha podido escribir el backup en %s", dest)
                msg = f"No se ha podido escribir: {error.strerror or error}{suffix}"
                result.results.append(DestinationResult(dest, False, msg))
            else:
                result.results.append(DestinationResult(dest, True, result.filename + suffix))

        _save_log(db_engine, result.results)
        log.info("Backup %s: %s", result.filename, [(r.destination, r.ok) for r in result.results])
        return result
