"""Fase 3, parte 3.3b: API de operaciones de inversión."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.investments import TZ
from app.db import SessionLocal
from app.models import Product, User

URL = "/api/investments/operations"


def product_id(username: str, name: str = "iShares Core S&P 500", symbol: str = "SXR8.DE") -> int:
    """Producto creado directamente en la BD (sin Yahoo: la API de productos ya está probada)."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        row = Product(
            user_id=user.id, name=name, kind="etf", price_source="yahoo", source_id=symbol
        )
        db.add(row)
        db.commit()
        return row.id


def account_id(client: TestClient, name: str, kind: str = "investment") -> int:
    res = client.post("/api/accounts", json={"name": name, "kind": kind})
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.fixture
def gerard(login) -> dict:
    client = login("gerard")
    return {
        "client": client,
        "scalable": account_id(client, "Scalable"),
        "tr": account_id(client, "Trade Republic", "mixed"),
        "sxr8": product_id("gerard"),
        "iusq": product_id("gerard", "iShares MSCI ACWI", "IUSQ.DE"),
    }


def op(g: dict, **fields) -> dict:
    body = {
        "account_id": g["scalable"],
        "product_id": g["sxr8"],
        "date": "2026-10-01",
        "kind": "buy",
        "shares": "1.5",
        "amount_eur": "1000.00",
    } | fields
    return body


def post(g: dict, **fields):
    return g["client"].post(URL, json=op(g, **fields))


def created(g: dict, **fields) -> dict:
    res = post(g, **fields)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- sesión y alta


def test_login_is_required(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401


def test_create_a_buy(gerard: dict) -> None:
    body = created(gerard, fee_eur="1.00")
    assert body == {
        "id": body["id"],
        "account_id": gerard["scalable"],
        "account_name": "Scalable",
        "product_id": gerard["sxr8"],
        "product_name": "iShares Core S&P 500",
        "date": "2026-10-01",
        "kind": "buy",
        "shares": "1.50000000",
        "amount_eur": "1000.00",
        "fee_eur": "1.00",
    }


def test_dividend_and_fee_without_shares(gerard: dict) -> None:
    created(gerard)
    dividend = created(gerard, kind="dividend", shares="0", amount_eur="3.20")
    fee = created(gerard, kind="fee", shares="0", amount_eur="1.00")
    assert (dividend["shares"], fee["shares"]) == ("0.00000000", "0.00000000")


def test_tiny_amounts_of_shares_are_not_in_scientific_notation(gerard: dict) -> None:
    body = created(gerard, shares="0.00000012", amount_eur="0.01")
    assert body["shares"] == "0.00000012"
    assert gerard["client"].get(f"{URL}/{body['id']}").json()["shares"] == "0.00000012"


def test_dividend_shares_default_to_zero(gerard: dict) -> None:
    body = gerard["client"].post(
        URL,
        json={
            "account_id": gerard["tr"],
            "product_id": gerard["sxr8"],
            "date": "2026-10-15",
            "kind": "dividend",
            "amount_eur": "2.10",
        },
    )
    assert body.status_code == 201, body.text


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"shares": "0"}, "Indica cuántas participaciones"),
        ({"kind": "sell", "shares": "0"}, "Indica cuántas participaciones"),
        ({"kind": "dividend"}, "no lleva participaciones"),
        ({"kind": "fee"}, "no lleva participaciones"),
        ({"fee_eur": "1000.01"}, "La comisión no puede ser mayor que el importe"),
        ({"amount_eur": "0"}, "Datos no válidos"),
        ({"amount_eur": "-5.00"}, "Datos no válidos"),
        ({"amount_eur": "10.001"}, "Datos no válidos"),
        ({"shares": "0.123456789"}, "Datos no válidos"),
        ({"fee_eur": "-1"}, "Datos no válidos"),
        ({"kind": "split"}, "Datos no válidos"),
    ],
)
def test_invalid_operations(gerard: dict, fields: dict, message: str) -> None:
    res = post(gerard, **fields)
    assert res.status_code == 422
    assert message in res.json()["detail"]


def test_date_cannot_be_in_the_future(gerard: dict) -> None:
    tomorrow = (datetime.now(TZ).date() + timedelta(days=1)).isoformat()
    res = post(gerard, date=tomorrow)
    assert res.status_code == 422
    assert res.json() == {"detail": "La fecha no puede ser posterior a hoy"}
    assert post(gerard, date=datetime.now(TZ).date().isoformat()).status_code == 201


def test_spending_account_is_rejected(gerard: dict) -> None:
    imagin = account_id(gerard["client"], "imagin", "spending")
    res = post(gerard, account_id=imagin)
    assert res.status_code == 422
    assert "no es de inversión" in res.json()["detail"]


def test_other_users_account_and_product_do_not_exist(gerard: dict, login) -> None:
    padres = login("padres")
    their_account = account_id(padres, "Broker de mis padres")
    their_product = product_id("padres")
    res = post(gerard, account_id=their_account)
    assert (res.status_code, res.json()) == (404, {"detail": "Cuenta no encontrada"})
    res = post(gerard, product_id=their_product)
    assert (res.status_code, res.json()) == (404, {"detail": "Producto no encontrado"})


# ---------------------------------------------------------------- ventas


def test_sell_what_you_have(gerard: dict) -> None:
    created(gerard, shares="2")
    created(gerard, kind="sell", shares="0.5", amount_eur="400.00", date="2026-10-20")
    created(gerard, kind="sell", shares="1.5", amount_eur="1200.00", date="2026-10-21")


