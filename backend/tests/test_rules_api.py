"""Fase 1c, parte 1.2: /api/rules y el flujo «¿Aplicar siempre a 'X'?»."""

import pytest
from fastapi.testclient import TestClient

from app.categories.seed import DEFAULT_RULES, PRIORITY_REVIEW, PRIORITY_USER


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _category(client: TestClient, name: str) -> int:
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def _account(client: TestClient) -> int:
    body = {"name": "Efectivo", "kind": "spending", "import_format": None}
    return client.post("/api/accounts", json=body).json()["id"]


def _tx(client: TestClient, account: int, description: str) -> dict:
    body = {
        "account_id": account,
        "date": "2026-09-26",
        "description": description,
        "amount": "-5.00",
    }
    return client.post("/api/transactions", json=body).json()


def _get_tx(client: TestClient, tx_id: int) -> dict:
    return next(t for t in client.get("/api/transactions").json()["items"] if t["id"] == tx_id)


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/rules").status_code == 401
    assert client.post("/api/rules/apply").status_code == 401


def test_list_in_engine_order(gerard: TestClient) -> None:
    rules = gerard.get("/api/rules").json()
    assert len(rules) == len(DEFAULT_RULES)
    # Primero las de Bizum (prioridad 10)
    assert {r["pattern"] for r in rules[:2]} == {"BIZUM ENVIAT", "BIZUM REBUT"}
    assert all(r["category_id"] is None for r in rules[:2])


def test_apply_always_flow(gerard: TestClient) -> None:
    """Cambio la categoría de uno → «¿Aplicar siempre?» → se crea la regla y los pendientes
    con ese concepto se categorizan. Los que puse a mano no se tocan."""
    account = _account(gerard)
    first = _tx(gerard, account, "Bon Preu Lleida")
    second = _tx(gerard, account, "BON PREU LLEIDA")
    other = _tx(gerard, account, "BON PREU TARREGA")
    assert first["category_status"] == "review"
    supermarket = _category(gerard, "Supermercado")

    gerard.patch(f"/api/transactions/{first['id']}", json={"category_id": supermarket})
    res = gerard.post("/api/rules", json={"pattern": "bon preu", "category_id": supermarket})
    assert res.status_code == 200
    saved = res.json()
    assert saved["rule"]["pattern"] == "BON PREU"  # se guarda normalizado
    assert saved["rule"]["priority"] == PRIORITY_USER
    assert saved["rule"]["created_by"] == "user"
    assert (saved["replaced"], saved["categorized"]) == (False, 2)

    assert _get_tx(gerard, first["id"])["category_status"] == "manual"
    for tx in (second, other):
        got = _get_tx(gerard, tx["id"])
        assert (got["category_id"], got["category_status"]) == (supermarket, "auto")


def test_save_replaces_same_pattern(gerard: TestClient) -> None:
    """«BAR» ya existe (sistema → Comida fuera). Guardarla otra vez la sustituye, sin
    duplicar."""
    leisure = _category(gerard, "Ocio y salidas")
    res = gerard.post("/api/rules", json={"pattern": " bar ", "category_id": leisure}).json()
    assert res["replaced"] is True
    bars = [r for r in gerard.get("/api/rules").json() if r["pattern"] == "BAR"]
    assert len(bars) == 1
    assert (bars[0]["category_id"], bars[0]["created_by"]) == (leisure, "user")


def test_save_without_category_leaves_for_review(gerard: TestClient) -> None:
    res = gerard.post("/api/rules", json={"pattern": "TRANSFERENCIA", "category_id": None})
    assert res.json()["rule"]["priority"] == PRIORITY_REVIEW
    account = _account(gerard)
    tx = _tx(gerard, account, "TRANSFERENCIA BAR PEPE")
    assert tx["category_status"] == "review"


def test_save_without_apply(gerard: TestClient) -> None:
    account = _account(gerard)
    tx = _tx(gerard, account, "FARMACIA CENTRAL")
    health = _category(gerard, "Salud")
    res = gerard.post(
        "/api/rules", json={"pattern": "FARMACIA", "category_id": health, "apply": False}
    )
    assert res.json()["categorized"] == 0
    assert _get_tx(gerard, tx["id"])["category_status"] == "review"

    applied = gerard.post("/api/rules/apply").json()
    assert applied == {"categorized": 1, "review": 0}


