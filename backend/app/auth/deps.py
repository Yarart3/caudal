"""Dependencias de FastAPI para proteger los endpoints."""

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.sessions import SESSION_COOKIE, get_user_by_token
from app.db import get_db
from app.models import User


def current_user(
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    """El usuario de la sesión. Si no hay sesión válida, responde 401."""
    user = get_user_by_token(db, token) if token else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Inicia sesión para continuar"
        )
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Solo para el administrador"
        )
    return user
