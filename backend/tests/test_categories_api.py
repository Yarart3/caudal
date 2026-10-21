"""Fase 1c, parte 1.2: /api/categories."""

import pytest
from fastapi.testclient import TestClient

from app.categories.seed import DEFAULT_CATEGORIES


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _by_name(client: TestClient) -> dict[str, dict]:
    return {c["name"]: c for c in client.get("/api/categories").json()}


def _account(client: TestClient) -> int:
    body = {"name": "Efectivo", "kind": "spending", "import_format": None}
    return client.post("/api/accounts", json=body).json()["id"]


def _tx(client: TestClient, account: int, description: str, amount: str = "-5.00") -> dict:
    body = {
        "account_id": account,
        "date": "2026-09-26",
        "description": description,
        "amount": amount,
    }
    res = client.post("/api/transactions", json=body)
    assert res.status_code == 201
    return res.json()


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/categories").status_code == 401


def test_list_has_defaults_expenses_first(gerard: TestClient) -> None:
    categories = gerard.get("/api/categories").json()
    assert len(categories) == len(DEFAULT_CATEGORIES)
    kinds = [c["kind"] for c in categories]
    assert kinds == sorted(kinds)  # expense antes que income
    super_ = next(c for c in categories if c["name"] == "Supermercado")
    assert super_["rules"] == 3  # BON AREA, MERCADONA, CONSUM
    assert super_["transactions"] == 0


def test_counts_transactions(gerard: TestClient) -> None:
    account = _account(gerard)
    _tx(gerard, account, "MERCADONA")
    _tx(gerard, account, "BON AREA")
    assert _by_name(gerard)["Supermercado"]["transactions"] == 2


def test_create_update_and_duplicate(gerard: TestClient) -> None:
    res = gerard.post("/api/categories", json={"name": " Mascotas ", "kind": "expense"})
    assert res.status_code == 201
    created = res.json()
    assert (created["name"], created["color"], created["transactions"]) == (
        "Mascotas",
        "#5B616B",
        0,
    )

    duplicate = gerard.post("/api/categories", json={"name": "Mascotas", "kind": "expense"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Ya tienes una categoría con ese nombre"

    res = gerard.patch(f"/api/categories/{created['id']}", json={"color": "#112233"})
    assert res.json()["color"] == "#112233"
    res = gerard.patch(f"/api/categories/{created['id']}", json={"name": "Supermercado"})
    assert res.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "kind": "expense"},
        {"name": "X", "kind": "gasto"},
        {"name": "X", "kind": "expense", "color": "rojo"},
        {"name": "X" * 61, "kind": "expense"},
    ],
)
def test_create_validation(gerard: TestClient, body: dict) -> None:
    assert gerard.post("/api/categories", json=body).status_code == 422


def test_patch_null_is_rejected(gerard: TestClient) -> None:
    category = _by_name(gerard)["Ropa"]
    res = gerard.patch(f"/api/categories/{category['id']}", json={"name": None})
    assert res.status_code == 422


def test_delete_sends_transactions_to_review_and_reapplies(gerard: TestClient) -> None:
    account = _account(gerard)
    categories = _by_name(gerard)
    shop = gerard.post("/api/categories", json={"name": "Tiendas", "kind": "expense"}).json()
    other = _tx(gerard, account, "ZAPATERIA PEPE")
    gerard.patch(f"/api/transactions/{other['id']}", json={"category_id": shop["id"]})
    market = _tx(gerard, account, "MERCADONA")  # auto → Supermercado
    gerard.patch(f"/api/transactions/{market['id']}", json={"category_id": shop["id"]})

    assert gerard.delete(f"/api/categories/{shop['id']}").status_code == 204
    items = {t["id"]: t for t in gerard.get("/api/transactions").json()["items"]}
    assert (items[other["id"]]["category_id"], items[other["id"]]["category_status"]) == (
        None,
        "review",
    )
    # Al quedar por revisar, la regla MERCADONA lo vuelve a categorizar
    assert items[market["id"]]["category_id"] == categories["Supermercado"]["id"]
    assert items[market["id"]]["category_status"] == "auto"


def test_delete_category_deletes_its_rules(gerard: TestClient) -> None:
    supermarket = _by_name(gerard)["Supermercado"]
    assert gerard.delete(f"/api/categories/{supermarket['id']}").status_code == 204
    patterns = {r["pattern"] for r in gerard.get("/api/rules").json()}
    assert "MERCADONA" not in patterns
    assert "BAR" in patterns


def test_isolation(gerard: TestClient, padres: TestClient) -> None:
    gerard_ids = {c["id"] for c in gerard.get("/api/categories").json()}
    padres_ids = {c["id"] for c in padres.get("/api/categories").json()}
    assert gerard_ids.isdisjoint(padres_ids)

    target = next(iter(gerard_ids))
    assert padres.patch(f"/api/categories/{target}", json={"name": "Hack"}).status_code == 404
    assert padres.delete(f"/api/categories/{target}").status_code == 404
    assert len(gerard.get("/api/categories").json()) == len(DEFAULT_CATEGORIES)

    # Dos usuarios pueden tener una categoría con el mismo nombre
    body = {"name": "Mascotas", "kind": "expense"}
    assert gerard.post("/api/categories", json=body).status_code == 201
    assert padres.post("/api/categories", json=body).status_code == 201
