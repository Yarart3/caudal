"""Precios: GET /api/prices/status (último precio de cada producto) y POST /api/prices/refresh.

Cada usuario ve y actualiza solo sus productos. Los precios son datos públicos de mercado, pero
qué productos tiene cada uno no lo es.
"""

from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.prices.auto import TZ, AutoPrices, PricesBusyError, auto_prices
from app.prices.service import price_status

router = APIRouter(prefix="/api/prices", tags=["prices"])


def prices_settings() -> Settings:
    """Dependencia aparte para que los tests puedan cambiar PRICE_MAX_AGE_HOURS."""
    return get_settings()


def prices_runner() -> AutoPrices:
    """Dependencia aparte para que los tests usen un Yahoo simulado."""
    return auto_prices


class ProductPriceOut(BaseModel):
    product_id: int
    name: str
    symbol: str | None
    price: Decimal | None
    currency: str | None
    date: date | None
    fetched_at: datetime | None
    stale: bool


class PriceStatusOut(BaseModel):
    last_refresh: datetime | None
    stale: bool
    max_age_hours: int
    products: list[ProductPriceOut]


class RefreshItemOut(BaseModel):
    symbol: str
    ok: bool
    days: int
    message: str | None


class RefreshOut(BaseModel):
    items: list[RefreshItemOut]
    status: PriceStatusOut


def _status(db: Session, user: User, settings: Settings) -> PriceStatusOut:
    hours = settings.price_max_age_hours
    result = price_status(db, user.id, datetime.now(TZ), timedelta(hours=hours))
    return PriceStatusOut.model_validate({**asdict(result), "max_age_hours": hours})


@router.get("/status")
def get_status(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(prices_settings),
) -> PriceStatusOut:
    return _status(db, user, settings)


@router.post("/refresh")
def refresh_now(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(prices_settings),
    runner: AutoPrices = Depends(prices_runner),
) -> RefreshOut:
    try:
        items = runner.refresh(user_id=user.id)
    except PricesBusyError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from None
    db.expire_all()  # el refresco ha escrito con otra sesión
    return RefreshOut(
        items=[RefreshItemOut.model_validate(asdict(item)) for item in items],
        status=_status(db, user, settings),
    )
