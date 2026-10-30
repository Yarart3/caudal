"""GET /api/backups/status y POST /api/backups/run (Fase 1d)."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text

from app.api.backups import backup_settings
from app.backup.service import LOCK_KEY, MARKER, TZ
from app.config import Settings, get_settings
from app.db import engine
from app.main import app
from app.models import BackupLog

PASSWORD = "clave-de-prueba-1d"


@pytest.fixture
def dirs(tmp_path: Path) -> dict[str, Path]:
    result = {"usb": tmp_path / "pendrive", "onedrive": tmp_path / "onedrive"}
    for d in result.values():
        d.mkdir()
        (d / MARKER).touch()
    return result


@pytest.fixture
def settings(dirs) -> Iterator[Settings]:
    current = get_settings().model_copy(
        update={
            "backup_password": SecretStr(PASSWORD),
            "backup_usb_dir": dirs["usb"],
            "backup_onedrive_dir": dirs["onedrive"],
        }
    )
    app.dependency_overrides[backup_settings] = lambda: current
    yield current
    app.dependency_overrides.pop(backup_settings, None)


def by_dest(status: dict) -> dict[str, dict]:
    return {d["destination"]: d for d in status["destinations"]}


def test_hace_falta_iniciar_sesion(client: TestClient, settings) -> None:
    assert client.get("/api/backups/status").status_code == 401
    assert client.post("/api/backups/run").status_code == 401


def test_estado_sin_backups(login, settings) -> None:
    status = login("gerard").get("/api/backups/status").json()
    assert status["configured"] is True
    assert status["last_backup_at"] is None
    assert status["stale"] is True
    assert status["max_age_days"] == 7
    dests = by_dest(status)
    assert [d["label"] for d in status["destinations"]] == ["Pendrive", "OneDrive"]
    assert dests["usb"]["available"] is True
    assert dests["usb"]["ok"] is False  # disponible, pero todavía sin backups
    assert dests["usb"]["last_at"] is None


def test_copia_manual(login, settings, dirs) -> None:
    client = login("gerard")
    res = client.post("/api/backups/run")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert (dirs["usb"] / body["filename"]).is_file()
    assert (dirs["onedrive"] / body["filename"]).is_file()
    status = body["status"]
    assert status["stale"] is False
    assert status["last_backup_at"] is not None
    assert all(d["ok"] for d in status["destinations"])
    assert by_dest(status)["usb"]["message"] == f"{body['filename']} (manual)"
    assert client.get("/api/backups/status").json() == status


def test_pendrive_no_conectado(login, settings, dirs) -> None:
    (dirs["usb"] / MARKER).unlink()
    body = login("gerard").post("/api/backups/run").json()
    assert body["ok"] is True  # OneDrive sí
    dests = by_dest(body["status"])
    assert dests["usb"] | {"last_at": None} == {
        "destination": "usb",
        "label": "Pendrive",
        "available": False,
        "ok": False,
        "last_at": None,
        "last_ok_at": None,
        "message": "Pendrive no conectado",
    }
    assert dests["onedrive"]["ok"] is True


def test_pendrive_desconectado_despues_de_un_backup_bueno(login, settings, dirs) -> None:
    client = login("gerard")
    client.post("/api/backups/run")
    (dirs["usb"] / MARKER).unlink()
    usb = by_dest(client.get("/api/backups/status").json())["usb"]
    assert usb["available"] is False
    assert usb["ok"] is False  # ✗ aunque el último backup saliera bien: ahora no está
    assert usb["last_ok_at"] is not None
    assert usb["message"] == "Pendrive no conectado"


def test_ningun_destino(login, settings, dirs) -> None:
    for d in dirs.values():
        (d / MARKER).unlink()
    body = login("gerard").post("/api/backups/run").json()
    assert body["ok"] is False
    assert body["status"]["last_backup_at"] is None


def test_backup_antiguo(login, settings, db) -> None:
    old = datetime.now(TZ) - timedelta(days=8)
    db.add(BackupLog(created_at=old, destination="usb", result="ok", message="x (manual)"))
    db.commit()
    status = login("gerard").get("/api/backups/status").json()
    assert status["stale"] is True
    assert status["last_backup_at"] is not None


def test_sin_contrasena(login, settings) -> None:
    app.dependency_overrides[backup_settings] = lambda: settings.model_copy(
        update={"backup_password": None}
    )
    client = login("gerard")
    assert client.get("/api/backups/status").json()["configured"] is False
    res = client.post("/api/backups/run")
    assert res.status_code == 409
    assert "BACKUP_PASSWORD" in res.json()["detail"]


def test_otro_backup_en_marcha(login, settings) -> None:
    client = login("gerard")
    with engine.connect() as other:
        other.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_KEY})
        res = client.post("/api/backups/run")
        other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    assert res.status_code == 409
    assert res.json()["detail"] == "Ya se está haciendo una copia de seguridad"


def test_el_estado_es_el_mismo_para_los_dos_usuarios(login, settings) -> None:
    """Los backups son de la BD entera: no hay datos por usuario que aislar, y el estado no
    enseña nada de nadie (solo fechas y ✓/✗). Los dos ven lo mismo y los dos pueden copiar."""
    gerard, padres = login("gerard", is_admin=True), login("padres")
    assert padres.post("/api/backups/run").status_code == 200
    assert gerard.get("/api/backups/status").json() == padres.get("/api/backups/status").json()
