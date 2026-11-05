"""Abrir y cerrar sincronizando (app/sync/service.py), con dos «equipos» de verdad.

Cada equipo tiene su propia base aparte ("<BD de tests>_mac", "<BD de tests>_pc") y su
pendrive; los dos comparten la carpeta de Google Drive (una carpeta temporal). Se usan
pg_dump y pg_restore de verdad.
"""

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.backup.restore import CONFLICTS_DIR, available_backups, recreate_database
from app.backup.service import MARKER
from app.config import Settings, get_settings
from app.models import User
from app.sync.lock import LOCK_FILENAME, read_lock, sha256_file, write_lock
from app.sync.service import (
    BLOCKED,
    CANCELLED,
    ERROR,
    OK,
    UPDATE_CODE,
    SyncContext,
    close_sync,
    migrate,
    open_sync,
    status_lines,
)
from app.sync.state import read_local_state

PASSWORD = "clave-de-prueba-r2"


@dataclass
class Device:
    name: str
    settings: Settings
    engine: Engine
    answers: list[str] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    on_sleep: Callable[[], None] | None = None

    def ctx(self, **kw) -> SyncContext:
        def ask(prompt: str) -> str:
            self.output.append(prompt)
            return self.answers.pop(0) if self.answers else ""

        def sleep(_: float) -> None:
            if self.on_sleep:
                self.on_sleep()

        return SyncContext(
            settings=self.settings,
            engine=self.engine,
            ask=ask,
            out=self.output.append,
            sleep=sleep,
            wait_timeout_s=kw.get("wait_timeout_s", 15.0),
            wait_poll_s=5.0,
        )

    def open(self, *answers: str, **kw) -> int:
        self.answers = list(answers)
        return open_sync(self.ctx(**kw))

    def close(self) -> int:
        return close_sync(self.ctx())

    def add_user(self, username: str) -> None:
        with Session(self.engine) as db:
            db.add(
                User(
                    username=username,
                    display_name=username.capitalize(),
                    color="#0E6B58",
                    password_hash=hash_password("contrasena-de-prueba"),
                )
            )
            db.commit()

    def users(self) -> set[str]:
        with Session(self.engine) as db:
            return set(db.scalars(select(User.username)))

    @property
    def text(self) -> str:
        return "\n".join(self.output)


@pytest.fixture
def cloud(tmp_path: Path) -> Path:
    path = tmp_path / "google-drive"
    path.mkdir()
    (path / MARKER).touch()
    return path


def _drop(settings: Settings, name: str) -> None:
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


@pytest.fixture
def make_device(tmp_path: Path, cloud: Path) -> Iterator[Callable[..., Device]]:
    created: list[Device] = []
    base = get_settings()

    def _make(name: str, password: str = PASSWORD) -> Device:
        usb = tmp_path / f"pendrive-{name}"
        usb.mkdir()
        (usb / MARKER).touch()
        settings = base.model_copy(
            update={
                "postgres_db": f"{base.postgres_db}_{name}",
                "device_name": name,
                "backup_password": SecretStr(password),
                "backup_usb_dir": usb,
                "backup_cloud_dir": cloud,
                "backup_keep": 30,
            }
        )
        recreate_database(settings, settings.postgres_db)
        engine = create_engine(
            settings.database_url, connect_args={"options": "-c timezone=Europe/Madrid"}
        )
        migrate(engine)
        device = Device(name, settings, engine)
        created.append(device)
        return device

    yield _make
    for device in created:
        device.engine.dispose()
        _drop(device.settings, device.settings.postgres_db)


# --------------------------------------------------------------------------- casos normales


