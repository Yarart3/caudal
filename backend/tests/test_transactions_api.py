"""Fase 1c, parte 1.2: GET, PATCH y DELETE de /api/transactions."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def gerard(login) -> TestClient:
    return login("gerard", is_admin=True)


@pytest.fixture
def padres(login) -> TestClient:
    return login("padres", color="#3555A0")


def _account(client: TestClient, name: str, import_format: str | None = None) -> int:
    body = {"name": name, "kind": "spending", "import_format": import_format}
    res = client.post("/api/accounts", json=body)
    assert res.status_code == 201
    return res.json()["id"]


def _upload(client: TestClient, account: int, data: bytes) -> dict:
    res = client.post(
        "/api/imports", data={"account_id": str(account)}, files={"file": ("x.xlsx", data, XLSX)}
    )
    assert res.status_code == 200
    return res.json()


def _tx(
    client: TestClient, account: int, description: str, amount: str = "-5.00", day="2026-09-26"
):
    body = {"account_id": account, "date": day, "description": description, "amount": amount}
    res = client.post("/api/transactions", json=body)
    assert res.status_code == 201
    return res.json()


def _category(client: TestClient, name: str) -> int:
    return next(c["id"] for c in client.get("/api/categories").json() if c["name"] == name)


def _list(client: TestClient, **params) -> dict:
    res = client.get("/api/transactions", params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _descriptions(page: dict) -> list[str]:
    return [t["description"] for t in page["items"]]


@pytest.fixture
def imported(gerard: TestClient) -> dict[str, int]:
    """imagin + Wise de samples/ importados (con la transferencia emparejada)."""
    accounts = {
        "imagin": _account(gerard, "imagin", "imagin"),
        "wise": _account(gerard, "Wise", "wise"),
    }
    _upload(gerard, accounts["wise"], WISE)
    _upload(gerard, accounts["imagin"], IMAGIN)
    return accounts


# ---------- GET ----------


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/transactions").status_code == 401
    assert client.patch("/api/transactions/1", json={}).status_code == 401
    assert client.delete("/api/transactions/1").status_code == 401


def test_list_newest_first(gerard: TestClient, imported: dict[str, int]) -> None:
    page = _list(gerard)
    assert page["total"] == 12  # 8 de imagin + 4 de Wise
    dates = [t["date"] for t in page["items"]]
    assert dates == sorted(dates, reverse=True)


def test_filter_by_month(gerard: TestClient) -> None:
    account = _account(gerard, "Efectivo")
    _tx(gerard, account, "AGOSTO", day="2026-08-31")
    _tx(gerard, account, "SEPTIEMBRE", day="2026-09-01")
    _tx(gerard, account, "DICIEMBRE", day="2026-12-31")
    _tx(gerard, account, "ENERO", day="2027-01-01")
    assert _descriptions(_list(gerard, month="2026-09")) == ["SEPTIEMBRE"]
    assert _descriptions(_list(gerard, month="2026-12")) == ["DICIEMBRE"]
    for bad in ("2026-13", "2026-9", "septiembre"):
        res = gerard.get("/api/transactions", params={"month": bad})
        assert res.status_code == 422
        assert res.json()["detail"] == "El mes tiene que ser AAAA-MM"


def test_search_in_description_and_category(gerard: TestClient, imported: dict[str, int]) -> None:
    assert sorted(_descriptions(_list(gerard, q="mercadona"))) == ["MERCADONA", "MERCADONA"]
    # «super» encaja con la categoría Supermercado (MERCADONA ×2, BON AREA) y con el concepto
    # de Wise «Supermercado Ejemplo CIUDAD»
    assert _list(gerard, q="super")["total"] == 4
    # Los comodines de LIKE se buscan como texto normal
    assert _list(gerard, q="%")["total"] == 0
    assert _list(gerard, q="_")["total"] == 0


def test_filter_by_status(gerard: TestClient, imported: dict[str, int]) -> None:
    internal = _list(gerard, status="internal")
    # Las dos patas de imagin → Wise (en Wise el concepto es el nombre del pagador)
    assert sorted(_descriptions(internal)) == ["Nombre Ejemplo", "enviament de dine"]
    assert internal["total"] == 2
    review = _list(gerard, status="review")
    assert all(not t["is_internal_transfer"] for t in review["items"])
    auto = _list(gerard, status="auto")
    assert all(t["category_id"] is not None for t in auto["items"])  # sin las internas
    assert internal["total"] + review["total"] + auto["total"] == 12
    assert _list(gerard, status="manual")["total"] == 0
    assert gerard.get("/api/transactions", params={"status": "otro"}).status_code == 422


def test_filter_by_category_and_account(gerard: TestClient, imported: dict[str, int]) -> None:
    supermarket = _category(gerard, "Supermercado")
    assert sorted(_descriptions(_list(gerard, category=supermarket))) == [
        "BON AREA",
        "MERCADONA",
        "MERCADONA",
    ]
    assert _list(gerard, account=imported["wise"])["total"] == 4


def test_limit_offset_and_count_only(gerard: TestClient, imported: dict[str, int]) -> None:
    first = _list(gerard, limit=5)
    second = _list(gerard, limit=5, offset=5)
    assert (len(first["items"]), first["total"]) == (5, 12)
    assert not {t["id"] for t in first["items"]} & {t["id"] for t in second["items"]}
    only_total = _list(gerard, status="review", limit=0)
    assert only_total["items"] == []
    assert only_total["total"] > 0
    assert gerard.get("/api/transactions", params={"limit": 1001}).status_code == 422


# ---------- PATCH ----------


def test_set_category_is_manual_and_null_goes_to_review(gerard: TestClient) -> None:
    account = _account(gerard, "Efectivo")
    tx = _tx(gerard, account, "MERCADONA")
    assert tx["category_status"] == "auto"
    clothes = _category(gerard, "Ropa")

    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"category_id": clothes})
    assert (res.json()["category_id"], res.json()["category_status"]) == (clothes, "manual")

    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"category_id": None})
    # Vuelve a por revisar… y la regla MERCADONA lo recoge otra vez
    assert res.json()["category_status"] == "auto"
    assert res.json()["category_id"] == _category(gerard, "Supermercado")


def test_edit_fields_and_rules_on_new_description(gerard: TestClient) -> None:
    account = _account(gerard, "Efectivo")
    other = _account(gerard, "Hucha")
    tx = _tx(gerard, account, "COMPRA RARA")
    assert tx["category_status"] == "review"
    body = {"description": "Netflix", "amount": "-12.99", "date": "2026-09-30", "account_id": other}
    res = gerard.patch(f"/api/transactions/{tx['id']}", json=body).json()
    assert (res["description"], res["amount"], res["date"], res["account_id"]) == (
        "Netflix",
        "-12.99",
        "2026-09-30",
        other,
    )
    assert res["category_id"] == _category(gerard, "Suscripciones")
    for bad in ({"amount": "-1.999"}, {"description": "  "}, {"date": None}, {"amount": None}):
        assert gerard.patch(f"/api/transactions/{tx['id']}", json=bad).status_code == 422


def test_toggle_internal_transfer(gerard: TestClient) -> None:
    account = _account(gerard, "Efectivo")
    tx = _tx(gerard, account, "PASO A LA HUCHA")
    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"is_internal_transfer": True}).json()
    assert (res["is_internal_transfer"], res["category_status"]) == (True, "auto")
    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"is_internal_transfer": False}).json()
    assert (res["is_internal_transfer"], res["category_status"]) == (False, "review")


def test_edited_import_survives_reimport(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    _upload(gerard, imagin, IMAGIN)
    tx = _list(gerard, q="BON AREA")["items"][0]
    gerard.patch(f"/api/transactions/{tx['id']}", json={"description": "Bonàrea Lleida"})
    assert _upload(gerard, imagin, IMAGIN)["new"] == 0
    assert _list(gerard, q="Bonàrea")["total"] == 1


# ---------- DELETE ----------


def test_delete(gerard: TestClient) -> None:
    account = _account(gerard, "Efectivo")
    tx = _tx(gerard, account, "BORRAME")
    assert gerard.delete(f"/api/transactions/{tx['id']}").status_code == 204
    assert gerard.delete(f"/api/transactions/{tx['id']}").status_code == 404
    assert _list(gerard)["total"] == 0


# ---------- aislamiento ----------


def test_isolation(gerard: TestClient, padres: TestClient, imported: dict[str, int]) -> None:
    assert _list(padres)["total"] == 0
    assert _list(padres, account=imported["imagin"])["total"] == 0
    tx = _list(gerard)["items"][0]

    assert (
        padres.patch(f"/api/transactions/{tx['id']}", json={"description": "X"}).status_code == 404
    )
    assert padres.delete(f"/api/transactions/{tx['id']}").status_code == 404
    assert _list(gerard)["total"] == 12

    # No se puede mover un movimiento a la cuenta de otro ni ponerle su categoría
    padres_account = _account(padres, "Efectivo")
    padres_category = _category(padres, "Ropa")
    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"account_id": padres_account})
    assert res.status_code == 404
    res = gerard.patch(f"/api/transactions/{tx['id']}", json={"category_id": padres_category})
    assert res.status_code == 404
    assert _list(padres)["total"] == 0
