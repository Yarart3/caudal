"""Fase 5, parte 5.2: deshacer una importación (GET /api/imports y DELETE /api/imports/{id})."""

from decimal import Decimal
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
    assert res.status_code == 200, res.text
    return res.json()


def _txs(client: TestClient, **params) -> list[dict]:
    res = client.get("/api/transactions", params=params)
    assert res.status_code == 200
    return res.json()["items"]


def _balance(client: TestClient, account: int) -> tuple[str | None, str | None]:
    body = client.get(f"/api/accounts/{account}").json()
    return body["reference_balance"], body["reference_balance_date"]


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/imports").status_code == 401
    assert client.delete("/api/imports/1").status_code == 401


def test_import_is_recorded_once(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    body = _upload(gerard, imagin, IMAGIN)
    assert body["import_id"] is not None

    # Reimportar lo mismo no trae nada nuevo: no queda registrado
    assert _upload(gerard, imagin, IMAGIN)["import_id"] is None

    records = gerard.get("/api/imports").json()
    assert len(records) == 1
    record = records[0]
    assert record["id"] == body["import_id"]
    assert record["account_id"] == imagin
    assert (record["new"], record["remaining"]) == (8, 8)
    assert record["last_date"] == "2026-09-29"
    assert record["first_date"] <= record["last_date"]


def test_undo_deletes_and_restores_balance(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    manual = gerard.post(
        "/api/transactions",
        json={"account_id": imagin, "date": "2026-09-01", "description": "A MANO", "amount": "-1"},
    ).json()
    import_id = _upload(gerard, imagin, IMAGIN)["import_id"]
    assert _balance(gerard, imagin) == ("67.23", "2026-09-29")

    res = gerard.delete(f"/api/imports/{import_id}")
    assert res.status_code == 200
    assert res.json() == {"deleted": 8, "unpaired": 0, "balance_restored": True}

    # Solo queda el apuntado a mano y el saldo vuelve a no tener referencia
    assert [t["id"] for t in _txs(gerard, account=imagin)] == [manual["id"]]
    assert _balance(gerard, imagin) == (None, None)
    assert gerard.get("/api/imports").json() == []
    assert gerard.delete(f"/api/imports/{import_id}").status_code == 404

    # Si se vuelve a importar, vuelve a entrar todo
    assert _upload(gerard, imagin, IMAGIN)["new"] == 8


def test_undo_also_deletes_edited_and_counts_remaining(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    import_id = _upload(gerard, imagin, IMAGIN)["import_id"]
    first, second = _txs(gerard, account=imagin)[:2]
    gerard.patch(f"/api/transactions/{first['id']}", json={"tags": ["editado"]})
    gerard.delete(f"/api/transactions/{second['id']}")
    assert gerard.get("/api/imports").json()[0]["remaining"] == 7

    assert gerard.delete(f"/api/imports/{import_id}").json()["deleted"] == 7
    assert _txs(gerard, account=imagin) == []


def test_balance_changed_later_is_kept(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    import_id = _upload(gerard, imagin, IMAGIN)["import_id"]
    res = gerard.patch(
        f"/api/accounts/{imagin}",
        json={"reference_balance": "100.00", "reference_balance_date": "2026-10-15"},
    )
    assert res.status_code == 200

    assert gerard.delete(f"/api/imports/{import_id}").json()["balance_restored"] is False
    assert _balance(gerard, imagin) == ("100.00", "2026-10-15")


def test_undo_unpairs_internal_transfer(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    wise = _account(gerard, "Wise", "wise")
    _upload(gerard, wise, WISE)
    body = _upload(gerard, imagin, IMAGIN)
    assert body["internal"] == 1
    wise_internal = _txs(gerard, account=wise, status="internal")
    assert len(wise_internal) == 1

    res = gerard.delete(f"/api/imports/{body['import_id']}").json()
    assert res["unpaired"] == 1

    # La otra pata (el ingreso en Wise) ya no es interna y vuelve a pasar por las reglas
    assert _txs(gerard, account=wise, status="internal") == []
    tx = next(t for t in _txs(gerard, account=wise) if t["id"] == wise_internal[0]["id"])
    assert tx["is_internal_transfer"] is False
    assert tx["category_status"] in ("review", "auto")


def test_undo_keeps_pair_when_ambiguous(gerard: TestClient) -> None:
    """Si la otra pata podría ser pareja de otro movimiento que se queda, no se toca."""
    imagin = _account(gerard, "imagin", "imagin")
    wise = _account(gerard, "Wise", "wise")
    _upload(gerard, wise, WISE)
    body = _upload(gerard, imagin, IMAGIN)
    pair = _txs(gerard, account=wise, status="internal")[0]
    # Otro envío igual, a mano en una tercera cuenta y marcado como interno
    cash = _account(gerard, "Efectivo")
    twin = gerard.post(
        "/api/transactions",
        json={
            "account_id": cash,
            "date": pair["date"],
            "description": "OTRO ENVIO",
            "amount": str(-Decimal(pair["amount"])),
        },
    ).json()
    gerard.patch(f"/api/transactions/{twin['id']}", json={"is_internal_transfer": True})

    assert gerard.delete(f"/api/imports/{body['import_id']}").json()["unpaired"] == 0
    assert len(_txs(gerard, account=wise, status="internal")) == 1


def test_filter_by_account(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    wise = _account(gerard, "Wise", "wise")
    _upload(gerard, imagin, IMAGIN)
    _upload(gerard, wise, WISE)
    assert len(gerard.get("/api/imports").json()) == 2
    only = gerard.get("/api/imports", params={"account_id": wise}).json()
    assert [r["account_id"] for r in only] == [wise]


def test_isolation(gerard: TestClient, padres: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    import_id = _upload(gerard, imagin, IMAGIN)["import_id"]
    assert padres.get("/api/imports").json() == []
    assert padres.get("/api/imports", params={"account_id": imagin}).json() == []
    assert padres.delete(f"/api/imports/{import_id}").status_code == 404
    assert len(_txs(gerard, account=imagin)) == 8
