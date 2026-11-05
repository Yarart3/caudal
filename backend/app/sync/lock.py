"""El candado de sincronización: `caudal-sync.json`, en la carpeta de Google Drive.

Dice qué equipo tiene Caudal abierto o cuál lo cerró el último, con qué versión y en qué copia.
El archivo lo puede haber escrito el otro equipo, así que se valida todo lo que se lee (por
ejemplo, el nombre de la copia tiene que ser un backup de Caudal, nunca una ruta).
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.backup.service import FILENAME_RE, PARTIAL_SUFFIX

LOCK_FILENAME = "caudal-sync.json"
LOCK_FORMAT = 1
STATES = ("open", "closed")


class LockError(Exception):
    """El candado está dañado o no se entiende. Mensaje en castellano."""


@dataclass(frozen=True)
class SyncLock:
    state: str  # "open": abierto en `device` · "closed": `device` lo cerró con esta versión
    device: str
    version: int
    version_id: str
    lineage: tuple[str, ...]
    schema: str  # revisión de Alembic del código que escribió la copia
    at: datetime
    file: str | None = None  # la copia con esta versión (None si todavía no hay ninguna)
    size: int | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lineage"] = list(self.lineage)
        data["at"] = self.at.isoformat()
        return {"format": LOCK_FORMAT, **data}

    @classmethod
    def from_dict(cls, data: Any) -> "SyncLock":
        try:
            if not isinstance(data, dict) or data.get("format") != LOCK_FORMAT:
                raise ValueError("formato desconocido")
            file = data.get("file")
            if file is not None and not (isinstance(file, str) and FILENAME_RE.match(file)):
                raise ValueError("el nombre de la copia no es válido")
            lock = cls(
                state=str(data["state"]),
                device=str(data["device"]),
                version=int(data["version"]),
                version_id=str(data["version_id"]),
                lineage=tuple(str(i) for i in data["lineage"]),
                schema=str(data["schema"]),
                at=datetime.fromisoformat(data["at"]),
                file=file,
                size=None if data.get("size") is None else int(data["size"]),
                sha256=None if data.get("sha256") is None else str(data["sha256"]),
            )
            if lock.state not in STATES:
                raise ValueError(f"estado «{lock.state}» desconocido")
        except (KeyError, TypeError, ValueError) as error:
            raise LockError(f"El candado de sincronización está dañado ({error})") from None
        return lock


def read_lock(directory: Path) -> SyncLock | None:
    """Lee el candado. None si todavía no existe (ningún equipo ha sincronizado)."""
    path = directory / LOCK_FILENAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise LockError(f"No se puede leer el candado de sincronización: {error}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise LockError("El candado de sincronización está dañado (no es JSON)") from None
    return SyncLock.from_dict(data)


def write_lock(directory: Path, lock: SyncLock) -> None:
    """Escribe el candado de golpe (temporal + renombrar): Google Drive nunca sube uno a medias."""
    final = directory / LOCK_FILENAME
    tmp = directory / f".{LOCK_FILENAME}{PARTIAL_SUFFIX}"
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(lock.to_dict(), fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
    finally:
        tmp.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileStatus(StrEnum):
    READY = "ready"  # está y es la que dice el candado
    MISSING = "missing"  # todavía no ha bajado (o el candado no apunta a ninguna)
    INCOMPLETE = "incomplete"  # está, pero no coincide: a medio bajar o es otra


def remote_file_status(directory: Path, lock: SyncLock) -> FileStatus:
    """¿Ha bajado ya de Google Drive la copia que dice el candado?"""
    if lock.file is None:
        return FileStatus.MISSING
    path = directory / lock.file
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return FileStatus.MISSING
    if lock.size is not None and size != lock.size:
        return FileStatus.INCOMPLETE
    if lock.sha256 is not None and sha256_file(path) != lock.sha256:
        return FileStatus.INCOMPLETE
    return FileStatus.READY
