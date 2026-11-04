"""Comprobar a mano qué da Yahoo (necesita internet; los tests no lo usan).

    python -m app.prices probe IE00B5BMR087 ...   → plazas y precios que Yahoo asocia a cada ISIN
    python -m app.prices quote SXR8.DE CSPX.L ... → precio de unos símbolos concretos

Con Docker, desde la raíz del proyecto:
    docker compose run --rm tests python -m app.prices probe IE00B5BMR087
"""

import sys
import time

from app.prices.yahoo import YahooClient, YahooError

PAUSE = 0.5  # segundos entre peticiones, por educación con Yahoo
HEADER = f"{'símbolo':<14}{'plaza':<22}{'divisa':<8}{'precio':>14}  {'fecha':<11}nombre"


def _row(client: YahooClient, symbol: str) -> str:
    try:
        quote = client.quote(symbol)
    except YahooError as exc:
        return f"{symbol:<14}{'—':<22}{'—':<8}{'—':>14}  {'—':<11}({exc})"
    return (
        f"{symbol:<14}{(quote.exchange or '—')[:21]:<22}{quote.currency:<8}"
        f"{quote.price:>14}  {quote.date.isoformat():<11}{quote.name or ''}"
    )


def probe(client: YahooClient, queries: list[str]) -> int:
    for query in queries:
        print(f"\n== {query}")
        try:
            listings = client.search(query)
        except YahooError as exc:
            print(f"   {exc}")
            return 1
        if not listings:
            print("   Yahoo no devuelve ningún símbolo para este texto")
        for listing in listings:
            time.sleep(PAUSE)
            print(" ", _row(client, listing.symbol))
    return 0


def quote(client: YahooClient, symbols: list[str]) -> int:
    print(HEADER)
    for symbol in symbols:
        print(_row(client, symbol))
        time.sleep(PAUSE)
    return 0


def main(argv: list[str]) -> int:
    commands = {"probe": probe, "quote": quote}
    if len(argv) < 2 or argv[0] not in commands:
        print(__doc__)
        return 2
    return commands[argv[0]](YahooClient(), argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
