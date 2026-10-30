"""Restaurar un backup sobre una base vacía (DISENO §12, "Restaurar").

Orden pensado para no perder nada si algo sale mal:
1. Descifrar y comprobar el archivo (pg_restore --list) ANTES de tocar la BD.
2. (Lo hace el script) copia de seguridad de lo que hay ahora.
3. Borrar la base y crearla vacía.
4. pg_restore en una sola transacción: o entra todo o no entra nada.
Las migraciones pendientes (si el backup es de una versión anterior) las aplica la app al
arrancar (`alembic upgrade head`).
"""

import os
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql

from app.backup.crypto import decrypt
from app.backup.service import (
    LABELS,
    TZ,
    BackupError,
    destination_dirs,
    find_tool,
    is_available,
    list_backup_files,
    pg_connection_args,
    pg_env,
)
from app.config import Settings

RESTORE_TIMEOUT_S = 1800


@dataclass
class BackupFile:
    destination: str
    path: Path
    size: int
    modified_at: datetime

    @property
    def label(self) -> str:
        return LABELS[self.destination]


def available_backups(settings: Settings) -> list[BackupFile]:
    """Backups de los destinos disponibles, del más reciente al más antiguo."""
    found: list[BackupFile] = []
    for dest, directory in destination_dirs(settings).items():
        if not is_available(directory):
            continue
        for path in list_backup_files(directory):
            st = path.stat()
            found.append(
                BackupFile(dest, path, st.st_size, datetime.fromtimestamp(st.st_mtime, TZ))
            )
    found.sort(key=lambda b: (b.path.name, b.destination), reverse=True)
    return found


@contextmanager
def decrypted_dump(path: Path, password: str) -> Iterator[Path]:
    """Descifra el backup a un archivo temporal (solo legible por el usuario del contenedor)
    y lo borra al terminar. pg_restore necesita un archivo: desde una tubería no siempre
    puede restaurar en el orden que quiere."""
    data = decrypt(path.read_bytes(), password)
    fd, name = tempfile.mkstemp(prefix="caudal_restore_", suffix=".dump")
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        yield tmp
    finally:
        tmp.unlink(missing_ok=True)


def _run(cmd: list[str], settings: Settings, what: str) -> None:
    try:
        proc = subprocess.run(  # noqa: S603  (argumentos fijos, sin shell)
            cmd,
            capture_output=True,
            env=pg_env(settings),
            timeout=RESTORE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise BackupError(f"{what} ha tardado demasiado") from None
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:800]
        raise BackupError(f"{what} ha fallado: {detail}")


def check_dump(dump: Path, settings: Settings) -> None:
    """Comprueba que pg_restore entiende el archivo, sin tocar ninguna base."""
    _run([find_tool("pg_restore"), "--list", str(dump)], settings, "La comprobación del backup")


def recreate_database(settings: Settings, dbname: str) -> None:
    """Borra la base (cerrando las conexiones que tenga) y la crea vacía."""
    conninfo = psycopg.conninfo.make_conninfo(
        host=settings.database_host,
        port=settings.database_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        name = sql.Identifier(dbname)
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(name))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(name))


def restore_dump(dump: Path, settings: Settings, dbname: str) -> None:
    cmd = [
        find_tool("pg_restore"),
        "--no-owner",
        "--no-privileges",
        "--single-transaction",
        "--exit-on-error",
        *pg_connection_args(settings, dbname),
        str(dump),
    ]
    _run(cmd, settings, "pg_restore")


def restore_backup(path: Path, password: str, settings: Settings, dbname: str) -> None:
    """Restaura `path` en la base `dbname`, que se BORRA antes. Si la contraseña es
    incorrecta o el archivo está dañado, falla antes de tocar nada (BackupDecryptError)."""
    with decrypted_dump(path, password) as dump:
        check_dump(dump, settings)
        recreate_database(settings, dbname)
        restore_dump(dump, settings, dbname)