def test_primera_vez_sin_candado(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    assert mac.open() == OK
    lock = read_lock(cloud)
    assert lock is not None
    assert (lock.state, lock.device, lock.version, lock.version_id) == ("open", "mac", 0, "")
    assert read_local_state(mac.engine).session_open


def test_cerrar_escribe_la_version_y_el_candado(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    mac.open()
    mac.add_user("gerard")
    assert mac.close() == OK

    lock = read_lock(cloud)
    local = read_local_state(mac.engine)
    assert lock is not None and lock.file is not None
    assert (lock.state, lock.device, lock.version) == ("closed", "mac", 1)
    assert lock.version_id == local.version_id
    assert lock.lineage == local.lineage == (local.version_id,)
    assert lock.sha256 == sha256_file(cloud / lock.file)
    assert lock.schema == "0008"
    assert not local.session_open
    assert "Versión 1 guardada" in mac.text


def test_el_otro_equipo_restaura_solo(make_device, cloud: Path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    mac.add_user("gerard")
    mac.close()

    assert pc.open() == OK
    assert pc.users() == {"gerard"}
    local = read_local_state(pc.engine)
    assert local.version == 1
    assert local.session_open
    assert local.device == "pc"
    lock = read_lock(cloud)
    assert lock is not None
    assert (lock.state, lock.device, lock.version) == ("open", "pc", 1)
    assert lock.file is not None  # sigue apuntando a la copia de esta versión


def test_ida_y_vuelta_mac_pc_mac(make_device) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    mac.add_user("gerard")
    mac.close()
    pc.open()
    pc.add_user("padres")
    assert pc.close() == OK

    assert mac.open() == OK
    assert mac.users() == {"gerard", "padres"}
    assert read_local_state(mac.engine).version == 2
    # Volver a abrir sin cambios en ningún sitio: no restaura nada
    mac.close()
    mac.output.clear()
    assert mac.open() == OK
    assert "Restaurando" not in mac.text


def test_abrir_otra_vez_en_el_mismo_equipo_sin_cerrar_avisa(make_device) -> None:
    mac = make_device("mac")
    mac.open()
    mac.add_user("gerard")
    mac.close()
    mac.open()
    mac.output.clear()
    assert mac.open() == OK  # se apagó sin «Cerrar Caudal»
    assert "no se cerró" in mac.text
    assert mac.users() == {"gerard"}


# --------------------------------------------------------------------------- candado abierto


def test_abierto_en_el_otro_equipo_no_arranca(make_device) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    assert pc.open("n") == BLOCKED
    assert "abierto en el mac" in pc.text


def test_abierto_en_el_otro_equipo_forzando(make_device, cloud: Path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    mac.add_user("gerard")
    mac.close()
    mac.open()  # vuelve a abrir en el Mac: el candado dice «abierto en el mac»
    assert pc.open("s") == OK
    assert pc.users() == {"gerard"}  # la copia de esa versión sigue valiendo


# --------------------------------------------------------------------------- esperar la copia


def test_espera_a_que_baje_la_copia(make_device, cloud: Path, tmp_path: Path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    mac.add_user("gerard")
    mac.close()
    lock = read_lock(cloud)
    assert lock is not None and lock.file is not None
    away = tmp_path / lock.file
    (cloud / lock.file).rename(away)  # todavía no ha bajado

    calls = 0

    def arrives_later() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            away.rename(cloud / str(lock.file))

    pc.on_sleep = arrives_later
    assert pc.open() == OK
    assert "Esperando" in pc.text
    assert pc.users() == {"gerard"}


def test_si_la_copia_no_llega_se_puede_abrir_con_lo_local(make_device, cloud, tmp_path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    mac.add_user("gerard")
    mac.close()
    lock = read_lock(cloud)
    assert lock is not None and lock.file is not None
    (cloud / lock.file).rename(tmp_path / lock.file)

    assert pc.open("n") == CANCELLED
    assert pc.open("s") == OK
    assert pc.users() == set()
    assert read_local_state(pc.engine).session_open
    assert read_lock(cloud) == lock  # el candado sigue diciendo lo del Mac


# --------------------------------------------------------------------------- código y errores


def test_copia_de_un_codigo_mas_nuevo_pide_git_pull(make_device, cloud: Path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    mac.open()
    mac.add_user("gerard")
    mac.close()
    data = json.loads((cloud / LOCK_FILENAME).read_text(encoding="utf-8"))
    data["schema"] = "9999"
    (cloud / LOCK_FILENAME).write_text(json.dumps(data), encoding="utf-8")

    assert pc.open() == UPDATE_CODE
    assert "git pull" in pc.text
    assert pc.users() == set()


def test_contrasena_distinta_no_toca_nada(make_device) -> None:
    mac, pc = make_device("mac"), make_device("pc", password="otra-clave")
    mac.open()
    mac.add_user("gerard")
    mac.close()

    assert pc.open() == ERROR
    assert "BACKUP_PASSWORD" in pc.text
    assert pc.users() == set()


@pytest.mark.parametrize("name", ["", "Mac Air", "x" * 21])
def test_device_name_no_valido(make_device, name: str) -> None:
    mac = make_device("mac")
    mac.settings = mac.settings.model_copy(update={"device_name": name})
    assert mac.open() == ERROR
    assert mac.close() == ERROR
    assert "DEVICE_NAME" in mac.text


def test_candado_danado_se_puede_abrir_y_al_cerrar_se_rehace(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    (cloud / LOCK_FILENAME).write_text("{roto", encoding="utf-8")
    assert mac.open("n") == CANCELLED
    assert mac.open("s") == OK
    assert mac.close() == OK
    lock = read_lock(cloud)
    assert lock is not None and lock.state == "closed"


def test_sin_google_drive_al_abrir_pregunta(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    (cloud / MARKER).unlink()
    assert mac.open("n") == CANCELLED
    assert mac.open("s") == OK
    assert not (cloud / LOCK_FILENAME).exists()


def test_cerrar_sin_google_drive_no_toca_el_candado(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    mac.open()
    before = read_lock(cloud)
    (cloud / MARKER).unlink()
    assert mac.close() == ERROR
    assert "no ha llegado a Google Drive" in mac.text
    assert read_lock(cloud) == before
    assert len(list(mac.settings.backup_usb_dir.glob("caudal_*.dump.enc"))) == 1
    # Al volver a abrir aquí sigue todo igual (el candado viejo está en su historia)
    (cloud / MARKER).touch()
    mac.output.clear()
    assert mac.open() == OK
    assert "Restaurando" not in mac.text


def test_cerrar_sin_ningun_destino_no_cambia_la_version(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    mac.open()
    before = read_local_state(mac.engine)
    (cloud / MARKER).unlink()
    (mac.settings.backup_usb_dir / MARKER).unlink()
    assert mac.close() == ERROR
    assert read_local_state(mac.engine) == before


# --------------------------------------------------------------------------- conflictos


def _diverge(mac: Device, pc: Device) -> None:
    """Los dos equipos acaban con cambios por separado: el PC abre la versión 1 y se queda
    abierto con «pc-only»; mientras, se abre el Mac a la fuerza y guarda la 2 con «mac-only»."""
    mac.open()
    mac.add_user("gerard")
    mac.close()  # v1
    pc.open()  # restaura v1 y queda abierto en el PC
    pc.add_user("pc-only")
    assert mac.open("s") == OK  # a la fuerza: se queda el candado
    mac.add_user("mac-only")
    assert mac.close() == OK  # v2, sin lo del PC


def test_conflicto_elegir_la_del_otro_equipo(make_device, cloud: Path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    _diverge(mac, pc)
    pc.output.clear()

    assert pc.open("1") == OK
    assert "Los dos equipos tienen cambios" in pc.text
    assert pc.users() == {"gerard", "mac-only"}
    kept = sorted(p.name for p in (cloud / CONFLICTS_DIR).iterdir())
    assert [k.split("_")[0] for k in kept] == ["mac-v2", "pc-v1"]
    conflicts = [b for b in available_backups(pc.settings) if b.conflict]
    assert {b.label for b in conflicts} == {"Google Drive (conflicto)"}
    assert len(conflicts) == 2


def test_conflicto_elegir_la_de_este_equipo(make_device, cloud: Path) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    _diverge(mac, pc)

    assert pc.open("2") == OK
    assert pc.users() == {"gerard", "pc-only"}
    assert [p.name.split("_")[0] for p in (cloud / CONFLICTS_DIR).iterdir()] == ["mac-v2"]
    assert pc.close() == OK

    # El Mac no vuelve a preguntar: la versión nueva del PC «contiene» la suya
    mac.output.clear()
    assert mac.open() == OK
    assert "Los dos equipos" not in mac.text
    assert mac.users() == {"gerard", "pc-only"}


def test_conflicto_sin_elegir_no_abre(make_device) -> None:
    mac, pc = make_device("mac"), make_device("pc")
    _diverge(mac, pc)
    before = pc.users()
    assert pc.open("") == CANCELLED
    assert pc.users() == before


# --------------------------------------------------------------------------- estado


def test_status_lines(make_device, cloud: Path) -> None:
    mac = make_device("mac")
    ctx = mac.ctx()
    assert status_lines(ctx)[1] == "Google Drive: todavía no hay ninguna versión sincronizada"
    mac.open()
    mac.close()
    lines = status_lines(ctx)
    assert lines[0] == "Este equipo (mac): versión 1, cerrado"
    assert lines[1].startswith("Google Drive: cerrado en el mac, versión 1, ")
    lock = read_lock(cloud)
    assert lock is not None
    write_lock(cloud, replace(lock, state="open"))
    assert "abierto en el mac" in status_lines(ctx)[1]
