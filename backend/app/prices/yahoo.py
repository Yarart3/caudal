"""Cliente de Yahoo Finance: precio actual, histórico diario y búsqueda por ISIN, ticker o nombre.

Es una API **no oficial y sin documentación**: se leen solo los campos que se conocen de sus
respuestas y todo lo que falte se trata como "sin datos", nunca se inventa.
Usa solo la biblioteca estándar (`urllib`): así no hace falta una dependencia nueva en la imagen.

Privacidad (CLAUDE.md §10.4): en las peticiones solo viaja el identificador o el texto del buscador.
Nunca cantidades, importes ni nada de la cartera. Solo GET, solo https y solo a los dos hosts de
Yahoo de abajo.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ALLOWED_HOSTS = frozenset({"query1.finance.yahoo.com", "query2.finance.yahoo.com"})
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search?"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
DEFAULT_TZ = ZoneInfo("Europe/Madrid")
PRICE_QUANTUM = Decimal("0.000001")  # precios con NUMERIC(18,6)


class YahooError(Exception):
    """Yahoo no responde o ha respondido algo que no se entiende. El mensaje va en castellano."""


class SymbolNotFoundError(YahooError):
    """Yahoo no conoce el símbolo o no tiene cotizaciones para él."""


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    date: date
    currency: str
    exchange: str | None
    name: str | None


@dataclass(frozen=True)
class DailyClose:
    date: date
    close: Decimal


@dataclass(frozen=True)
class Listing:
    """Un resultado del buscador: todavía sin precio (eso lo da `quote`)."""

    symbol: str
    name: str | None
    kind: str | None  # quoteType de Yahoo: ETF, EQUITY, MUTUALFUND, CRYPTOCURRENCY, FUTURE…


# Descarga: recibe la URL y el tiempo de espera y devuelve el cuerpo. Se puede sustituir en los
# tests (o en el futuro por una caché) sin tocar el resto.
Fetcher = Callable[[str, float], bytes]


def http_get(
    url: str,
    timeout: float = 15.0,
    *,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """GET con tiempo de espera y reintentos (espera creciente) ante fallos de red, 429 y 5xx."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise YahooError(f"Caudal no sale a {parts.scheme}://{parts.hostname}")
    request = urllib.request.Request(url, headers=HEADERS, method="GET")  # noqa: S310
    error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise SymbolNotFoundError("Yahoo no conoce ese símbolo") from exc
            if exc.code != 429 and exc.code < 500:
                raise YahooError(f"Yahoo ha respondido con el error {exc.code}") from exc
            error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = exc
        if attempt < retries:
            sleep(1.5 * attempt)
    raise YahooError(f"Yahoo no responde ({error})")


def _json(body: bytes) -> dict:
    """JSON con los decimales como `Decimal`: el dinero nunca pasa por `float`."""
    try:
        data = json.loads(body.decode("utf-8", "replace"), parse_float=Decimal)
    except ValueError as exc:
        raise YahooError("Yahoo ha respondido algo que no es JSON") from exc
    if not isinstance(data, dict):
        raise YahooError("Yahoo ha respondido en un formato inesperado")
    return data


def _price(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool) or not isinstance(value, int | Decimal):
        return None
    price = Decimal(value).quantize(PRICE_QUANTUM)
    return price if price > 0 else None


def _timezone(meta: dict) -> ZoneInfo:
    name = meta.get("exchangeTimezoneName")
    if isinstance(name, str):
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return DEFAULT_TZ


def _day(timestamp: int, tz: ZoneInfo) -> date:
    return datetime.fromtimestamp(timestamp, tz).date()


class YahooClient:
    def __init__(self, fetch: Fetcher = http_get, timeout: float = 15.0) -> None:
        self._fetch = fetch
        self._timeout = timeout

    def _chart(
        self, symbol: str, params: dict[str, str | int]
    ) -> tuple[dict, list[tuple[int, Decimal]]]:
        """(meta, [(marca de tiempo, cierre)]) sin los huecos que Yahoo deja a `null`."""
        url = CHART_URL + urllib.parse.quote(symbol, safe="") + "?" + urllib.parse.urlencode(params)
        data = _json(self._fetch(url, self._timeout))
        chart = data.get("chart")
        results = chart.get("result") if isinstance(chart, dict) else None
        if not results or not isinstance(results[0], dict):
            raise SymbolNotFoundError(f"Yahoo no tiene datos de {symbol}")
        result = results[0]
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        # Algunas plazas (como Stuttgart) solo dan `meta`, sin serie diaria
        try:
            closes = result["indicators"]["quote"][0]["close"]
        except (KeyError, IndexError, TypeError):
            closes = None
        stamps = result.get("timestamp")
        if not isinstance(closes, list) or not isinstance(stamps, list):
            raise SymbolNotFoundError(f"Yahoo no tiene cotizaciones diarias de {symbol}")
        series = []
        for stamp, close in zip(stamps, closes, strict=False):
            price = _price(close)
            if isinstance(stamp, int) and price is not None:
                series.append((stamp, price))
        if not series:
            raise SymbolNotFoundError(f"Yahoo no tiene cotizaciones de {symbol}")
        return meta, series

    def quote(self, symbol: str) -> Quote:
        """Último cierre diario conocido (durante la sesión, el precio actual con ~15 min)."""
        meta, series = self._chart(symbol, {"range": "1mo", "interval": "1d"})
        stamp, price = series[-1]
        return Quote(
            symbol=symbol,
            price=price,
            date=_day(stamp, _timezone(meta)),
            currency=str(meta.get("currency") or "EUR"),
            exchange=meta.get("fullExchangeName") or meta.get("exchangeName"),
            name=meta.get("longName") or meta.get("shortName"),
        )

    def history(self, symbol: str, start: date, end: date) -> list[DailyClose]:
        """Cierres diarios entre dos fechas. Se pide por fechas (`period1`/`period2`) porque con
        `range=max` Yahoo devuelve un dato al mes aunque se pida `interval=1d`."""
        period1 = int(datetime(start.year, start.month, start.day, tzinfo=UTC).timestamp())
        last = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
        meta, series = self._chart(
            symbol, {"period1": period1, "period2": int(last.timestamp()), "interval": "1d"}
        )
        granularity = meta.get("dataGranularity", "1d")
        if granularity != "1d":
            raise YahooError(f"Yahoo ha devuelto precios cada {granularity} en vez de diarios")
        tz = _timezone(meta)
        by_day = {_day(stamp, tz): price for stamp, price in series}  # el último del día gana
        return [DailyClose(day, by_day[day]) for day in sorted(by_day)]

    def search(self, text: str, count: int = 10) -> list[Listing]:
        """Símbolos que Yahoo asocia a un ISIN, ticker o nombre."""
        query = urllib.parse.urlencode({"q": text, "quotesCount": count, "newsCount": 0})
        data = _json(self._fetch(SEARCH_URL + query, self._timeout))
        quotes = data.get("quotes")
        listings = []
        for item in quotes if isinstance(quotes, list) else []:
            if isinstance(item, dict) and isinstance(item.get("symbol"), str) and item["symbol"]:
                name = item.get("longname") or item.get("shortname")
                listings.append(Listing(item["symbol"], name, item.get("quoteType")))
        return listings