def test_cannot_sell_more_than_you_have(gerard: dict) -> None:
    created(gerard, shares="2")
    res = post(gerard, kind="sell", shares="2.5", amount_eur="2000.00", date="2026-10-20")
    assert res.status_code == 422
    assert res.json() == {
        "detail": "Venderías más participaciones de las que tienes en esa cuenta: "
        "el 20/10/2026 quedarían -0,5"
    }
    assert len(gerard["client"].get(URL).json()) == 1  # no se ha guardado


def test_cannot_sell_before_buying(gerard: dict) -> None:
    created(gerard, shares="2", date="2026-10-10")
    res = post(gerard, kind="sell", shares="1", amount_eur="700.00", date="2026-10-09")
    assert res.status_code == 422


def test_buy_and_sell_on_the_same_day(gerard: dict) -> None:
    created(gerard, kind="buy", shares="1", date="2026-10-10")
    created(gerard, kind="sell", shares="1", amount_eur="700.00", date="2026-10-10")


def test_shares_are_counted_per_account(gerard: dict) -> None:
    created(gerard, account_id=gerard["scalable"], shares="3")
    res = post(gerard, account_id=gerard["tr"], kind="sell", shares="1", amount_eur="700.00")
    assert res.status_code == 422


def test_shares_are_counted_per_product(gerard: dict) -> None:
    created(gerard, product_id=gerard["sxr8"], shares="3")
    res = post(gerard, product_id=gerard["iusq"], kind="sell", shares="1", amount_eur="100.00")
    assert res.status_code == 422


# ---------------------------------------------------------------- lista


def test_list_newest_first_with_filters(gerard: dict) -> None:
    created(gerard, date="2026-09-01")
    created(gerard, date="2026-10-01", product_id=gerard["iusq"])
    created(gerard, date="2026-10-01", account_id=gerard["tr"])
    client = gerard["client"]
    rows = client.get(URL).json()
    assert [(r["date"], r["product_name"]) for r in rows] == [
        ("2026-10-01", "iShares Core S&P 500"),
        ("2026-10-01", "iShares MSCI ACWI"),
        ("2026-09-01", "iShares Core S&P 500"),
    ]
    by_product = client.get(URL, params={"product_id": gerard["iusq"]}).json()
    assert [r["product_name"] for r in by_product] == ["iShares MSCI ACWI"]
    by_account = client.get(URL, params={"account_id": gerard["tr"]}).json()
    assert [r["account_name"] for r in by_account] == ["Trade Republic"]


def test_operations_are_isolated(gerard: dict, login) -> None:
    mine = created(gerard)
    padres = login("padres")
    assert padres.get(URL).json() == []
    for method in ("get", "patch", "delete"):
        kwargs = {"json": {"amount_eur": "1.00"}} if method == "patch" else {}
        res = getattr(padres, method)(f"{URL}/{mine['id']}", **kwargs)
        assert (res.status_code, res.json()) == (404, {"detail": "Operación no encontrada"})


# ---------------------------------------------------------------- edición


def test_update_changes_only_what_is_sent(gerard: dict) -> None:
    body = created(gerard, fee_eur="1.00")
    res = gerard["client"].patch(f"{URL}/{body['id']}", json={"amount_eur": "1010.00"})
    assert res.status_code == 200
    after = res.json()
    assert (after["amount_eur"], after["fee_eur"], after["shares"]) == (
        "1010.00",
        "1.00",
        "1.50000000",
    )


def test_update_is_validated_as_a_whole(gerard: dict) -> None:
    body = created(gerard)
    res = gerard["client"].patch(f"{URL}/{body['id']}", json={"kind": "dividend"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Un dividendo o una comisión no lleva participaciones"}
    res = gerard["client"].patch(f"{URL}/{body['id']}", json={"amount_eur": "0"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Datos no válidos: revisa amount_eur"}


def test_update_cannot_leave_a_sale_without_shares(gerard: dict) -> None:
    buy = created(gerard, shares="2")
    created(gerard, kind="sell", shares="2", amount_eur="1500.00", date="2026-10-20")
    client = gerard["client"]
    res = client.patch(f"{URL}/{buy['id']}", json={"shares": "1"})
    assert res.status_code == 422
    assert "quedarían -1" in res.json()["detail"]
    res = client.patch(f"{URL}/{buy['id']}", json={"date": "2026-10-25"})
    assert res.status_code == 422
    assert client.get(f"{URL}/{buy['id']}").json()["shares"] == "2.00000000"  # sin cambios


def test_moving_a_buy_to_another_account_is_checked_in_both(gerard: dict) -> None:
    buy = created(gerard, shares="2")
    created(gerard, kind="sell", shares="1", amount_eur="700.00", date="2026-10-20")
    res = gerard["client"].patch(f"{URL}/{buy['id']}", json={"account_id": gerard["tr"]})
    assert res.status_code == 422  # la venta de Scalable se quedaría sin participaciones


def test_update_to_another_users_product_is_not_found(gerard: dict, login) -> None:
    body = created(gerard)
    login("padres")
    res = gerard["client"].patch(f"{URL}/{body['id']}", json={"product_id": product_id("padres")})
    assert res.status_code == 404


# ---------------------------------------------------------------- borrado


def test_delete_an_operation(gerard: dict) -> None:
    body = created(gerard)
    assert gerard["client"].delete(f"{URL}/{body['id']}").status_code == 204
    assert gerard["client"].get(URL).json() == []


def test_cannot_delete_a_buy_needed_by_a_later_sale(gerard: dict) -> None:
    buy = created(gerard, shares="2")
    sale = created(gerard, kind="sell", shares="2", amount_eur="1500.00", date="2026-10-20")
    client = gerard["client"]
    res = client.delete(f"{URL}/{buy['id']}")
    assert res.status_code == 422
    assert len(client.get(URL).json()) == 2
    assert client.delete(f"{URL}/{sale['id']}").status_code == 204
    assert client.delete(f"{URL}/{buy['id']}").status_code == 204
