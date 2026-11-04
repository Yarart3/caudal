"""Qué es una operación válida (lo usan la API y la importación de la plantilla)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator

TZ = ZoneInfo("Europe/Madrid")
INVESTMENT_ACCOUNTS = ("investment", "mixed")

OperationKind = Literal["buy", "sell", "dividend", "fee"]
Shares = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=8)]
Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Fee = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

FIELDS = ("account_id", "product_id", "date", "kind", "shares", "amount_eur", "fee_eur")


def first_error(error) -> str:
    """Mensaje en castellano del primer error de una ValidationError de pydantic."""
    first = error.errors()[0]
    if first.get("type") == "value_error":
        return first["msg"].removeprefix("Value error, ")
    return (
        f"Datos no válidos: revisa {first['loc'][-1]}" if first.get("loc") else "Datos no válidos"
    )


class OperationCreate(BaseModel):
    account_id: int
    product_id: int
    date: date
    kind: OperationKind
    shares: Shares = Decimal(0)
    amount_eur: Amount
    fee_eur: Fee | None = None

    @field_validator("date")
    @classmethod
    def _not_in_the_future(cls, value: date) -> date:
        if value > datetime.now(TZ).date():
            raise ValueError("La fecha no puede ser posterior a hoy")
        return value

    @model_validator(mode="after")
    def _shares_and_fee(self):
        if self.kind in ("buy", "sell") and self.shares <= 0:
            raise ValueError("Indica cuántas participaciones has comprado o vendido")
        if self.kind in ("dividend", "fee") and self.shares != 0:
            raise ValueError("Un dividendo o una comisión no lleva participaciones")
        if self.fee_eur is not None and self.fee_eur > self.amount_eur:
            raise ValueError("La comisión no puede ser mayor que el importe")
        return self
