"""Productos de inversión del usuario de la sesión (Fase 3, DISENO §7.2).

- GET /api/products/search?q=…    → símbolos que Yahoo asocia a un ISIN, ticker o nombre.
- GET /api/products/preview?symbol=… → precio, divisa y plaza de un símbolo, antes de guardarlo.
- GET/POST /api/products y GET/PATCH/DELETE /api/products/{id}.

Al crear un producto con precio de Yahoo se comprueba que el símbolo tiene precio (si Yahoo no
responde, no se guarda: así nunca queda un producto sin precio por un error de escritura). La
divisa se toma de Yahoo. El tipo que propone Yahoo es orientativo: decide el usuario.
Nadie ve ni toca los productos de otro usuario.
"""

import logging
import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import get_db
from app.models import InvestmentOperation, Product, User
from app.prices.service import normalize_currency
from app.prices.yahoo import Quote, SymbolNotFoundError, YahooClient, YahooError, http_get

router = APIRouter(prefix="/api/products", tags=["products"])
log = logging.getLogger(__name__)

ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ISIN_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def _isin(value: str) -> str:
    value = value.strip().upper()
    if not ISIN_RE.fullmatch(value):
        raise ValueError("El ISIN no es válido: son 12 caracteres, como IE00B5BMR087")
    return value


Isin = Annotated[str, AfterValidator(_isin)]
Ticker = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Symbol = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=60)
]
ProductKind = Literal["etf", "stock", "fund", "crypto", "pension", "commodity", "other"]
# Morningstar y CoinGecko se añadirán cuando haya un fondo o una cripto (FASE_3.md)
PriceSource = Literal["yahoo", "manual"]
Ter = Annotated[Decimal, Field(ge=0, lt=1, max_digits=7, decimal_places=5)]

# instrumentType / quoteType de Yahoo → tipo de Caudal (solo una propuesta)
YAHOO_KINDS = {"ETF": "etf", "EQUITY": "stock", "MUTUALFUND": "fund", "CRYPTOCURRENCY": "crypto"}

NOT_FOUND = "Producto no encontrado"
YAHOO_DOWN = "No se ha podido consultar Yahoo. Prueba en un momento."
DUPLICATE_ISIN = "Ya tienes un producto con ese ISIN"
HAS_OPERATIONS = "Este producto tiene operaciones: bórralas antes de borrar el producto"


# Alguien está esperando delante del formulario: un solo intento de 8 s (y no 3 de 15 s, como
# el refresco en segundo plano). Si Yahoo no responde, el error llega enseguida.
INTERACTIVE_TIMEOUT = 8.0


def _interactive_get(url: str, timeout: float) -> bytes:
    return http_get(url, timeout, retries=1)


def yahoo_client() -> YahooClient:
    """Dependencia aparte para que los tests usen un Yahoo simulado."""
    return YahooClient(_interactive_get, timeout=INTERACTIVE_TIMEOUT)


class ProductCreate(BaseModel):
    name: ProductName
    isin: Isin | None = None
    ticker: Ticker | None = None
    kind: ProductKind
    price_source: PriceSource
    source_id: Symbol | None = None
    ter: Ter | None = None
    long_term: bool = True

    @model_validator(mode="after")
    def _source_id_matches_source(self):
        if self.price_source == "yahoo" and not self.source_id:
            raise ValueError("Falta el símbolo de Yahoo (por ejemplo, SXR8.DE)")
        if self.price_source == "manual" and self.source_id:
            raise ValueError("Un producto con valor anotado a mano no lleva símbolo")
        return self


class ProductUpdate(BaseModel):
    """PATCH: solo los campos que se envían. El símbolo y la divisa no se cambian: para eso se
    borra el producto (si no tiene operaciones) y se crea otra vez."""

    name: ProductName | None = None
    isin: Isin | None = None
    ticker: Ticker | None = None
    kind: ProductKind | None = None
    ter: Ter | None = None
    long_term: bool | None = None


