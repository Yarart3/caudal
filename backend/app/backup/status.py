"""Estado de los backups para el indicador «Último backup · Pendrive ✓ · OneDrive ✓»."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backup.service import LABELS, NOT_AVAILABLE, TZ, destination_dirs, is_available
from app.config import Settings
from app.models import BackupLog


@dataclass
class DestinationStatus:
    destination: str
    label: str
    available: bool  # el destino está ahora (pendrive conectado, carpeta de OneDrive)
    ok: bool  # disponible y su último backup salió bien → ✓
    last_at: datetime | None  # último intento
    last_ok_at: datetime | None  # último backup bueno
    message: str | None


@dataclass
class BackupStatus:
    configured: bool  # hay BACKUP_PASSWORD
    auto: bool
    last_backup_at: datetime | None
    stale: bool  # no hay backup bueno o tiene más de BACKUP_MAX_AGE_DAYS días
    max_age_days: int
    destinations: list[DestinationStatus]


def backup_status(db: Session, settings: Settings) -> BackupStatus:
    destinations: list[DestinationStatus] = []
    for dest, directory in destination_dirs(settings).items():
        last = db.scalar(
            select(BackupLog)
            .where(BackupLog.destination == dest)
            .order_by(BackupLog.id.desc())
            .limit(1)
        )
        last_ok = db.scalar(
            select(func.max(BackupLog.created_at)).where(
                BackupLog.destination == dest, BackupLog.result == "ok"
            )
        )
        available = is_available(directory)
        destinations.append(
            DestinationStatus(
                destination=dest,
                label=LABELS[dest],
                available=available,
                ok=available and last is not None and last.result == "ok",
                last_at=last.created_at if last else None,
                last_ok_at=last_ok,
                message=(last.message if last else None) if available else NOT_AVAILABLE[dest],
            )
        )
    oks = [d.last_ok_at for d in destinations if d.last_ok_at]
    last_backup_at = max(oks) if oks else None
    max_age = settings.backup_max_age_days
    stale = last_backup_at is None or datetime.now(TZ) - last_backup_at > timedelta(days=max_age)
    password = settings.backup_password
    return BackupStatus(
        configured=bool(password and password.get_secret_value()),
        auto=settings.backup_auto,
        last_backup_at=last_backup_at,
        stale=stale,
        max_age_days=max_age,
        destinations=destinations,
    )
