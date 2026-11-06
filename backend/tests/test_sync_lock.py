"""El candado de sincronización en la carpeta de Google Drive (Fase R)."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.sync.lock import (
    LOCK_FILENAME,
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

TZ = ZoneInfo("Europe/Madrid")
FILE = "caudal_2026-11-05_2230.dump.enc"


def make_lock(**fields) -> SyncLock:
    values = {
        "state": "closed",
        "device": "mac",
        "version": 3,
        "version_id": "id-3",
        "lineage": ("id-1", "id-2", "id-3"),
        "schema": "0008",
        "at": datetime(2026, 11, 5, 22, 30, tzinfo=TZ),
        "file": FILE,
        "size": 5,
        "sha256": "x" * 64,
    }
    values.update(fields)
    return SyncLock(**values)


def test_sin_candado_devuelve_none(tmp_path: Path) -> None:
    assert read_lock(tmp_path) is None


def test_ida_y_vuelta(tmp_path: Path) -> None:
    original = make_lock()
    write_lock(tmp_path, original)
    assert read_lock(tmp_path) == original
    # Sin el temporal: solo queda el candado
    assert [p.name for p in tmp_path.iterdir()] == [LOCK_FILENAME]


def test_candado_abierto_con_quien_cerro_la_version(tmp_path: Path) -> None:
    original = make_lock(
        state="open", closed_by="pc", closed_at=datetime(2026, 11, 5, 20, 0, tzinfo=TZ)
    )
    write_lock(tmp_path, original)
    assert read_lock(tmp_path) == original


def test_ultima_copia() -> None:
    assert last_copy(None) is None
    assert last_copy(make_lock(version_id="")) is None
    assert last_copy(make_lock()) == LastCopy("mac", 3, make_lock().at)
    opened = make_lock(state="open", device="pc", closed_by="mac", closed_at=make_lock().at)
    assert last_copy(opened) == LastCopy("mac", 3, make_lock().at)
    assert last_copy(make_lock(state="open", device="pc")) is None


def test_candado_abierto_sin_copia(tmp_path: Path) -> None:
    original = make_lock(state="open", file=None, size=None, sha256=None)
    write_lock(tmp_path, original)
    assert read_lock(tmp_path) == original


def test_no_es_json(tmp_path: Path) -> None:
    (tmp_path / LOCK_FILENAME).write_text("{roto", encoding="utf-8")
    with pytest.raises(LockError, match="no es JSON"):
        read_lock(tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        {"format": 99},
        {"state": "medio"},
        {"version": "doce"},
        {"at": "ayer"},
        {"file": "../../etc/passwd"},
        {"file": "otro.txt"},
    ],
)
def test_candado_danado(tmp_path: Path, change: dict) -> None:
    data = make_lock().to_dict()
    data.update(change)
    (tmp_path / LOCK_FILENAME).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LockError, match="dañado"):
        read_lock(tmp_path)


def test_falta_un_campo(tmp_path: Path) -> None:
    data = make_lock().to_dict()
    del data["version_id"]
    (tmp_path / LOCK_FILENAME).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LockError, match="dañado"):
        read_lock(tmp_path)


def test_estado_de_la_copia(tmp_path: Path) -> None:
    blob = b"hola!"
    path = tmp_path / FILE
    lock = make_lock(size=len(blob), sha256=None)

    assert remote_file_status(tmp_path, lock) is FileStatus.MISSING
    path.write_bytes(blob[:2])  # a medio bajar
    assert remote_file_status(tmp_path, lock) is FileStatus.INCOMPLETE
    path.write_bytes(blob)
    lock = make_lock(size=len(blob), sha256=sha256_file(path))
    assert remote_file_status(tmp_path, lock) is FileStatus.READY
    path.write_bytes(b"HOLA!")  # mismo tamaño, otro contenido
    assert remote_file_status(tmp_path, lock) is FileStatus.INCOMPLETE


def test_candado_sin_copia_es_missing(tmp_path: Path) -> None:
    assert remote_file_status(tmp_path, make_lock(file=None)) is FileStatus.MISSING
