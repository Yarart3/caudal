"""Fase 3, parte 3.2a: cliente de Yahoo. Todo con respuestas simuladas (sin internet)."""

import json
import urllib.error
import urllib.parse
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.prices import __main__ as cli
from app.prices.yahoo import (
    DailyClose,
    History,
    Listing,
    SymbolNotFoundError,
    YahooClient,
    YahooError,
    http_get,
)

# 3 de noviembre de 2026, 16:30 UTC (17:30 en Fráncfort): una sesión normal de Xetra
T0 = int(datetime(2026, 11, 3, 16, 30, tzinfo=UTC).timestamp())
DAY = 86400


def chart(closes: list, stamps: list | None = None, **meta) -> bytes:
    """Respuesta del endpoint chart de Yahoo, con los precios como números JSON (floats)."""
    stamps = (
        stamps
        if stamps is not None
        else [T0 - DAY * (len(closes) - 1 - i) for i in range(len(closes))]
    )
    result = {"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": closes}]}}
    return json.dumps({"chart": {"result": [result], "error": None}}).encode()


class Fetch:
    """Descargador falso: guarda las URL pedidas y devuelve el cuerpo que se le diga."""

    def __init__(self, body: bytes | Exception) -> None:
        self.body = body
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: float) -> bytes:
        self.urls.append(url)
        if isinstance(self.body, Exception):
            raise self.body
        return self.body

    @property
    def query(self) -> dict[str, list[str]]:
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.urls[-1]).query)


def client(body: bytes | Exception) -> tuple[YahooClient, Fetch]:
    fetch = Fetch(body)
    return YahooClient(fetch), fetch


# ---------------------------------------------------------------- quote


def test_quote_returns_last_close_as_exact_decimal() -> None:
    body = chart(
        [111.5, None, 112.339997],
        currency="EUR",
        fullExchangeName="XETRA",
        longName="iShares Core S&P 500",
        exchangeTimezoneName="Europe/Berlin",
        instrumentType="ETF",
    )
    yahoo, fetch = client(body)
    quote = yahoo.quote("SXR8.DE")
    assert quote.price == Decimal("112.339997")
    assert isinstance(quote.price, Decimal)
    assert quote.date == date(2026, 11, 3)
    assert (quote.symbol, quote.currency) == ("SXR8.DE", "EUR")
    assert (quote.exchange, quote.name, quote.kind) == ("XETRA", "iShares Core S&P 500", "ETF")
    assert fetch.urls[0].startswith("https://query1.finance.yahoo.com/v8/finance/chart/SXR8.DE?")
    assert fetch.query == {"range": ["1mo"], "interval": ["1d"]}


def test_quote_skips_empty_bar_at_the_end() -> None:
    yahoo, _ = client(chart([110.1, 111.2, None]))
    assert yahoo.quote("X").price == Decimal("111.200000")


def test_quote_rounds_to_six_decimals() -> None:
    yahoo, _ = client(chart([0.1234567891]))
    assert yahoo.quote("X").price == Decimal("0.123457")


def test_quote_falls_back_on_missing_meta() -> None:
    yahoo, _ = client(chart([10.5], exchangeName="GER", shortName="Nombre corto"))
    quote = yahoo.quote("X")
    assert (quote.exchange, quote.name) == ("GER", "Nombre corto")
    assert quote.currency == "EUR"


def test_quote_date_uses_the_exchange_timezone() -> None:
    late = int(datetime(2026, 11, 4, 2, 0, tzinfo=UTC).timestamp())  # 21:00 del 3 en Nueva York
    in_new_york, _ = client(chart([1.0], [late], exchangeTimezoneName="America/New_York"))
    assert in_new_york.quote("X").date == date(2026, 11, 3)
    in_madrid, _ = client(chart([1.0], [late]))  # sin zona en la respuesta: Europe/Madrid
    assert in_madrid.quote("X").date == date(2026, 11, 4)


def test_quote_ignores_an_unknown_timezone() -> None:
    yahoo, _ = client(chart([1.0], exchangeTimezoneName="Marte/Olympus"))
    assert yahoo.quote("X").date == date(2026, 11, 3)


def test_symbol_is_url_encoded() -> None:
    yahoo, fetch = client(chart([1.0]))
    yahoo.quote("^GSPC")
    assert "/chart/%5EGSPC?" in fetch.urls[0]


@pytest.mark.parametrize("price", [0, -1.5, "abc", True])
def test_quote_ignores_invalid_prices(price) -> None:
    yahoo, _ = client(chart([price]))
    with pytest.raises(SymbolNotFoundError):
        yahoo.quote("X")


def test_unknown_symbol_is_not_found() -> None:
    error = {"chart": {"result": None, "error": {"code": "Not Found"}}}
    yahoo, _ = client(json.dumps(error).encode())
    with pytest.raises(SymbolNotFoundError):
        yahoo.quote("NOEXISTE")


def test_symbol_without_quotes_is_not_found() -> None:
    yahoo, _ = client(chart([None, None]))
    with pytest.raises(SymbolNotFoundError):
        yahoo.quote("X")


