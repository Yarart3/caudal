"""Servicio de precios: descarga de Yahoo y guarda en la BD (`prices` y `exchange_rates`).

- Histórico diario de cada producto: desde su último precio guardado (se vuelve a pedir ese día,
  por si era de una sesión a medias) o, si no tiene, desde su primera operación o hace un año.
  Si se apunta una operación anterior al primer precio guardado, se pide desde esa operación.
- Un símbolo que tengan varios usuarios se descarga una sola vez.
- Divisas: cada precio se guarda en su divisa (los peniques GBp/GBX, pasados a libras) y los
  tipos de cambio a EUR se guardan aparte, por día (`{DIVISA}EUR=X` de Yahoo, como en RUMBO).
- Un fallo en un símbolo no para los demás: queda anotado en el resultado.
- Precio desactualizado: el último precio de un producto se descargó hace más de `max_age`.
  Se mira cuándo se descargó, no la fecha del precio: un viernes sigue valiendo el sábado.

En las peticiones solo viaja el símbolo (CLAUDE.md §10.4).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ExchangeRate, InvestmentOperation, Price, Product
from app.prices.yahoo import PRICE_QUANTUM, YahooClient, YahooError

SOURCE = "yahoo"
DEFAULT_HISTORY_DAYS = 365
# Divisas que Yahoo da en céntimos: (divisa principal, cuántos céntimos tiene)
SUBUNITS = {"GBp": ("GBP", Decimal(100)), "GBX": ("GBP", Decimal(100))}


@dataclass(frozen=True)
class RefreshItem:
    symbol: str
    ok: bool
    days: int  # días guardados
    message: str | None = None


@dataclass(frozen=True)
class ProductPrice:
    product_id: int
    name: str
    symbol: str | None
    price: Decimal | None
    currency: str | None
    date: date | None
    fetched_at: datetime | None
    stale: bool


@dataclass(frozen=True)
class PriceStatus:
    last_refresh: datetime | None
    stale: bool
    products: list[ProductPrice]


def normalize_currency(currency: str, price: Decimal) -> tuple[str, Decimal]:
    """(divisa, precio) en la unidad principal: 2751,50 GBp → 27,515 GBP."""
    if currency in SUBUNITS:
        major, factor = SUBUNITS[currency]
        return major, (price / factor).quantize(PRICE_QUANTUM)
    return currency.upper(), price


def fx_symbol(currency: str) -> str:
    return f"{currency}EUR=X"


def _product_start(db: Session, product: Product, today: date) -> date:
    first_price, last_price = db.execute(
        select(func.min(Price.date), func.max(Price.date)).where(Price.product_id == product.id)
    ).one()
    first_operation = db.scalar(
        select(func.min(InvestmentOperation.date)).where(
            InvestmentOperation.product_id == product.id
        )
    )
    if first_operation is not None and (first_price is None or first_operation < first_price):
        return first_operation
    if last_price is not None:
        return last_price
    return today - timedelta(days=DEFAULT_HISTORY_DAYS)


def _refresh_symbol(
    db: Session,
    client: YahooClient,
    symbol: str,
    products: list[Product],
    today: date,
    now: datetime,
) -> tuple[RefreshItem, str | None, date]:
    """Descarga un símbolo y lo guarda para todos sus productos. Devuelve también la divisa
    (ya normalizada) y desde qué fecha se ha pedido, para los tipos de cambio."""
    start = min(_product_start(db, product, today) for product in products)
    try:
        history = client.history(symbol, start, today)
    except YahooError as error:
        return RefreshItem(symbol, ok=False, days=0, message=str(error)), None, start
    currency = normalize_currency(history.currency, Decimal(1))[0]
    rows = []
    for close in history.closes:
        price = normalize_currency(history.currency, close.close)[1]
        rows.extend(
            {
                "product_id": product.id,
                "date": close.date,
                "price": price,
                "currency": currency,
                "source": SOURCE,
                "fetched_at": now,
            }
            for product in products
        )
    if rows:
        stmt = insert(Price).values(rows)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=[Price.product_id, Price.date],
                set_={
                    "price": stmt.excluded.price,
                    "currency": stmt.excluded.currency,
                    "source": stmt.excluded.source,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
        )
    db.commit()
    return RefreshItem(symbol, ok=True, days=len(history.closes)), currency, start


def _refresh_rate(
    db: Session, client: YahooClient, currency: str, start: date, today: date, now: datetime
) -> RefreshItem:
    symbol = fx_symbol(currency)
    first, last = db.execute(
        select(func.min(ExchangeRate.date), func.max(ExchangeRate.date)).where(
            ExchangeRate.currency == currency
        )
    ).one()
    # Si ya hay tipos de cambio desde antes de `start`, basta con seguir desde el último
    if first is not None and start >= first:
        start = last
    try:
        history = client.history(symbol, start, today)
    except YahooError as error:
        return RefreshItem(symbol, ok=False, days=0, message=str(error))
    rows = [
        {"currency": currency, "date": c.date, "rate": c.close, "source": SOURCE, "fetched_at": now}
        for c in history.closes
    ]
    if rows:
        stmt = insert(ExchangeRate).values(rows)
        db.execute(
            stmt.on_conflict_do_update(
                index_elements=[ExchangeRate.currency, ExchangeRate.date],
                set_={"rate": stmt.excluded.rate, "fetched_at": stmt.excluded.fetched_at},
            )
        )
    db.commit()
    return RefreshItem(symbol, ok=True, days=len(rows))


def refresh_prices(
    db: Session,
    client: YahooClient,
    today: date,
    now: datetime,
    user_id: int | None = None,
) -> list[RefreshItem]:
    """Actualiza los precios de los productos con precio de Yahoo (de un usuario o de todos)
    y los tipos de cambio de sus divisas. Nunca lanza YahooError: los fallos van en la lista."""
    query = select(Product).where(Product.price_source == SOURCE, Product.source_id.is_not(None))
    if user_id is not None:
        query = query.where(Product.user_id == user_id)
    by_symbol: dict[str, list[Product]] = defaultdict(list)
    for product in db.scalars(query.order_by(Product.id)):
        by_symbol[product.source_id].append(product)

    items: list[RefreshItem] = []
    currencies: dict[str, date] = {}  # divisa → desde cuándo hacen falta sus tipos de cambio
    for symbol, products in by_symbol.items():
        item, currency, start = _refresh_symbol(db, client, symbol, products, today, now)
        items.append(item)
        if currency and currency != "EUR":
            currencies[currency] = min(start, currencies.get(currency, start))
    for currency, start in sorted(currencies.items()):
        items.append(_refresh_rate(db, client, currency, start, today, now))
    return items


def to_eur(db: Session, amount: Decimal, currency: str, day: date) -> Decimal | None:
    """Importe en euros con el tipo de cambio de ese día o del último anterior (fines de semana
    y festivos). None si no hay ningún tipo de cambio hasta ese día."""
    if currency == "EUR":
        return amount
    rate = db.scalar(
        select(ExchangeRate.rate)
        .where(ExchangeRate.currency == currency, ExchangeRate.date <= day)
        .order_by(ExchangeRate.date.desc())
        .limit(1)
    )
    return None if rate is None else amount * rate


def price_status(db: Session, user_id: int, now: datetime, max_age: timedelta) -> PriceStatus:
    """Último precio de cada producto del usuario con precio automático y si está desactualizado."""
    products = db.scalars(
        select(Product)
        .where(Product.user_id == user_id, Product.price_source != "manual")
        .order_by(func.lower(Product.name), Product.id)
    ).all()
    rows: list[ProductPrice] = []
    for product in products:
        last = db.scalars(
            select(Price).where(Price.product_id == product.id).order_by(Price.date.desc()).limit(1)
        ).first()
        rows.append(
            ProductPrice(
                product_id=product.id,
                name=product.name,
                symbol=product.source_id,
                price=last.price if last else None,
                currency=last.currency if last else None,
                date=last.date if last else None,
                fetched_at=last.fetched_at if last else None,
                stale=last is None or now - last.fetched_at > max_age,
            )
        )
    fetched = [row.fetched_at for row in rows if row.fetched_at is not None]
    return PriceStatus(
        last_refresh=max(fetched) if fetched else None,
        stale=any(row.stale for row in rows),
        products=rows,
    )
