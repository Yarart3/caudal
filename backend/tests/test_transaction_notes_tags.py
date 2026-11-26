"""Fase 5, parte 5.1: notas y etiquetas en los movimientos."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _account(client: TestClient, name: str = "Efectivo") -> int:
    res = client.post("/api/accounts", json={"name": name, "kind": "spending"})
    assert res.status_code == 201
    return res.json()["id"]


def _tx(client: TestClient, account: int, description: str, **extra) -> dict:
    body = {
        "account_id": account,
        "date": "2026-09-26",
        "description": description,
        "amount": "-5.00",
        **extra,
    }
    res = client.post("/api/transactions", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _list(client: TestClient, **params) -> list[str]:
    res = client.get("/api/transactions", params=params)
    assert res.status_code == 200, res.text
    return [t["description"] for t in res.json()["items"]]


def test_new_transaction_without_note_or_tags(gerard: TestClient) -> None:
    tx = _tx(gerard, _account(gerard), "PAN")
    assert tx["note"] is None
    assert tx["tags"] == []


def test_create_with_note_and_tags_cleaned(gerard: TestClient) -> None:
    tx = _tx(
        gerard,
        _account(gerard),
        "HOTEL",
        note="  reserva de 2 noches  ",
        tags=["  Viaje   Japón ", "viaje japón", "", "regalos"],
    )
    assert tx["note"] == "reserva de 2 noches"
    # Espacios de más fuera, vacías fuera y repetidas (sin mirar mayúsculas) una sola vez
    assert tx["tags"] == ["Viaje Japón", "regalos"]


def test_existing_spelling_is_reused(gerard: TestClient) -> None:
    account = _account(gerard)
    _tx(gerard, account, "HOTEL", tags=["Viaje"])
    tx = _tx(gerard, account, "TREN", tags=["VIAJE"])
    assert tx["tags"] == ["Viaje"]


def test_patch_note_and_tags(gerard: TestClient) -> None:
    tx = _tx(gerard, _account(gerard), "CENA", note="con Ana", tags=["amigos"])
    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"tags": ["cumple", "amigos"]})
    assert res.status_code == 200
    assert res.json()["tags"] == ["cumple", "amigos"]
    assert res.json()["note"] == "con Ana"  # lo que no se manda no cambia

    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"note": "   ", "tags": None})
    assert res.status_code == 200
    assert res.json()["note"] is None
    assert res.json()["tags"] == []


def test_patch_tags_keeps_category(gerard: TestClient) -> None:
    account = _account(gerard)
    tx = _tx(gerard, account, "MERCADONA")
    assert tx["category_status"] == "auto"
    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"tags": ["casa"]})
    assert res.json()["category_status"] == "auto"
    assert res.json()["category_id"] == tx["category_id"]


def test_limits(gerard: TestClient) -> None:
    account = _account(gerard)
    body = {"account_id": account, "date": "2026-09-26", "description": "X", "amount": "-1.00"}
    too_long = gerard.post("/api/transactions", json={**body, "tags": ["x" * 31]})
    assert too_long.status_code == 422
    assert "30 caracteres" in too_long.json()["detail"]
    too_many = gerard.post("/api/transactions", json={**body, "tags": [f"t{i}" for i in range(11)]})
    assert too_many.status_code == 422
    long_note = gerard.post("/api/transactions", json={**body, "note": "x" * 501})
    assert long_note.status_code == 422


def test_filter_by_tag_and_search_in_note(gerard: TestClient) -> None:
    account = _account(gerard)
    _tx(gerard, account, "HOTEL", tags=["Viaje Japón"])
    _tx(gerard, account, "SUSHI", tags=["Viaje Japón", "comida"], note="Osaka")
    _tx(gerard, account, "PAN")
    assert sorted(_list(gerard, tag="Viaje Japón")) == ["HOTEL", "SUSHI"]
    assert _list(gerard, tag="  Viaje   Japón ") != []  # espacios de más no importan
    assert _list(gerard, tag="comida") == ["SUSHI"]
    assert _list(gerard, tag="no existe") == []
    assert _list(gerard, q="osaka") == ["SUSHI"]


def test_list_tags_with_counts(gerard: TestClient) -> None:
    account = _account(gerard)
    _tx(gerard, account, "A", tags=["viaje", "Casa"])
    _tx(gerard, account, "B", tags=["viaje"])
    _tx(gerard, account, "C")
    res = gerard.get("/api/transactions/tags")
    assert res.status_code == 200
    assert res.json() == [
        {"name": "Casa", "transactions": 1},
        {"name": "viaje", "transactions": 2},
    ]


def test_tags_requires_login(client: TestClient) -> None:
    assert client.get("/api/transactions/tags").status_code == 401


def test_isolation(gerard: TestClient, padres: TestClient) -> None:
    """Las etiquetas y notas de un usuario no las ve ni las usa el otro."""
    tx = _tx(gerard, _account(gerard), "HOTEL", note="secreto", tags=["Viaje"])
    assert padres.get("/api/transactions/tags").json() == []
    assert _list(padres, tag="Viaje") == []
    assert _list(padres, q="secreto") == []
    # Padres no reutiliza la forma de escribir de Gerard
    mine = _tx(padres, _account(padres), "TREN", tags=["VIAJE"])
    assert mine["tags"] == ["VIAJE"]
    # Ni puede tocar el movimiento de Gerard
    res = padres.patch(f"/api/transactions/{tx['id']}", json={"tags": []})
    assert res.status_code == 404
    assert gerard.get("/api/transactions/tags").json() == [{"name": "Viaje", "transactions": 1}]