@pytest.mark.parametrize(
    "result",
    [
        # Como responde Stuttgart (IE00BNRQM384.SG): solo meta, sin serie diaria
        {"meta": {"currency": "EUR", "regularMarketPrice": 78.44}, "indicators": {"quote": [{}]}},
        {"meta": {}, "timestamp": [1]},
        {"meta": {}, "indicators": {"quote": [{"close": [1.0]}]}},
    ],
)
def test_result_without_daily_series_is_not_found(result: dict) -> None:
    yahoo, _ = client(json.dumps({"chart": {"result": [result], "error": None}}).encode())
    with pytest.raises(SymbolNotFoundError, match="diarias"):
        yahoo.quote("IE00BNRQM384.SG")


@pytest.mark.parametrize("body", [b"<html>Too Many Requests</html>", b"[1, 2]"])
def test_unexpected_format_is_an_error(body: bytes) -> None:
    yahoo, _ = client(body)
    with pytest.raises(YahooError) as info:
        yahoo.quote("X")
    assert not isinstance(info.value, SymbolNotFoundError)


def test_network_errors_pass_through() -> None:
    yahoo, _ = client(YahooError("Yahoo no responde (timeout)"))
    with pytest.raises(YahooError, match="no responde"):
        yahoo.quote("X")


# ---------------------------------------------------------------- history


def test_history_asks_for_dates_and_returns_sorted_closes() -> None:
    stamps = [T0, T0 - DAY, T0 + DAY]  # desordenadas a propósito
    yahoo, fetch = client(chart([2.5, 1.5, None], stamps, dataGranularity="1d", currency="USD"))
    history = yahoo.history("X", date(2026, 10, 1), date(2026, 10, 31))
    assert history == History(
        "USD",
        [
            DailyClose(date(2026, 11, 2), Decimal("1.500000")),
            DailyClose(date(2026, 11, 3), Decimal("2.500000")),
        ],
    )
    assert fetch.query["interval"] == ["1d"]
    assert fetch.query["period1"] == [str(int(datetime(2026, 10, 1, tzinfo=UTC).timestamp()))]
    # period2 es exclusivo: se pide hasta el día siguiente para incluir el último
    assert fetch.query["period2"] == [str(int(datetime(2026, 11, 1, tzinfo=UTC).timestamp()))]


def test_history_keeps_the_last_bar_of_each_day() -> None:
    yahoo, _ = client(chart([1.0, 2.0], [T0, T0 + 3600], exchangeTimezoneName="Europe/Berlin"))
    history = yahoo.history("X", date(2026, 11, 1), date(2026, 11, 3))
    assert history == History("EUR", [DailyClose(date(2026, 11, 3), Decimal("2.000000"))])


def test_history_rejects_non_daily_granularity() -> None:
    yahoo, _ = client(chart([1.0], dataGranularity="1mo"))
    with pytest.raises(YahooError, match="1mo"):
        yahoo.history("X", date(2020, 1, 1), date(2026, 1, 1))


# ---------------------------------------------------------------- search


def test_search_returns_symbols_with_names() -> None:
    body = {
        "quotes": [
            {
                "symbol": "SXR8.DE",
                "longname": "iShares Core S&P 500",
                "shortname": "ISH",
                "quoteType": "ETF",
            },
            {"symbol": "CSPX.L", "shortname": "ISHARES CORE", "quoteType": "ETF"},
            {"longname": "Sin símbolo"},
            {"symbol": ""},
            "basura",
        ]
    }
    yahoo, fetch = client(json.dumps(body).encode())
    assert yahoo.search("IE00B5BMR087") == [
        Listing("SXR8.DE", "iShares Core S&P 500", "ETF"),
        Listing("CSPX.L", "ISHARES CORE", "ETF"),
    ]
    assert fetch.urls[0].startswith("https://query2.finance.yahoo.com/v1/finance/search?")
    assert fetch.query == {"q": ["IE00B5BMR087"], "quotesCount": ["10"], "newsCount": ["0"]}


@pytest.mark.parametrize("body", [{}, {"quotes": None}, {"quotes": "x"}])
def test_search_without_results_is_empty(body: dict) -> None:
    yahoo, _ = client(json.dumps(body).encode())
    assert yahoo.search("nada") == []


# ---------------------------------------------------------------- http_get


class Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://query1.finance.yahoo.com/x", code, "x", {}, None)


class Network:
    """Sustituye a urlopen: devuelve o lanza, una cosa por llamada."""

    def __init__(self, *steps) -> None:
        self.steps = list(steps)
        self.timeouts: list[float] = []

    def __call__(self, request, timeout: float):
        self.timeouts.append(timeout)
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return Response(step)


@pytest.fixture
def sleeps() -> list[float]:
    return []


def test_http_get_returns_the_body(monkeypatch, sleeps) -> None:
    network = Network(b"hola")
    monkeypatch.setattr("urllib.request.urlopen", network)
    assert http_get("https://query1.finance.yahoo.com/x", 7.0, sleep=sleeps.append) == b"hola"
    assert network.timeouts == [7.0]
    assert sleeps == []


