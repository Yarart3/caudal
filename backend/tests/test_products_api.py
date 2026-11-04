"""Fase 3, parte 3.3a: API de productos (buscador, vista previa, alta, edición y borrado)."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.products import yahoo_client
from app.db import SessionLocal
from app.main import app
from app.models import Account, InvestmentOperation, Price, Product
from app.prices.yahoo import Listing, Quote, SymbolNotFoundError, YahooError


class FakeYahoo:
    """Yahoo simulado para quote y search: {símbolo o texto: respuesta o excepción}."""

    def __init__(self) -> None:
        self.quotes: dict[str, Quote | Exception] = {}
        self.searches: dict[str, list[Listing] | Exception] = {}
        self.calls: list[str] = []

    def _answer(self, table: dict, key: str, missing: Exception):
        self.calls.append(key)
        value = table.get(key, missing)
        if isinstance(value, Exception):
            raise value
        return value

    def quote(self, symbol: str) -> Quote:
        return self._answer(self.quotes, symbol, SymbolNotFoundError("Yahoo no conoce ese símbolo"))

    def search(self, text: str) -> list[Listing]:
        return self._answer(self.searches, text, [])


def quote(symbol: str, price: str, currency: str = "EUR", kind: str | None = "ETF") -> Quote:
    return Quote(
        symbol, Decimal(price), date(2026, 11, 4), currency, "XETRA", f"ETF {symbol}", kind
    )


@pytest.fixture
def yahoo() -> Iterator[FakeYahoo]:
    fake = FakeYahoo()
    fake.quotes["SXR8.DE"] = quote("SXR8.DE", "731.400024")
    app.dependency_overrides[yahoo_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(yahoo_client, None)


SXR8 = {
    "name": "iShares Core S&P 500",
    "isin": "IE00B5BMR087",
    "ticker": "SXR8",
    "kind": "etf",
    "price_source": "yahoo",
    "source_id": "SXR8.DE",
    "ter": "0.00070",
}
PLAN = {"name": "Plan de pensiones", "kind": "pension", "price_source": "manual"}


def create(client: TestClient, body: dict) -> dict:
    res = client.post("/api/products", json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- sesión


def test_login_is_required(client: TestClient, yahoo) -> None:
    assert client.get("/api/products").status_code == 401
    assert client.post("/api/products", json=SXR8).status_code == 401
    assert client.get("/api/products/search", params={"q": "IE00B5BMR087"}).status_code == 401
    assert client.get("/api/products/preview", params={"symbol": "SXR8.DE"}).status_code == 401
    assert yahoo.calls == []  # sin sesión no se pregunta nada a Yahoo


# ---------------------------------------------------------------- buscador y vista previa


def test_search_maps_yahoo_types(login, yahoo: FakeYahoo) -> None:
    yahoo.searches["IE00B5BMR087"] = [
        Listing("CSSPX.MI", "iShares Core S&P 500", "ETF"),
        Listing("XXX", None, "INDEX"),
    ]
    res = login("gerard").get("/api/products/search", params={"q": " IE00B5BMR087 "})
    assert res.json() == [
        {"symbol": "CSSPX.MI", "name": "iShares Core S&P 500", "kind": "etf"},
        {"symbol": "XXX", "name": None, "kind": None},
    ]


def test_search_needs_two_characters(login, yahoo) -> None:
    assert login("gerard").get("/api/products/search", params={"q": "a"}).status_code == 422


def test_search_when_yahoo_is_down(login, yahoo: FakeYahoo) -> None:
    yahoo.searches["SP500"] = YahooError("Yahoo no responde (sin red)")
    res = login("gerard").get("/api/products/search", params={"q": "SP500"})
    assert res.status_code == 502
    assert "No se ha podido consultar Yahoo" in res.json()["detail"]


def test_preview_shows_price_currency_and_exchange(login, yahoo: FakeYahoo) -> None:
    res = login("gerard").get("/api/products/preview", params={"symbol": "sxr8.de"})
    assert res.json() == {
        "symbol": "SXR8.DE",
        "name": "ETF SXR8.DE",
        "exchange": "XETRA",
        "price": "731.400024",
        "currency": "EUR",
        "price_date": "2026-11-04",
        "kind": "etf",
    }


def test_preview_converts_pence_to_pounds(login, yahoo: FakeYahoo) -> None:
    yahoo.quotes["AIAG.L"] = quote("AIAG.L", "2751.500000", "GBp", kind=None)
    body = login("gerard").get("/api/products/preview", params={"symbol": "AIAG.L"}).json()
    assert (body["price"], body["currency"], body["kind"]) == ("27.515000", "GBP", None)


def test_preview_of_unknown_symbol(login, yahoo) -> None:
    res = login("gerard").get("/api/products/preview", params={"symbol": "NOEXISTE"})
    assert res.status_code == 404
    assert res.json() == {"detail": "Yahoo no tiene precio para NOEXISTE"}


# ---------------------------------------------------------------- alta


def test_create_checks_the_price_and_takes_the_currency(login, yahoo: FakeYahoo) -> None:
    yahoo.quotes["FWRA.L"] = quote("FWRA.L", "9.37", "USD")
    client = login("gerard")
    product = create(client, {**SXR8, "isin": "IE000716YHJ7", "source_id": "fwra.l"})
    assert (product["source_id"], product["currency"]) == ("FWRA.L", "USD")
    assert yahoo.calls == ["FWRA.L"]


def test_create_returns_the_product(login, yahoo) -> None:
    product = create(login("gerard"), SXR8)
    assert product == {
        "id": product["id"],
        "name": "iShares Core S&P 500",
        "isin": "IE00B5BMR087",
        "ticker": "SXR8",
        "kind": "etf",
        "currency": "EUR",
        "price_source": "yahoo",
        "source_id": "SXR8.DE",
        "ter": "0.00070",
        "long_term": True,
    }


def test_create_without_price_is_rejected(login, yahoo) -> None:
    client = login("gerard")
    res = client.post("/api/products", json={**SXR8, "source_id": "NOEXISTE.DE"})
    assert res.status_code == 404
    assert client.get("/api/products").json() == []


def test_create_when_yahoo_is_down_is_not_saved(login, yahoo: FakeYahoo) -> None:
    yahoo.quotes["SXR8.DE"] = YahooError("Yahoo no responde (sin red)")
    client = login("gerard")
    assert client.post("/api/products", json=SXR8).status_code == 502
    assert client.get("/api/products").json() == []


def test_manual_product_needs_no_yahoo(login, yahoo: FakeYahoo) -> None:
    product = create(login("gerard"), PLAN)
    assert (product["currency"], product["source_id"], product["isin"]) == ("EUR", None, None)
    assert yahoo.calls == []


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"source_id": None}, "Falta el símbolo de Yahoo"),
        ({"price_source": "manual"}, "no lleva símbolo"),
        ({"isin": "IE00B5BMR08"}, "El ISIN no es válido"),
        ({"isin": "1E00B5BMR087"}, "El ISIN no es válido"),
        ({"kind": "bono"}, "Datos no válidos"),
        ({"price_source": "morningstar"}, "Datos no válidos"),
        ({"ter": "1"}, "Datos no válidos"),
        ({"ter": "-0.001"}, "Datos no válidos"),
        ({"name": "  "}, "Datos no válidos"),
    ],
)
def test_invalid_products_are_rejected(login, yahoo, changes: dict, message: str) -> None:
    res = login("gerard").post("/api/products", json={**SXR8, **changes})
    assert res.status_code == 422
    assert message in res.json()["detail"]


def test_isin_is_normalized(login, yahoo) -> None:
    assert create(login("gerard"), {**SXR8, "isin": " ie00b5bmr087 "})["isin"] == "IE00B5BMR087"


def test_same_isin_twice_is_a_conflict(login, yahoo: FakeYahoo) -> None:
    client = login("gerard")
    create(client, SXR8)
    calls = len(yahoo.calls)
    res = client.post("/api/products", json=SXR8)
    assert res.status_code == 409
    assert res.json() == {"detail": "Ya tienes un producto con ese ISIN"}
    assert len(yahoo.calls) == calls  # el duplicado se detecta antes de preguntar a Yahoo


def test_two_users_can_have_the_same_product(login, yahoo) -> None:
    create(login("gerard"), SXR8)
    create(login("padres"), SXR8)


# ---------------------------------------------------------------- lista, edición y aislamiento


def test_list_is_sorted_and_isolated(login, yahoo) -> None:
    gerard, padres = login("gerard"), login("padres")
    create(gerard, SXR8)
    create(gerard, PLAN)
    create(padres, {**PLAN, "name": "Depósito de mis padres"})
    # Sin distinguir mayúsculas: «iShares» va antes que «Plan»
    assert [p["name"] for p in gerard.get("/api/products").json()] == [
        "iShares Core S&P 500",
        "Plan de pensiones",
    ]
    assert [p["name"] for p in padres.get("/api/products").json()] == ["Depósito de mis padres"]


def test_other_users_product_looks_like_it_does_not_exist(login, yahoo) -> None:
    mine = create(login("gerard"), SXR8)
    padres = login("padres")
    for method in ("get", "patch", "delete"):
        kwargs = {"json": {"name": "Robado"}} if method == "patch" else {}
        res = getattr(padres, method)(f"/api/products/{mine['id']}", **kwargs)
        assert res.status_code == 404, method
        assert res.json() == {"detail": "Producto no encontrado"}


def test_update_changes_only_what_is_sent(login, yahoo) -> None:
    client = login("gerard")
    product = create(client, SXR8)
    res = client.patch(
        f"/api/products/{product['id']}",
        json={"name": "Core S&P 500", "ter": None, "long_term": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert (body["name"], body["ter"], body["long_term"]) == ("Core S&P 500", None, False)
    assert (body["source_id"], body["isin"]) == ("SXR8.DE", "IE00B5BMR087")


def test_update_cannot_empty_required_fields(login, yahoo) -> None:
    client = login("gerard")
    product = create(client, SXR8)
    res = client.patch(f"/api/products/{product['id']}", json={"name": None})
    assert res.status_code == 422
    assert res.json() == {"detail": "El campo name no puede ir vacío"}


def test_update_to_an_existing_isin_is_a_conflict(login, yahoo) -> None:
    client = login("gerard")
    create(client, SXR8)
    plan = create(client, PLAN)
    res = client.patch(f"/api/products/{plan['id']}", json={"isin": "IE00B5BMR087"})
    assert res.status_code == 409


def test_symbol_cannot_be_changed(login, yahoo) -> None:
    client = login("gerard")
    product = create(client, SXR8)
    client.patch(f"/api/products/{product['id']}", json={"source_id": "IUSQ.DE"})
    assert client.get(f"/api/products/{product['id']}").json()["source_id"] == "SXR8.DE"


# ---------------------------------------------------------------- borrado


def test_delete_removes_the_product_and_its_prices(login, yahoo) -> None:
    client = login("gerard")
    product = create(client, SXR8)
    with SessionLocal() as db:
        db.add(
            Price(
                product_id=product["id"],
                date=date(2026, 11, 4),
                price=Decimal("731.4"),
                currency="EUR",
                source="yahoo",
            )
        )
        db.commit()
    assert client.delete(f"/api/products/{product['id']}").status_code == 204
    assert client.get(f"/api/products/{product['id']}").status_code == 404
    with SessionLocal() as db:
        assert db.scalars(select(Price)).all() == []


def test_product_with_operations_cannot_be_deleted(login, yahoo) -> None:
    client = login("gerard")
    product = create(client, SXR8)
    with SessionLocal() as db:
        user_id = db.get(Product, product["id"]).user_id
        account = Account(user_id=user_id, name="Scalable", kind="investment")
        db.add(account)
        db.commit()
        db.add(
            InvestmentOperation(
                account_id=account.id,
                product_id=product["id"],
                date=date(2026, 10, 1),
                kind="buy",
                shares=Decimal(1),
                amount_eur=Decimal("700.00"),
            )
        )
        db.commit()
    res = client.delete(f"/api/products/{product['id']}")
    assert res.status_code == 409
    assert res.json() == {
        "detail": "Este producto tiene operaciones: bórralas antes de borrar el producto"
    }