def test_update_and_delete(gerard: TestClient) -> None:
    rule = next(r for r in gerard.get("/api/rules").json() if r["pattern"] == "RENFE")
    res = gerard.patch(
        f"/api/rules/{rule['id']}", json={"pattern": "renfe viajeros", "priority": 20}
    )
    assert (res.json()["pattern"], res.json()["priority"]) == ("RENFE VIAJEROS", 20)
    assert (
        gerard.patch(f"/api/rules/{rule['id']}", json={"category_id": None}).json()["category_id"]
        is None
    )
    for bad in ({"pattern": "   "}, {"pattern": None}, {"priority": 0}, {"priority": None}):
        assert gerard.patch(f"/api/rules/{rule['id']}", json=bad).status_code == 422
    assert gerard.delete(f"/api/rules/{rule['id']}").status_code == 204
    assert gerard.delete(f"/api/rules/{rule['id']}").status_code == 404


def test_reapply_including_auto_fixes_wrong_rule(gerard: TestClient) -> None:
    """Una regla mal puesta categoriza mal; tras corregirla, «Reaplicar» con include_auto
    arregla los automáticos y deja en paz los manuales."""
    account = _account(gerard)
    wrong = _tx(gerard, account, "BAR PEPE")  # auto → Comida fuera
    manual = _tx(gerard, account, "BAR LA PLAZA")
    clothes = _category(gerard, "Ropa")
    gerard.patch(f"/api/transactions/{manual['id']}", json={"category_id": clothes})

    bar = next(r for r in gerard.get("/api/rules").json() if r["pattern"] == "BAR")
    leisure = _category(gerard, "Ocio y salidas")
    gerard.patch(f"/api/rules/{bar['id']}", json={"category_id": leisure})

    assert gerard.post("/api/rules/apply").json()["categorized"] == 0  # solo pendientes
    assert gerard.post("/api/rules/apply?include_auto=true").json()["categorized"] == 1
    assert _get_tx(gerard, wrong["id"])["category_id"] == leisure
    assert _get_tx(gerard, manual["id"])["category_id"] == clothes

    # Si la regla desaparece, el automático vuelve a «por revisar»
    gerard.delete(f"/api/rules/{bar['id']}")
    applied = gerard.post("/api/rules/apply?include_auto=true").json()
    assert applied == {"categorized": 0, "review": 1}
    assert _get_tx(gerard, wrong["id"])["category_status"] == "review"


def test_validation(gerard: TestClient) -> None:
    supermarket = _category(gerard, "Supermercado")
    for body in (
        {"pattern": "", "category_id": supermarket},
        {"pattern": "  ", "category_id": supermarket},
        {"pattern": "X" * 121, "category_id": supermarket},
        {"pattern": "X"},  # category_id es obligatorio (aunque sea null)
    ):
        assert gerard.post("/api/rules", json=body).status_code == 422
    assert (
        gerard.post("/api/rules", json={"pattern": "X", "category_id": 999999}).status_code == 404
    )


def test_isolation(gerard: TestClient, padres: TestClient) -> None:
    gerard_rule = gerard.get("/api/rules").json()[0]
    padres_category = _category(padres, "Ropa")

    assert padres.patch(f"/api/rules/{gerard_rule['id']}", json={"priority": 1}).status_code == 404
    assert padres.delete(f"/api/rules/{gerard_rule['id']}").status_code == 404
    # No se puede apuntar una regla a la categoría de otro usuario
    res = gerard.post("/api/rules", json={"pattern": "ZARA", "category_id": padres_category})
    assert res.status_code == 404
    res = gerard.patch(f"/api/rules/{gerard_rule['id']}", json={"category_id": padres_category})
    assert res.status_code == 404

    # Reaplicar las reglas de gerard no toca los movimientos de padres
    account = _account(padres)
    tx = _tx(padres, account, "ZARA LLEIDA")
    gerard.post("/api/rules", json={"pattern": "ZARA", "category_id": _category(gerard, "Ropa")})
    gerard.post("/api/rules/apply")
    assert _get_tx(padres, tx["id"])["category_status"] == "review"
    assert len(padres.get("/api/rules").json()) == len(DEFAULT_RULES)
