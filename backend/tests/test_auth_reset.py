"""Restablecer contraseña desde la terminal (app/auth/reset.py)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.auth import reset
from app.auth.reset import ResetError, reset_password
from app.auth.security import verify_password
from app.models import User, UserSession


def test_cambia_la_contrasena_desbloquea_y_cierra_sesiones(db, login):
    client = login("padres")
    user = db.scalar(select(User).where(User.username == "padres"))
    user.failed_attempts = 5
    user.locked_until = datetime.now(UTC) + timedelta(minutes=5)
    db.commit()
    assert db.scalar(select(func.count()).select_from(UserSession)) == 1

    reset_password(db, "padres", "nueva-clave-123")

    db.refresh(user)
    assert verify_password(user.password_hash, "nueva-clave-123")
    assert user.failed_attempts == 0
    assert user.locked_until is None
    assert db.scalar(select(func.count()).select_from(UserSession)) == 0
    assert client.get("/api/auth/me").status_code == 401  # la sesión abierta ya no vale
    res = client.post("/api/auth/login", json={"username": "padres", "password": "nueva-clave-123"})
    assert res.status_code == 200


def test_solo_toca_a_ese_usuario(db, login):
    login("gerard")
    login("padres")
    reset_password(db, "padres", "nueva-clave-123")
    gerard = db.scalar(select(User).where(User.username == "gerard"))
    assert verify_password(gerard.password_hash, "contrasena-de-prueba")
    assert db.scalar(select(func.count()).select_from(UserSession)) == 1  # la de gerard


def test_usuario_que_no_existe(db):
    with pytest.raises(ResetError, match="No existe"):
        reset_password(db, "nadie", "nueva-clave-123")


def test_contrasena_corta(db, make_user):
    make_user("padres")
    with pytest.raises(ResetError, match="al menos"):
        reset_password(db, "padres", "corta")


def test_terminal_pide_dos_veces(db, make_user, monkeypatch, capsys):
    make_user("padres")
    answers = iter(["nueva-clave-123", "nueva-clave-123"])
    monkeypatch.setattr(reset, "_ask_secret", lambda _: next(answers))
    assert reset.main(["padres"]) == 0
    assert "cambiada" in capsys.readouterr().out
    user = db.scalar(select(User).where(User.username == "padres"))
    db.refresh(user)
    assert verify_password(user.password_hash, "nueva-clave-123")


def test_terminal_no_coinciden(db, make_user, monkeypatch, capsys):
    make_user("padres")
    answers = iter(["nueva-clave-123", "otra-clave-456"])
    monkeypatch.setattr(reset, "_ask_secret", lambda _: next(answers))
    assert reset.main(["padres"]) == 1
    assert "no coinciden" in capsys.readouterr().out


def test_terminal_usuario_desconocido(make_user, capsys):
    make_user("gerard")
    assert reset.main(["nadie"]) == 1
    assert "no existe" in capsys.readouterr().out


def test_terminal_sin_usuarios(capsys):
    assert reset.main(["gerard"]) == 1
    assert "asistente" in capsys.readouterr().out
