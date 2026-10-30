"""Backups (app/backup/service.py y restore.py) con carpetas temporales como destinos.

Usan pg_dump y pg_restore de verdad contra la BD de tests: el test de restauración vuelca la
BD, la restaura en otra base aparte ("<BD de tests>_restore") y compara tabla a tabla.
"""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.backup import service
from app.backup.crypto import BackupDecryptError, decrypt
from app.backup.restore import available_backups, restore_backup
from app.backup.service import (
    MARKER,
    BackupBusyError,
    BackupError,
    rotate,
    run_backup,
    write_atomic,
)
from app.categories import seed_user_defaults
from app.config import Settings, get_settings
from app.db import Base, engine
from app.models import BackupLog, Transaction

PASSWORD = "clave-de-prueba-1d"


@pytest.fixture
def dirs(tmp_path: Path) -> dict[str, Path]:
    """Pendrive y OneDrive simulados, con su marcador."""
    result = {"usb": tmp_path / "pendrive", "onedrive": tmp_path / "onedrive"}
    for d in result.values():
        d.mkdir()
        (d / MARKER).touch()
    return result


@pytest.fixture
def settings(dirs: dict[str, Path]) -> Settings:
    return get_settings().model_copy(
        update={
            "backup_password": SecretStr(PASSWORD),
            "backup_usb_dir": dirs["usb"],
            "backup_onedrive_dir": dirs["onedrive"],
            "backup_keep": 30,
        }
    )


def backups_in(directory: Path) -> list[Path]:
    return sorted(directory.glob("caudal_*.dump.enc"))


def log_rows(db: Session) -> list[tuple[str, str, str]]:
    rows = db.scalars(select(BackupLog).order_by(BackupLog.id)).all()
    return [(r.destination, r.result, r.message or "") for r in rows]


def test_backup_en_los_dos_destinos(settings, dirs, db, make_user):
    make_user("gerard")
    result = run_backup("manual", settings)

    assert result.ok
    assert [(r.destination, r.ok) for r in result.results] == [("usb", True), ("onedrive", True)]
    usb, onedrive = backups_in(dirs["usb"]), backups_in(dirs["onedrive"])
    assert [p.name for p in usb] == [result.filename] == [p.name for p in onedrive]
    assert usb[0].read_bytes() == onedrive[0].read_bytes()
    assert decrypt(usb[0].read_bytes(), PASSWORD).startswith(b"PGDMP")  # pg_dump -Fc
    assert log_rows(db) == [
        ("usb", "ok", f"{result.filename} (manual)"),
        ("onedrive", "ok", f"{result.filename} (manual)"),
    ]


def test_sin_marcador_el_pendrive_no_cuenta(settings, dirs, db):
    (dirs["usb"] / MARKER).unlink()
    result = run_backup("interval", settings)

    assert result.ok  # OneDrive sí
    assert backups_in(dirs["usb"]) == []
    assert len(backups_in(dirs["onedrive"])) == 1
    assert log_rows(db)[0] == ("usb", "error", "Pendrive no conectado (periódica)")
    assert log_rows(db)[1][:2] == ("onedrive", "ok")


def test_carpeta_que_no_existe(settings, tmp_path):
    settings = settings.model_copy(update={"backup_onedrive_dir": tmp_path / "no-existe"})
    result = run_backup("manual", settings)
    assert [(r.destination, r.ok) for r in result.results] == [("usb", True), ("onedrive", False)]
    assert result.results[1].message.startswith("Carpeta de OneDrive no disponible")


def test_ningun_destino_disponible(settings, dirs, db):
    for d in dirs.values():
        (d / MARKER).unlink()
    result = run_backup("startup", settings)
    assert not result.ok
    assert [r[1] for r in log_rows(db)] == ["error", "error"]


def test_si_un_destino_falla_al_escribir_se_guarda_en_el_otro(settings, dirs, db, monkeypatch):
    real_write = service.write_atomic

    def failing_write(directory: Path, filename: str, blob: bytes) -> Path:
        if directory == dirs["usb"]:
            raise OSError(28, "No queda espacio en el dispositivo")
        return real_write(directory, filename, blob)

    monkeypatch.setattr(service, "write_atomic", failing_write)
    result = run_backup("import", settings)

    assert result.ok
    assert log_rows(db)[0] == (
        "usb",
        "error",
        "No se ha podido escribir: No queda espacio en el dispositivo (tras importar)",
    )
    assert len(backups_in(dirs["onedrive"])) == 1


def test_sin_contrasena_no_hace_nada(settings, dirs, db):
    for empty in (None, SecretStr("")):
        with pytest.raises(BackupError, match="BACKUP_PASSWORD"):
            run_backup("manual", settings.model_copy(update={"backup_password": empty}))
    assert log_rows(db) == []
    assert backups_in(dirs["usb"]) == []


def test_si_falla_pg_dump_se_apunta_en_el_registro(settings, dirs, db):
    result = run_backup("manual", settings.model_copy(update={"postgres_db": "no_existe"}))
    assert not result.ok
    rows = log_rows(db)
    assert [(r[0], r[1]) for r in rows] == [("usb", "error"), ("onedrive", "error")]
    assert rows[0][2].startswith("pg_dump ha fallado")
    assert backups_in(dirs["usb"]) == []


def test_disparador_desconocido(settings):
    with pytest.raises(ValueError, match="Disparador"):
        run_backup("cuando-sea", settings)


def test_no_se_hacen_dos_backups_a_la_vez(settings):
    with engine.connect() as other:
        other.execute(text("SELECT pg_advisory_lock(:k)"), {"k": service.LOCK_KEY})
        with pytest.raises(BackupBusyError):
            run_backup("manual", settings)
        other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": service.LOCK_KEY})
    assert run_backup("manual", settings).ok  # el bloqueo se libera


