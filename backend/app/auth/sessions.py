"""Sesiones guardadas en la BD, con caducidad por inactividad."""

from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import hash_token, new_session_token
from app.config import get_settings
from app.models import User, UserSession

SESSION_COOKIE = "caudal_session"


def _timeout() -> timedelta:
    return timedelta(minutes=get_settings().session_timeout_min)


def create_session(db: Session, user: User) -> str:
    """Crea una sesión y devuelve el token (va en la cookie; en la BD solo queda su hash)."""
    now = datetime.now(UTC)
    # De paso, limpia las sesiones caducadas de todos los usuarios
    db.execute(delete(UserSession).where(UserSession.last_seen_at < now - _timeout()))
    token = new_session_token()
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token), last_seen_at=now))
    db.commit()
    return token


def get_user_by_token(db: Session, token: str) -> User | None:
    """Devuelve el usuario de la sesión, o None si no existe o ha caducado.

    Cada uso válido renueva la sesión (last_seen_at = ahora): caduca por inactividad.
    """
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None:
        return None
    now = datetime.now(UTC)
    if now - session.last_seen_at > _timeout():
        db.delete(session)
        db.commit()
        return None
    session.last_seen_at = now
    db.commit()
    return session.user


def delete_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    db.commit()


def set_session_cookie(response: Response, token: str) -> None:
    # Sin "secure": la app va por HTTP en la red de casa y el navegador no enviaría la cookie.
    # Sin max_age: es una cookie de sesión; la caducidad la controla el servidor.
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="strict", secure=False, path="/"
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="strict", path="/")
