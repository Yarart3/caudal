"""Parte 2.2: asistente de primer arranque."""

from sqlalchemy import select

from app.auth.security import verify_password
from app.models import User

PASSWORDS = {"gerard_password": "clave-gerard-123", "padres_password": "clave-padres-123"}


def test_status_needs_setup_when_there_are_no_users(client):
    res = client.get("/api/setup/status")
    assert res.status_code == 200
    assert res.json() == {"needs_setup": True}


def test_setup_creates_gerard_admin_and_padres(client, db):
    res = client.post("/api/setup", json=PASSWORDS)
    assert res.status_code == 201
    assert res.json() == [
        {"username": "gerard", "display_name": "Gerard", "is_admin": True},
        {"username": "padres", "display_name": "Padres", "is_admin": False},
    ]

    users = {u.username: u for u in db.scalars(select(User))}
    assert set(users) == {"gerard", "padres"}
    assert users["gerard"].color == "#0E6B58"
    assert users["padres"].color == "#3555A0"
    # Se guarda el hash, nunca la contraseña
    assert users["gerard"].password_hash != "clave-gerard-123"
    assert verify_password(users["gerard"].password_hash, "clave-gerard-123")
    assert verify_password(users["padres"].password_hash, "clave-padres-123")

    assert client.get("/api/setup/status").json() == {"needs_setup": False}


def test_setup_only_works_once(client):
    assert client.post("/api/setup", json=PASSWORDS).status_code == 201
    res = client.post("/api/setup", json=PASSWORDS)
    assert res.status_code == 409
    assert res.json() == {"detail": "Caudal ya está configurado"}


def test_setup_rejects_short_passwords(client, db):
    res = client.post("/api/setup", json={**PASSWORDS, "padres_password": "corta"})
    assert res.status_code == 422
    assert res.json() == {"detail": "La contraseña de Padres debe tener al menos 8 caracteres"}
    assert db.scalars(select(User)).first() is None


def test_setup_requires_both_passwords(client):
    res = client.post("/api/setup", json={"gerard_password": "clave-gerard-123"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Datos no válidos: revisa padres_password"}
