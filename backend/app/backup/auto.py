"""Backups automáticos (DISENO §12, "Cuándo"):

- Tras importar: el endpoint de importar lo pide en segundo plano (si ha entrado algo nuevo).
- Cada BACKUP_INTERVAL_MIN minutos, solo si hubo cambios desde el último backup.
- Al arrancar, si el último backup bueno tiene más de BACKUP_MAX_AGE_DAYS días (o no hay).
- Al cerrar: lo hace el script "Cerrar Caudal" con `python -m app.backup run --trigger close`.

"Hubo cambios" se mira con los contadores de filas insertadas, cambiadas y borradas que lleva
PostgreSQL (pg_stat_user_tables), sin contar `sessions` ni `backup_log`: entrar o hacer un
backup no cuenta como cambio. Los contadores se reinician si PostgreSQL se cae; en ese caso
se hace un backup de más, que no hace daño.

Un hilo en segundo plano dentro de la app basta para esto; no hace falta APScheduler.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import Engine, bindparam, func, select, text
from sqlalchemy.orm import Session

from app.backup.service import TZ, BackupBusyError, BackupError, BackupResult, run_backup
from app.config import Settings, get_settings
from app.db import engine as default_engine
from app.models import BackupLog

log = logging.getLogger(__name__)

IGNORED_TABLES = ("sessions", "backup_log")


def changes_counter(db_engine: Engine) -> int:
    """Total de filas insertadas, cambiadas o borradas desde que arrancó PostgreSQL."""
    query = text(
        "SELECT COALESCE(SUM(n_tup_ins + n_tup_upd + n_tup_del), 0) "
        "FROM pg_stat_user_tables WHERE relname NOT IN :ignored"
    ).bindparams(bindparam("ignored", value=IGNORED_TABLES, expanding=True))
    with db_engine.connect() as conn:
        return int(conn.scalar(query) or 0)


def last_ok_at(db_engine: Engine) -> datetime | None:
    """Fecha del último backup guardado bien en algún destino."""
    with Session(db_engine) as db:
        return db.scalar(select(func.max(BackupLog.created_at)).where(BackupLog.result == "ok"))


class AutoBackup:
    def __init__(
        self,
        settings_factory: Callable[[], Settings] = get_settings,
        db_engine: Engine | None = None,
    ) -> None:
        self._settings_factory = settings_factory
        self._engine = db_engine or default_engine
        self._lock = threading.Lock()
        self._baseline: int | None = None  # contador de cambios del último backup bueno
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def settings(self) -> Settings:
        return self._settings_factory()

    # ---------- Hacer un backup ----------

    def run_recorded(self, trigger: str, settings: Settings | None = None) -> BackupResult:
        """Hace un backup y, si sale bien, recuerda el contador de cambios. Lanza las
        excepciones de run_backup (otro en marcha, falta la contraseña)."""
        settings = settings or self.settings()
        counter = changes_counter(self._engine)  # ANTES del volcado: lo de después cuenta
        result = run_backup(trigger, settings, self._engine)
        if result.ok:
            with self._lock:
                self._baseline = counter
        return result

    def run_quietly(self, trigger: str) -> BackupResult | None:
        """Para los disparadores automáticos: nunca lanza excepciones (un hilo en segundo
        plano no debe morir) y no hace nada si los backups automáticos están desactivados."""
        settings = self.settings()
        if not settings.backup_auto:
            return None
        try:
            return self.run_recorded(trigger, settings)
        except BackupBusyError:
            log.info("Backup '%s' omitido: ya hay otro en marcha", trigger)
        except BackupError as error:
            log.warning("Backup '%s' no hecho: %s", trigger, error)
        except Exception:
            log.exception("Error inesperado en el backup '%s'", trigger)
        return None

    # ---------- Disparadores ----------

    def startup_check(self) -> BackupResult | None:
        """Al arrancar: toma el contador de referencia y hace un backup si el último bueno
        es demasiado antiguo (o no hay ninguno)."""
        with self._lock:
            self._baseline = changes_counter(self._engine)
        last = last_ok_at(self._engine)
        max_age = timedelta(days=self.settings().backup_max_age_days)
        if last is None or datetime.now(TZ) - last > max_age:
            return self.run_quietly("startup")
        return None

    def interval_tick(self) -> BackupResult | None:
        """Cada BACKUP_INTERVAL_MIN: backup solo si el contador ha cambiado."""
        current = changes_counter(self._engine)
        with self._lock:
            baseline = self._baseline
        if baseline is not None and current == baseline:
            return None
        return self.run_quietly("interval")

    # ---------- Hilo en segundo plano ----------

    def start(self) -> None:
        settings = self.settings()
        if not settings.backup_auto:
            return
        if not settings.backup_password or not settings.backup_password.get_secret_value():
            log.warning("Sin BACKUP_PASSWORD: no se harán backups automáticos")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="caudal-backups", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
            self._thread = None

    def _loop(self) -> None:
        try:
            self.startup_check()
        except Exception:
            log.exception("Error en el backup al arrancar")
        interval_s = max(1, self.settings().backup_interval_min) * 60
        while not self._stop.wait(interval_s):
            try:
                self.interval_tick()
            except Exception:
                log.exception("Error en el backup periódico")


# La instancia de la app (main.py la arranca y la para; imports.py la usa tras importar)
auto_backup = AutoBackup()
