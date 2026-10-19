"""Inicio de sesión: tarjetas de "¿Quién entra?", login, logout y el usuario actual."""

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.security import hash_password, verify_password
from app.auth.sessions import (
    SESSION_COOKIE,
    clear_session_cookie,
    create_session,
    delete_session,
    set_session_cookie,
)
from app.config import get_settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

WRONG_CREDENTIALS = "Usuario o contraseña incorrectos"

# Hash de una contraseña cualquiera. Si el usuario no existe se verifica contra él, para que
# la respuesta tarde lo mismo y no se pueda adivinar qué usuarios existen por el tiempo.
_DUMMY_HASH = hash_password("caudal-usuario-inexistente")


class UserCard(BaseModel):
    """Lo mínimo para las tarjetas de "¿Quién entra?" (sin datos sensibles)."""

    username: str
    display_name: str
    initial: str
    color: str


class Me(UserCard):
    is_admin: bool


class LoginRequest(BaseModel):
    username: str
    password: str


def _card(user: User) -> UserCard:
    return UserCard(
        username=user.username,
        display_name=user.display_name,
        initial=user.display_name[:1].upper(),
        color=user.color,
    )


def _me(user: User) -> Me:
    return Me(**_card(user).model_dump(), is_admin=user.is_admin)


def _locked_error(locked_until: datetime, now: datetime) -> HTTPException:
    minutes = max(1, math.ceil((locked_until - now).total_seconds() / 60))
    unit = "minuto" if minutes == 1 else "minutos"
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Demasiados intentos fallidos. Vuelve a probar en {minutes} {unit}",
    )


@router.get("/users")
def list_users(db: Session = Depends(get_db)) -> list[UserCard]:
    return [_card(u) for u in db.scalars(select(User).order_by(User.id))]


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> Me:
    settings = get_settings()
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.username == body.username))

    if user is None:
        verify_password(_DUMMY_HASH, body.password)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=WRONG_CREDENTIALS)

    # Bloqueado: no se comprueba la contraseña, ni siquiera si es la correcta
    if user.locked_until is not None and user.locked_until > now:
        raise _locked_error(user.locked_until, now)

    if not verify_password(user.password_hash, body.password):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.login_max_attempts:
            user.failed_attempts = 0
            user.locked_until = now + timedelta(minutes=settings.login_lockout_min)
            db.commit()
            raise _locked_error(user.locked_until, now)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=WRONG_CREDENTIALS)

    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    set_session_cookie(response, create_session(db, user))
    return _me(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> None:
    """Cierra la sesión. Funciona aunque ya hubiera caducado."""
    if token:
        delete_session(db, token)
    clear_session_cookie(response)


@router.get("/me")
def me(user: User = Depends(current_user)) -> Me:
    return _me(user)
