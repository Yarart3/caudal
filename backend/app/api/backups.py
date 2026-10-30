"""Backups: GET /api/backups/status (indicador) y POST /api/backups/run (copia manual).

Los backups son de la BD entera (no de un usuario): cualquier usuario con sesión ve el estado
y puede pedir una copia. No exponen ningún dato de nadie: solo fechas y ✓/✗.
"""

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.backup.auto import auto_backup
from app.backup.service import BackupBusyError, BackupError
from app.backup.status import backup_status
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/backups", tags=["backups"])


def backup_settings() -> Settings:
    """Dependencia aparte para que los tests puedan cambiar las carpetas y la contraseña."""
    return get_settings()


class DestinationOut(BaseModel):
    destination: str
    label: str
    available: bool
    ok: bool
    last_at: datetime | None
    last_ok_at: datetime | None
    message: str | None


class BackupStatusOut(BaseModel):
    configured: bool
    auto: bool
    last_backup_at: datetime | None
    stale: bool
    max_age_days: int
    destinations: list[DestinationOut]


class BackupRunOut(BaseModel):
    ok: bool
    filename: str
    status: BackupStatusOut


def _status(db: Session, settings: Settings) -> BackupStatusOut:
    return BackupStatusOut.model_validate(asdict(backup_status(db, settings)))


@router.get("/status")
def get_status(
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(backup_settings),
) -> BackupStatusOut:
    return _status(db, settings)


@router.post("/run")
def run_now(
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(backup_settings),
) -> BackupRunOut:
    try:
        result = auto_backup.run_recorded("manual", settings)
    except BackupBusyError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    except BackupError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    return BackupRunOut(ok=result.ok, filename=result.filename, status=_status(db, settings))