@pytest.mark.parametrize(
    "url",
    [
        "http://query1.finance.yahoo.com/x",
        "https://example.com/x",
        "https://query1.finance.yahoo.com.evil.example/x",
        "file:///etc/passwd",
    ],
)
def test_http_get_only_talks_to_yahoo_over_https(monkeypatch, url: str) -> None:
    network = Network(b"no se llama")
    monkeypatch.setattr("urllib.request.urlopen", network)
    with pytest.raises(YahooError, match="no sale"):
        http_get(url)
    assert network.timeouts == []


@pytest.mark.parametrize(
    "failure", [urllib.error.URLError("sin red"), TimeoutError(), http_error(429)]
)
def test_http_get_retries_temporary_failures(monkeypatch, sleeps, failure) -> None:
    network = Network(failure, b"ok")
    monkeypatch.setattr("urllib.request.urlopen", network)
    assert http_get("https://query2.finance.yahoo.com/x", sleep=sleeps.append) == b"ok"
    assert sleeps == [1.5]


def test_http_get_gives_up_after_three_attempts(monkeypatch, sleeps) -> None:
    network = Network(http_error(503), http_error(503), http_error(503), b"nunca")
    monkeypatch.setattr("urllib.request.urlopen", network)
    with pytest.raises(YahooError, match="no responde"):
        http_get("https://query1.finance.yahoo.com/x", sleep=sleeps.append)
    assert len(network.timeouts) == 3
    assert sleeps == [1.5, 3.0]  # sin espera tras el último intento


def test_http_get_does_not_retry_404(monkeypatch, sleeps) -> None:
    network = Network(http_error(404), b"nunca")
    monkeypatch.setattr("urllib.request.urlopen", network)
    with pytest.raises(SymbolNotFoundError):
        http_get("https://query1.finance.yahoo.com/x", sleep=sleeps.append)
    assert len(network.timeouts) == 1


def test_http_get_does_not_retry_client_errors(monkeypatch, sleeps) -> None:
    network = Network(http_error(400), b"nunca")
    monkeypatch.setattr("urllib.request.urlopen", network)
    with pytest.raises(YahooError, match="400"):
        http_get("https://query1.finance.yahoo.com/x", sleep=sleeps.append)
    assert len(network.timeouts) == 1


# ---------------------------------------------------------------- comando python -m app.prices


@pytest.fixture(autouse=True)
def no_pause(monkeypatch) -> None:
    monkeypatch.setattr(cli, "PAUSE", 0)


class Routes:
    """Descargador falso con una respuesta por tipo de petición."""

    def __init__(self, search: bytes | Exception, charts: dict[str, bytes]) -> None:
        self.search, self.charts = search, charts

    def __call__(self, url: str, timeout: float) -> bytes:
        if "/search?" in url:
            if isinstance(self.search, Exception):
                raise self.search
            return self.search
        symbol = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[1])
        if symbol not in self.charts:
            raise SymbolNotFoundError("Yahoo no conoce ese símbolo")
        return self.charts[symbol]


def test_probe_lists_each_listing_with_exchange_currency_and_price(capsys) -> None:
    search = json.dumps(
        {"quotes": [{"symbol": "SXR8.DE", "quoteType": "ETF"}, {"symbol": "ROTO.L"}]}
    )
    routes = Routes(
        search.encode(),
        {
            "SXR8.DE": chart(
                [112.34], currency="EUR", fullExchangeName="XETRA", longName="Core S&P 500"
            )
        },
    )
    assert cli.probe(YahooClient(routes), ["IE00B5BMR087"]) == 0
    out = capsys.readouterr().out
    assert "== IE00B5BMR087" in out
    assert "SXR8.DE" in out and "XETRA" in out and "EUR" in out and "112.340000" in out
    assert "2026-11-03" in out
    assert "ROTO.L" in out and "no conoce" in out  # un símbolo sin precio no rompe el resto


def test_probe_reports_when_yahoo_is_unreachable(capsys) -> None:
    routes = Routes(YahooError("Yahoo no responde (sin red)"), {})
    assert cli.probe(YahooClient(routes), ["IE00B5BMR087"]) == 1
    assert "no responde" in capsys.readouterr().out


def test_probe_with_no_listings(capsys) -> None:
    routes = Routes(b'{"quotes": []}', {})
    assert cli.probe(YahooClient(routes), ["xxx"]) == 0
    assert "ningún símbolo" in capsys.readouterr().out


def test_quote_command_prints_a_table(capsys) -> None:
    routes = Routes(b"{}", {"CSPX.L": chart([640.5], currency="GBp", exchangeName="LSE")})
    assert cli.quote(YahooClient(routes), ["CSPX.L", "NOEXISTE"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("símbolo")
    assert "CSPX.L" in out and "GBp" in out and "640.500000" in out and "NOEXISTE" in out


def test_main_without_arguments_shows_help(capsys) -> None:
    assert cli.main([]) == 2
    assert "probe" in capsys.readouterr().out
