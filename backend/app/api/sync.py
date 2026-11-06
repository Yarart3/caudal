"""Sincronización: GET /api/sync/status (Fase R, DISENO §15).

Para la pantalla de inicio («¿Quién entra?»), así que no pide sesión: solo dice qué equipo es
este, qué versión tiene y quién guardó la última copia y cuándo. No expone datos de nadie.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import engine
from app.sync.service import sync_info

router = APIRouter(prefix="/api/sync", tags=["sync"])


def sync_settings() -> Settings:
    """Dependencia aparte para que los tests puedan cambiar la carpeta y el equipo."""
    return get_settings()


class LastCopyOut(BaseModel):
    device: str
    version: int
    at: datetime


class SyncStatusOut(BaseModel):
    this_device: str
    local_version: int
    cloud_available: bool
    last_copy: LastCopyOut | None


@router.get("/status")
def get_status(settings: Settings = Depends(sync_settings)) -> SyncStatusOut:
    info = sync_info(settings, engine)
    last = info.last_copy
    return SyncStatusOut(
        this_device=info.this_device,
        local_version=info.local_version,
        cloud_available=info.cloud_available,
        last_copy=LastCopyOut(device=last.device, version=last.version, at=last.at)
        if last
        else None,
    )