class ProductOut(BaseModel):
    id: int
    name: str
    isin: str | None
    ticker: str | None
    kind: str
    currency: str
    price_source: str
    source_id: str | None
    ter: Decimal | None
    long_term: bool


class ListingOut(BaseModel):
    symbol: str
    name: str | None
    kind: str | None


class PreviewOut(BaseModel):
    symbol: str
    name: str | None
    exchange: str | None
    price: Decimal
    currency: str
    price_date: date
    kind: str | None


def _out(product: Product) -> ProductOut:
    return ProductOut.model_validate(product, from_attributes=True)


def get_own_product(db: Session, user: User, product_id: int) -> Product:
    """El producto, solo si es del usuario. Si es de otro, 404 (como si no existiera)."""
    product = db.scalar(select(Product).where(Product.id == product_id, Product.user_id == user.id))
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return product


def _quote(client: YahooClient, symbol: str) -> Quote:
    try:
        return client.quote(symbol)
    except SymbolNotFoundError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"Yahoo no tiene precio para {symbol}"
        ) from None
    except YahooError as error:
        log.warning("Yahoo no responde: %s", error)  # el detalle técnico, al log
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=YAHOO_DOWN) from None


def _commit_or_duplicate(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_ISIN) from None


@router.get("/search")
def search(
    q: Annotated[str, Query(min_length=2, max_length=60)],
    _: User = Depends(current_user),
    client: YahooClient = Depends(yahoo_client),
) -> list[ListingOut]:
    try:
        listings = client.search(q.strip())
    except YahooError as error:
        log.warning("Yahoo no responde: %s", error)  # el detalle técnico, al log
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=YAHOO_DOWN) from None
    return [
        ListingOut(symbol=item.symbol, name=item.name, kind=YAHOO_KINDS.get(item.kind or ""))
        for item in listings
    ]


@router.get("/preview")
def preview(
    symbol: Annotated[str, Query(min_length=1, max_length=60)],
    _: User = Depends(current_user),
    client: YahooClient = Depends(yahoo_client),
) -> PreviewOut:
    symbol = symbol.strip().upper()
    quote = _quote(client, symbol)
    currency, price = normalize_currency(quote.currency, quote.price)
    return PreviewOut(
        symbol=symbol,
        name=quote.name,
        exchange=quote.exchange,
        price=price,
        currency=currency,
        price_date=quote.date,
        kind=YAHOO_KINDS.get(quote.kind or ""),
    )


@router.get("")
def list_products(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ProductOut]:
    # lower(): mismo orden en cualquier PostgreSQL, sin depender de su intercalación
    products = db.scalars(
        select(Product)
        .where(Product.user_id == user.id)
        .order_by(func.lower(Product.name), Product.id)
    )
    return [_out(p) for p in products]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    client: YahooClient = Depends(yahoo_client),
) -> ProductOut:
    if body.isin and db.scalar(
        select(exists().where(Product.user_id == user.id, Product.isin == body.isin))
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=DUPLICATE_ISIN)
    currency = "EUR"
    if body.price_source == "yahoo":
        quote = _quote(client, body.source_id)
        currency = normalize_currency(quote.currency, quote.price)[0]
    product = Product(user_id=user.id, currency=currency, **body.model_dump())
    db.add(product)
    _commit_or_duplicate(db)
    return _out(product)


@router.get("/{product_id}")
def get_product(
    product_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ProductOut:
    return _out(get_own_product(db, user, product_id))


@router.patch("/{product_id}")
def update_product(
    product_id: int,
    body: ProductUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProductOut:
    product = get_own_product(db, user, product_id)
    changes = body.model_dump(exclude_unset=True)
    for field in ("name", "kind", "long_term"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"El campo {field} no puede ir vacío"
            )
    for field, value in changes.items():
        setattr(product, field, value)
    _commit_or_duplicate(db)
    return _out(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    product = get_own_product(db, user, product_id)
    if db.scalar(select(exists().where(InvestmentOperation.product_id == product.id))):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=HAS_OPERATIONS)
    db.delete(product)  # sus precios y valores anotados se borran en cascada
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
