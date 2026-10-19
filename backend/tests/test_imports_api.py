"""POST /api/imports y POST /api/transactions (Fase 1b, parte 1.4)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.imports import MAX_BYTES
from app.main import app
from app.models import Account, Transaction

TEST_PASSWORD = "contrasena-de-prueba"  # la que pone make_user por defecto
SAMPLES = Path(__file__).resolve().parents[2] / "samples"
IMAGIN = (SAMPLES / "imagin_ejemplo.xlsx").read_bytes()
WISE = (SAMPLES / "wise_ejemplo.xlsx").read_bytes()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _logged_client(username: str) -> TestClient:
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert res.status_code == 200
    return client


@pytest.fixture
def gerard(make_user) -> TestClient:
    make_user("gerard", is_admin=True)
    return _logged_client("gerard")


@pytest.fixture
def padres(make_user) -> TestClient:
    make_user("padres", color="#3555A0")
    return _logged_client("padres")


def _account(client: TestClient, name: str, import_format: str | None) -> int:
    body = {"name": name, "kind": "spending", "import_format": import_format}
    res = client.post("/api/accounts", json=body)
    assert res.status_code == 201
    return res.json()["id"]


def _upload(client: TestClient, account_id: int, data: bytes, name: str = "extracto.xlsx"):
    return client.post(
        "/api/imports", data={"account_id": str(account_id)}, files={"file": (name, data, XLSX)}
    )


def _count(db: Session, account_id: int) -> int:
    return db.scalar(select(func.count()).where(Transaction.account_id == account_id))


# ---------- POST /api/imports ----------


def test_import_requires_login(client: TestClient) -> None:
    assert _upload(client, 1, IMAGIN).status_code == 401


def test_import_and_reimport(gerard: TestClient, db: Session) -> None:
    imagin = _account(gerard, "imagin", "imagin")

    res = _upload(gerard, imagin, IMAGIN)
    assert res.status_code == 200
    body = res.json()
    assert {k: body[k] for k in ("read", "new", "duplicates", "review", "internal")} == {
        "read": 8,
        "new": 8,
        "duplicates": 0,
        "review": 8,
        "internal": 0,
    }
    assert body["errors"] == [] and body["warnings"] == []
    assert (body["closing_balance"], body["closing_date"]) == ("67.23", "2026-09-29")

    again = _upload(gerard, imagin, IMAGIN).json()
    assert (again["new"], again["duplicates"]) == (0, 8)
    assert _count(db, imagin) == 8
    # El saldo de referencia de la cuenta queda actualizado
    account = gerard.get(f"/api/accounts/{imagin}").json()
    assert (account["reference_balance"], account["reference_balance_date"]) == (
        "67.23",
        "2026-09-29",
    )


def test_import_marks_internal_transfer(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    wise = _account(gerard, "Wise", "wise")
    _upload(gerard, imagin, IMAGIN)

    body = _upload(gerard, wise, WISE).json()
    assert (body["new"], body["internal"], body["review"]) == (4, 1, 3)


def test_wrong_bank_message(gerard: TestClient, db: Session) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    res = _upload(gerard, imagin, WISE)
    assert res.status_code == 422
    assert res.json() == {
        "detail": "Este archivo parece de Wise, pero has elegido una cuenta de imagin"
    }
    assert _count(db, imagin) == 0


def test_not_an_excel_and_empty(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    res = _upload(gerard, imagin, b"Concepto;Fecha\n", name="extracto.csv")
    assert (res.status_code, res.json()["detail"]) == (
        422,
        "El archivo no es un Excel (.xlsx) válido",
    )
    res = _upload(gerard, imagin, b"")
    assert (res.status_code, res.json()["detail"]) == (422, "El archivo está vacío")


def test_too_big(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    res = _upload(gerard, imagin, b"0" * (MAX_BYTES + 1))
    assert res.status_code == 413
    assert res.json()["detail"] == "El archivo es demasiado grande (máximo 5 MB)"


def test_manual_account_cannot_import(gerard: TestClient) -> None:
    cash = _account(gerard, "Efectivo", None)
    res = _upload(gerard, cash, IMAGIN)
    assert res.status_code == 422
    assert "no tiene banco asociado" in res.json()["detail"]


def test_missing_fields(gerard: TestClient) -> None:
    res = gerard.post("/api/imports", data={"account_id": "1"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Datos no válidos: revisa file"}


def test_cannot_import_into_other_users_account(
    gerard: TestClient, padres: TestClient, db: Session
) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    res = _upload(padres, imagin, IMAGIN)
    assert res.status_code == 404
    assert res.json() == {"detail": "Cuenta no encontrada"}
    assert _count(db, imagin) == 0


# ---------- POST /api/transactions (alta manual) ----------


def test_add_manual_transaction(gerard: TestClient, db: Session) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    body = {
        "account_id": imagin,
        "date": "2026-09-26",
        "description": " BON AREA ",
        "amount": "-1.90",
    }
    res = gerard.post("/api/transactions", json=body)
    assert res.status_code == 201
    created = res.json()
    assert {k: created[k] for k in ("date", "description", "amount", "category_status")} == {
        "date": "2026-09-26",
        "description": "BON AREA",
        "amount": "-1.90",
        "category_status": "review",
    }
    assert created["is_internal_transfer"] is False
    tx = db.get(Transaction, created["id"])
    assert tx.fingerprint is None


def test_manual_transaction_validation(gerard: TestClient) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    base = {"account_id": imagin, "date": "2026-09-26", "description": "X", "amount": "-1.90"}
    for bad in ({"amount": "-1.999"}, {"description": "  "}, {"date": "26/09/2026"}):
        assert gerard.post("/api/transactions", json={**base, **bad}).status_code == 422


def test_manual_income_pairs_with_imagin_transfer(gerard: TestClient) -> None:
    """Ingreso apuntado a mano en Trade Republic ↔ salida de imagin del mismo día."""
    imagin = _account(gerard, "imagin", "imagin")
    trade = _account(gerard, "Trade Republic", None)
    _upload(gerard, imagin, IMAGIN)  # trae «enviament de dine» -50,00 el 27/09

    body = {"account_id": trade, "date": "2026-09-27", "description": "Ingreso", "amount": "50.00"}
    created = gerard.post("/api/transactions", json=body).json()
    assert created["is_internal_transfer"] is True


def test_cannot_add_transaction_to_other_users_account(
    gerard: TestClient, padres: TestClient, db: Session
) -> None:
    imagin = _account(gerard, "imagin", "imagin")
    body = {"account_id": imagin, "date": "2026-09-26", "description": "X", "amount": "-1.00"}
    res = padres.post("/api/transactions", json=body)
    assert res.status_code == 404
    assert _count(db, imagin) == 0
    assert db.scalar(select(func.count()).select_from(Account)) == 1
