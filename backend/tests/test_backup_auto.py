"""Backups automáticos (app/backup/auto.py): tras importar, periódico si hubo cambios y al
arrancar si el último es antiguo."""

import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api import imports as imports_api
from app.backup.auto import AutoBackup, changes_counter, last_ok_at
from app.backup.service import LOCK_KEY, MARKER, TZ
from app.config import Settings, get_settings
from app.db import engine
from app.models import Account, BackupLog, Transaction, User

PASSWORD = "clave-de-prueba-1d"
SAMPLES = Path(__file__).resolve().parents[2] / "samples"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(autouse=True)
def quiet_stats() -> None:
    """Las conexiones de tests anteriores pueden tener contadores sin publicar, que llegarían
    a mitad de un test. Al cerrarlas, PostgreSQL los publica; luego se espera a que el total
    deje de moverse."""
    engine.dispose()
    previous = changes_counter(engine)
    for _ in range(30):  # hasta 3 s
        time.sleep(0.1)
        current = changes_counter(engine)
        if current == previous:
            return
        previous = current


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    usb, onedrive = tmp_path / "pendrive", tmp_path / "onedrive"
    for d in (usb, onedrive):
        d.mkdir()
        (d / MARKER).touch()
    return get_settings().model_copy(
        update={
            "backup_password": SecretStr(PASSWORD),
            "backup_usb_dir": usb,
            "backup_onedrive_dir": onedrive,
            "backup_auto": True,
        }
    )


@pytest.fixture
def auto(settings: Settings) -> AutoBackup:
    return AutoBackup(settings_factory=lambda: settings)


def triggers(db: Session) -> list[str]:
    """Disparador de cada backup apuntado (uno por backup: se mira la fila del pendrive)."""
    rows = db.scalars(
        select(BackupLog.message).where(BackupLog.destination == "usb").order_by(BackupLog.id)
    )
    return [m.rsplit("(", 1)[1].rstrip(")") for m in rows]


def publish(*objects) -> None:
    """Guarda filas y obliga a PostgreSQL a publicar ya sus contadores de cambios.

    Cada conexión publica sus contadores cuando queda libre, pero como mucho una vez por
    segundo (y si no, hasta 10 s después). Para que los tests no dependan de eso, se escribe
    con una conexión propia y se llama a pg_stat_force_next_flush() en la misma transacción.
    """
    with engine.begin() as conn:
        with Session(bind=conn) as session:
            session.add_all(objects)
            session.flush()
        conn.execute(text("SELECT pg_stat_force_next_flush()"))


def new_account() -> int:
    user = User(username="gerard", display_name="Gerard", color="#0E6B58", password_hash="x")
    publish(user)
    account = Account(user_id=user.id, name="imagin", kind="spending", import_format="imagin")
    publish(account)
    return account.id


def add_transactions(account_id: int, n: int = 1) -> None:
    publish(
        *[
            Transaction(
                account_id=account_id,
                date=date(2026, 9, 1),
                description=f"COMPRA {i}",
                amount=Decimal("-1.00"),
                category_status="review",
            )
            for i in range(n)
        ]
    )


def test_el_contador_sube_con_los_cambios():
    account_id = new_account()
    before = changes_counter(engine)
    add_transactions(account_id, 3)
    assert changes_counter(engine) == before + 3


def test_periodico_solo_si_hubo_cambios(auto, db):
    account_id = new_account()
    auto.startup_check()  # no hay backups → hace el de arranque
    assert triggers(db) == ["al arrancar"]

    assert auto.interval_tick() is None  # sin cambios: nada
    assert triggers(db) == ["al arrancar"]

    add_transactions(account_id)
    result = auto.interval_tick()
    assert result is not None and result.ok
    assert triggers(db) == ["al arrancar", "periódica"]

    assert auto.interval_tick() is None  # el backup en sí no cuenta como cambio


def test_al_arrancar_sin_backups_hace_uno(auto, db):
    result = auto.startup_check()
    assert result is not None and result.ok
    assert last_ok_at(engine) is not None


def test_al_arrancar_con_un_backup_reciente_no_hace_nada(auto, db):
    db.add(BackupLog(destination="usb", result="ok", message="x (manual)"))
    db.commit()
    assert auto.startup_check() is None


def test_al_arrancar_con_un_backup_de_hace_mas_de_7_dias_hace_uno(auto, db):
    old = datetime.now(TZ) - timedelta(days=8)
    db.add(BackupLog(created_at=old, destination="usb", result="ok", message="x (manual)"))
    db.add(BackupLog(destination="onedrive", result="error", message="no (manual)"))
    db.commit()
    result = auto.startup_check()
    assert result is not None and result.ok


def test_desactivado_no_hace_nada(settings, db):
    off = AutoBackup(settings_factory=lambda: settings.model_copy(update={"backup_auto": False}))
    assert off.run_quietly("interval") is None
    assert off.startup_check() is None
    off.start()  # no arranca el hilo
    assert off._thread is None
    assert db.scalars(select(BackupLog)).all() == []


def test_sin_contrasena_no_falla(settings, db):
    no_pw = AutoBackup(
        settings_factory=lambda: settings.model_copy(update={"backup_password": None})
    )
    assert no_pw.run_quietly("interval") is None
    no_pw.start()
    assert no_pw._thread is None


def test_si_hay_otro_backup_en_marcha_se_omite_sin_error(auto, db):
    with engine.connect() as other:
        other.execute(text("SELECT pg_advisory_lock(:k)"), {"k": LOCK_KEY})
        assert auto.run_quietly("interval") is None
        other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
    assert db.scalars(select(BackupLog)).all() == []


def test_hilo_hace_el_backup_de_arranque_y_se_para(auto, db):
    auto.start()
    try:
        for _ in range(100):  # hasta 10 s
            if last_ok_at(engine):
                break
            auto._stop.wait(0.1)
    finally:
        auto.stop()
    assert triggers(db) == ["al arrancar"]
    assert auto._thread is None


def test_importar_hace_backup_solo_si_entra_algo_nuevo(auto, db, login, monkeypatch):
    monkeypatch.setattr(imports_api, "auto_backup", auto)
    client = login("gerard")
    res = client.post(
        "/api/accounts", json={"name": "imagin", "kind": "spending", "import_format": "imagin"}
    )
    account_id = res.json()["id"]
    data = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()

    def upload() -> dict:
        files = {"file": ("extracto.xlsx", data, XLSX)}
        res = client.post("/api/imports", data={"account_id": str(account_id)}, files=files)
        assert res.status_code == 200
        return res.json()

    assert upload()["new"] > 0
    assert triggers(db) == ["tras importar"]  # TestClient ejecuta las tareas en segundo plano

    assert upload()["new"] == 0  # el mismo extracto otra vez
    assert triggers(db) == ["tras importar"]
