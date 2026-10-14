"""Parte 2.1: contraseñas, tokens, sesiones y la dependencia current_user."""

from datetime import UTC, datetime, timedelta

from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.security import hash_password, hash_token, new_session_token, verify_password
from app.auth.sessions import (
    SESSION_COOKIE,
    create_session,
    delete_session,
    get_user_by_token,
    set_session_cookie,
)
from app.db import get_db
from app.models import User, UserSession

# --- Contraseñas ---


def test_password_hash_is_argon2_and_not_the_password():
    hashed = hash_password("mi-contrasena")
    assert hashed.startswith("$argon2id$")
    assert "mi-contrasena" not in hashed


def test_verify_password():
    hashed = hash_password("mi-contrasena")
    assert verify_password(hashed, "mi-contrasena")
    assert not verify_password(hashed, "otra")
    assert not verify_password("esto-no-es-un-hash", "mi-contrasena")


def test_same_password_gives_different_hashes():
    # Argon2 usa una sal aleatoria: dos hashes de la misma contraseña no coinciden
    assert hash_password("igual") != hash_password("igual")


# --- Tokens y sesiones ---


def test_tokens_are_random_and_only_the_hash_is_stored(db, make_user):
    assert new_session_token() != new_session_token()
    user = make_user("gerard")
    token = create_session(db, user)
    stored = db.scalar(select(UserSession.token_hash))
    assert stored == hash_token(token)
    assert stored != token


def test_get_user_by_token(db, make_user):
    user = make_user("gerard")
    token = create_session(db, user)
    assert get_user_by_token(db, token).id == user.id
    assert get_user_by_token(db, "token-inventado") is None


def test_session_expires_after_inactivity(db, make_user):
    user = make_user("gerard")
    token = create_session(db, user)
    session = db.scalar(select(UserSession))
    session.last_seen_at = datetime.now(UTC) - timedelta(minutes=31)
    db.commit()
    assert get_user_by_token(db, token) is None
    # La sesión caducada se borra
    assert db.scalar(select(func.count()).select_from(UserSession)) == 0


def test_activity_renews_the_session(db, make_user):
    user = make_user("gerard")
    token = create_session(db, user)
    session = db.scalar(select(UserSession))
    session.last_seen_at = datetime.now(UTC) - timedelta(minutes=29)
    db.commit()
    assert get_user_by_token(db, token) is not None
    db.refresh(session)
    assert datetime.now(UTC) - session.last_seen_at < timedelta(minutes=1)


def test_delete_session(db, make_user):
    user = make_user("gerard")
    token = create_session(db, user)
    delete_session(db, token)
    assert get_user_by_token(db, token) is None


# --- current_user en un endpoint (app mínima solo para el test) ---


def _app_with_protected_route() -> FastAPI:
    test_app = FastAPI()

    @test_app.get("/protegido")
    def protected(user: User = Depends(current_user)) -> dict[str, str]:
        return {"username": user.username}

    @test_app.post("/entrar/{user_id}")
    def enter(user_id: int, response: Response, db: Session = Depends(get_db)) -> dict[str, bool]:
        user = db.get(User, user_id)
        set_session_cookie(response, create_session(db, user))
        return {"ok": True}

    return test_app


def test_current_user_requires_a_valid_cookie(make_user):
    user = make_user("gerard")
    client = TestClient(_app_with_protected_route())

    res = client.get("/protegido")
    assert res.status_code == 401
    assert res.json() == {"detail": "Inicia sesión para continuar"}

    res = client.post(f"/entrar/{user.id}")
    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Secure" not in cookie

    res = client.get("/protegido")
    assert res.status_code == 200
    assert res.json() == {"username": "gerard"}
