"""Parte 2.4: cuentas del usuario y aislamiento entre usuarios."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Account, User

TEST_PASSWORD = "contrasena-de-prueba"  # la que pone make_user por defecto

IMAGIN = {
    "name": "imagin",
    "kind": "spending",
    "import_format": "imagin",
    "reference_balance": "1234.50",
    "reference_balance_date": "2026-09-30",
}


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


def test_accounts_require_login(client):
    assert client.get("/api/accounts").status_code == 401
    assert client.post("/api/accounts", json=IMAGIN).status_code == 401


def test_create_and_list(gerard):
    res = gerard.post("/api/accounts", json=IMAGIN)
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == "imagin"
    assert created["kind"] == "spending"
    assert created["liquidity_type"] == "cash"
    # El dinero viaja como texto, con sus dos decimales
    assert created["reference_balance"] == "1234.50"
    assert created["reference_balance_date"] == "2026-09-30"

    gerard.post("/api/accounts", json={"name": "Wise", "kind": "spending"})
    names = [a["name"] for a in gerard.get("/api/accounts").json()]
    assert names == ["imagin", "Wise"]


def test_validation_messages(gerard):
    res = gerard.post("/api/accounts", json={"name": "X", "kind": "ahorro"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Datos no válidos: revisa kind"}

    res = gerard.post("/api/accounts", json={"name": "   ", "kind": "spending"})
    assert res.status_code == 422

    res = gerard.post(
        "/api/accounts", json={"name": "X", "kind": "spending", "reference_balance": "10.00"}
    )
    assert res.status_code == 422
    assert res.json() == {"detail": "El saldo de referencia y su fecha van juntos"}

    res = gerard.post(
        "/api/accounts",
        json={**IMAGIN, "reference_balance": "10.123"},  # más de 2 decimales
    )
    assert res.status_code == 422


def test_duplicate_name_is_per_user(gerard, padres):
    assert gerard.post("/api/accounts", json=IMAGIN).status_code == 201
    res = gerard.post("/api/accounts", json=IMAGIN)
    assert res.status_code == 409
    assert res.json() == {"detail": "Ya tienes una cuenta con ese nombre"}
    # Otro usuario sí puede tener una cuenta con el mismo nombre
    assert padres.post("/api/accounts", json=IMAGIN).status_code == 201


def test_update_account(gerard):
    account_id = gerard.post("/api/accounts", json=IMAGIN).json()["id"]

    res = gerard.patch(f"/api/accounts/{account_id}", json={"reference_balance": "99.90"})
    assert res.status_code == 200
    assert res.json()["reference_balance"] == "99.90"
    assert res.json()["reference_balance_date"] == "2026-09-30"  # no se ha tocado

    res = gerard.patch(
        f"/api/accounts/{account_id}",
        json={"reference_balance": None, "reference_balance_date": None},
    )
    assert res.json()["reference_balance"] is None

    res = gerard.patch(f"/api/accounts/{account_id}", json={"reference_balance": "5.00"})
    assert res.status_code == 422
    assert res.json() == {"detail": "El saldo de referencia y su fecha van juntos"}

    res = gerard.patch(f"/api/accounts/{account_id}", json={"name": None})
    assert res.status_code == 422


# --- Aislamiento: cada usuario solo ve y toca lo suyo ---


def test_user_cannot_see_or_modify_other_users_accounts(gerard, padres, db):
    account_id = gerard.post("/api/accounts", json=IMAGIN).json()["id"]

    # padres no la ve en su lista…
    assert padres.get("/api/accounts").json() == []
    # …ni puede pedirla ni cambiarla: 404, como si no existiera
    res = padres.get(f"/api/accounts/{account_id}")
    assert res.status_code == 404
    assert res.json() == {"detail": "Cuenta no encontrada"}
    res = padres.patch(f"/api/accounts/{account_id}", json={"name": "Robada"})
    assert res.status_code == 404

    # La cuenta de gerard sigue intacta
    account = db.scalar(select(Account).where(Account.id == account_id))
    assert account.name == "imagin"
    assert gerard.get(f"/api/accounts/{account_id}").status_code == 200


def test_created_account_belongs_to_the_session_user(gerard, padres, db):
    gerard_id = db.scalar(select(User.id).where(User.username == "gerard"))
    padres_id = db.scalar(select(User.id).where(User.username == "padres"))
    # Aunque se intente colar el user_id de gerard en el JSON, se ignora: manda la sesión
    res = padres.post("/api/accounts", json={**IMAGIN, "user_id": gerard_id})
    assert res.status_code == 201
    owner = db.scalar(select(Account.user_id).where(Account.id == res.json()["id"]))
    assert owner == padres_id
    assert gerard.get("/api/accounts").json() == []