def test_rotacion_deja_las_ultimas_y_no_toca_lo_demas(tmp_path):
    names = [f"caudal_2026-{m:02d}-{d:02d}_1200.dump.enc" for m in (1, 2) for d in range(1, 19)]
    for name in names:  # 36 backups
        (tmp_path / name).write_bytes(b"x")
    others = ["notas.txt", "caudal_2026-01-01_1200.dump", "caudal_raro.dump.enc", MARKER]
    for name in others:
        (tmp_path / name).write_bytes(b"x")

    removed = rotate(tmp_path, 30)

    assert [p.name for p in removed] == sorted(names)[:6]
    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == sorted(sorted(names)[6:] + others)


def test_run_backup_rota_en_cada_destino(settings, dirs):
    for d in dirs.values():
        for day in range(1, 6):
            (d / f"caudal_2026-01-{day:02d}_0900.dump.enc").write_bytes(b"viejo")
    result = run_backup("manual", settings.model_copy(update={"backup_keep": 3}))
    for d in dirs.values():
        names = [p.name for p in backups_in(d)]
        assert len(names) == 3
        assert names[-1] == result.filename
        assert "caudal_2026-01-01_0900.dump.enc" not in names


def test_escritura_atomica_no_deja_temporales(tmp_path):
    write_atomic(tmp_path, "caudal_2026-10-30_1200.dump.enc", b"datos")
    write_atomic(tmp_path, "caudal_2026-10-30_1200.dump.enc", b"datos nuevos")  # mismo minuto
    assert [p.name for p in tmp_path.iterdir()] == ["caudal_2026-10-30_1200.dump.enc"]
    assert (tmp_path / "caudal_2026-10-30_1200.dump.enc").read_bytes() == b"datos nuevos"


def test_lista_de_backups_disponibles(settings, dirs):
    (dirs["usb"] / "caudal_2026-01-01_0900.dump.enc").write_bytes(b"a")
    (dirs["onedrive"] / "caudal_2026-02-01_0900.dump.enc").write_bytes(b"b")
    (dirs["onedrive"] / "otro.txt").write_bytes(b"c")
    found = available_backups(settings)
    assert [(b.path.name, b.destination) for b in found] == [
        ("caudal_2026-02-01_0900.dump.enc", "onedrive"),
        ("caudal_2026-01-01_0900.dump.enc", "usb"),
    ]
    (dirs["usb"] / MARKER).unlink()  # pendrive "desconectado"
    assert [b.destination for b in available_backups(settings)] == ["onedrive"]


# ---------- Restauración completa ----------


@pytest.fixture
def scratch_db(settings: Settings) -> Iterator[str]:
    """Base aparte donde se restaura. Se borra al terminar."""
    name = settings.postgres_db + "_restore"
    yield name
    conninfo = psycopg.conninfo.make_conninfo(
        host=settings.database_host,
        port=settings.database_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
        )


def snapshot(db_url) -> dict[str, list[tuple]]:
    """Todas las filas de todas las tablas (y la versión de Alembic), ordenadas."""
    eng = create_engine(db_url)
    try:
        with eng.connect() as conn:
            data = {
                t.name: [tuple(r) for r in conn.execute(select(t).order_by(*t.primary_key))]
                for t in Base.metadata.sorted_tables
            }
            data["alembic_version"] = [
                tuple(r) for r in conn.execute(text("SELECT version_num FROM alembic_version"))
            ]
        return data
    finally:
        eng.dispose()


def test_restauracion_completa_sobre_una_base_vacia(settings, dirs, db, make_account, scratch_db):
    account = make_account("imagin", name="imagin")
    make_account("wise", username="padres", name="Wise")
    seed_user_defaults(db, account.user_id)
    db.add_all(
        [
            Transaction(
                account_id=account.id,
                date=date(2026, 9, 3),
                description="MERCADONA VALÈNCIA",
                amount=Decimal("-23.45"),
                category_status="review",
                fingerprint="a" * 64,
            ),
            Transaction(
                account_id=account.id,
                date=date(2026, 9, 30),
                description="NÒMINA",
                amount=Decimal("1234.56"),
                category_status="review",
                fingerprint="b" * 64,
            ),
        ]
    )
    db.commit()
    result = run_backup("manual", settings)
    original = snapshot(settings.database_url)
    assert original["transactions"] and original["categories"] and original["rules"]

    restore_backup(backups_in(dirs["onedrive"])[0], PASSWORD, settings, scratch_db)

    restored = snapshot(settings.database_url.set(database=scratch_db))
    # La fila de backup_log de este backup se escribe DESPUÉS del volcado: no está en la copia
    original.pop("backup_log")
    restored_log = restored.pop("backup_log")
    assert restored == original
    assert restored_log == []
    assert result.ok


def test_restaurar_con_contrasena_incorrecta_no_toca_la_base(settings, dirs, make_user, scratch_db):
    make_user("gerard")
    run_backup("manual", settings)
    backup = backups_in(dirs["usb"])[0]
    restore_backup(backup, PASSWORD, settings, scratch_db)  # la base de destino ya tiene datos

    with pytest.raises(BackupDecryptError):
        restore_backup(backup, "otra-clave", settings, scratch_db)

    eng = create_engine(settings.database_url.set(database=scratch_db))
    try:
        with eng.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM users")) == 1
    finally:
        eng.dispose()


def test_restaurar_un_archivo_que_no_es_un_backup(settings, tmp_path, scratch_db):
    fake = tmp_path / "caudal_2026-10-30_1200.dump.enc"
    fake.write_bytes(b"esto no es un backup")
    with pytest.raises(BackupDecryptError, match="no es un backup"):
        restore_backup(fake, PASSWORD, settings, scratch_db)
