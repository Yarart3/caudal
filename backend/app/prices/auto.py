"""Refresco automático de precios (DISENO §7.3):

- Al arrancar, si algún producto con precio automático no tiene precio o el último se
  descargó hace más de PRICE_MAX_AGE_HOURS.
- Cada PRICE_REFRESH_MIN minutos, siempre: son pocas peticiones (una por símbolo y divisa).
- A mano, con POST /api/prices/refresh (solo los productos de ese usuario).

Un hilo en segundo plano, como los backups. Nunca deja escapar una excepción del hilo, y dos
refrescos no se pisan: si ya hay uno en marcha, el segundo no se hace.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.models import Price, Product
from app.prices.service import SOURCE, RefreshItem, refresh_prices
from app.prices.yahoo import YahooClient

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Madrid")


class PricesBusyError(Exception):
    """Ya hay una actualización de precios en marcha."""


def needs_refresh(db: Session, now: datetime, max_age: timedelta) -> bool:
    """¿Algún producto con precio automático sin precio o con el último bajado hace > max_age?"""
    latest = db.execute(
        select(func.max(Price.fetched_at))
        .select_from(Product)
        .outerjoin(Price, Price.product_id == Product.id)
        .where(Product.price_source == SOURCE, Product.source_id.is_not(None))
        .group_by(Product.id)
    ).scalars()
    return any(fetched is None or now - fetched > max_age for fetched in latest)


class AutoPrices:
    def __init__(
        self,
        settings_factory: Callable[[], Settings] = get_settings,
        session_factory: sessionmaker[Session] = SessionLocal,
        client_factory: Callable[[], YahooClient] = YahooClient,
        clock: Callable[[], datetime] = lambda: datetime.now(TZ),
    ) -> None:
        self._settings_factory = settings_factory
        self._session_factory = session_factory
        self._client_factory = client_factory
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def settings(self) -> Settings:
        return self._settings_factory()

    def refresh(self, user_id: int | None = None) -> list[RefreshItem]:
        """Actualiza los precios (de un usuario o de todos). Lanza PricesBusyError si ya hay
        otra actualización en marcha; los fallos de Yahoo van en la lista, no como excepción."""
        if not self._lock.acquire(blocking=False):
            raise PricesBusyError("Ya se están actualizando los precios. Prueba en un momento.")
        try:
            now = self._clock()
            with self._session_factory() as db:
                return refresh_prices(db, self._client_factory(), now.date(), now, user_id)
        finally:
            self._lock.release()

    def refresh_quietly(self, trigger: str) -> list[RefreshItem] | None:
        """Para el hilo: nunca lanza excepciones (un hilo en segundo plano no debe morir)."""
        try:
            items = self.refresh()
        except PricesBusyError:
            log.info("Actualización de precios '%s' omitida: ya hay otra en marcha", trigger)
            return None
        except Exception:
            log.exception("Error inesperado al actualizar los precios ('%s')", trigger)
            return None
        failed = [item.symbol for item in items if not item.ok]
        if failed:
            log.warning("Precios sin actualizar ('%s'): %s", trigger, ", ".join(failed))
        return items

    def startup_check(self) -> list[RefreshItem] | None:
        """Al arrancar: actualiza solo si algún precio falta o es antiguo."""
        max_age = timedelta(hours=self.settings().price_max_age_hours)
        with self._session_factory() as db:
            if not needs_refresh(db, self._clock(), max_age):
                return None
        return self.refresh_quietly("startup")

    # ---------- Hilo en segundo plano ----------

    def start(self) -> None:
        if not self.settings().price_auto:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="caudal-precios", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        try:
            self.startup_check()
        except Exception:
            log.exception("Error al comprobar los precios al arrancar")
        interval_s = max(1, self.settings().price_refresh_min) * 60
        while not self._stop.wait(interval_s):
            self.refresh_quietly("interval")


# La instancia de la app (main.py la arranca y la para; la API la usa para el refresco manual)
auto_prices = AutoPrices()
