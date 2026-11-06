"""GET /api/sync/status: «Última copia» en la pantalla de inicio (Fase R)."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.api.sync import sync_settings
from app.backup.service import MARKER
from app.config import get_settings
from app.main import app
from app.sync.lock import SyncLock, write_lock
from app.sync.state import LocalState, write_local_state

TZ = ZoneInfo("Europe/Madrid")
AT = datetime(2026, 11, 5, 22, 30, tzinfo=TZ)


@pytest.fixture
def cloud(tmp_path: Path):
    path = tmp_path / "google-drive"
    path.mkdir()
    (path / MARKER).touch()
    settings = get_settings().model_copy(update={"backup_cloud_dir": path, "device_name": "pc"})
    app.dependency_overrides[sync_settings] = lambda: settings
    yield path
    app.dependency_overrides.pop(sync_settings, None)


def lock(**fields) -> SyncLock:
    values = {
        "state": "closed",
        "device": "mac",
        "version": 3,
        "version_id": "id-3",
        "lineage": ("id-3",),
        "schema": "0008",
        "at": AT,
        "file": "caudal_2026-11-05_2230.dump.enc",
        "size": 10,
        "sha256": "0" * 64,
    }
    values.update(fields)
    return SyncLock(**values)


def test_sin_sesion_y_sin_candado(client, cloud: Path) -> None:
    res = client.get("/api/sync/status")
    assert res.status_code == 200
    assert res.json() == {
        "this_device": "pc",
        "local_version": 0,
        "cloud_available": True,
        "last_copy": None,
    }


def test_candado_cerrado(client, cloud: Path) -> None:
    write_local_state(LocalState(version=3, version_id="id-3", lineage=("id-3",)))
    write_lock(cloud, lock())
    body = client.get("/api/sync/status").json()
    assert body["local_version"] == 3
    assert body["last_copy"]["device"] == "mac"
    assert body["last_copy"]["version"] == 3
    assert datetime.fromisoformat(body["last_copy"]["at"]) == AT


def test_candado_abierto_ensena_quien_cerro_la_version(client, cloud: Path) -> None:
    write_lock(
        cloud, lock(state="open", device="pc", at=datetime.now(TZ), closed_by="mac", closed_at=AT)
    )
    body = client.get("/api/sync/status").json()
    assert body["last_copy"]["device"] == "mac"
    assert datetime.fromisoformat(body["last_copy"]["at"]) == AT


def test_sin_google_drive(client, cloud: Path) -> None:
    (cloud / MARKER).unlink()
    body = client.get("/api/sync/status").json()
    assert body["cloud_available"] is False
    assert body["last_copy"] is None


def test_no_expone_datos_de_usuarios(login, cloud: Path) -> None:
    # Con sesión o sin ella, la respuesta es la misma y no lleva nada de nadie
    client = login("gerard")
    body = client.get("/api/sync/status").json()
    assert set(body) == {"this_device", "local_version", "cloud_available", "last_copy"}
