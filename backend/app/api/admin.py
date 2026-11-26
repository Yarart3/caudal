"""Ajustes → Usuarios (Fase 4): crear, editar, desactivar y restablecer la contraseña.

Solo para el administrador (403 para los demás). Un usuario no se borra nunca desde aquí: se
desactiva, deja de salir en «¿Quién entra?», se cierran sus sesiones y sus datos se quedan.
El administrador no puede desactivarse ni quitarse el permiso a sí mismo: así siempre queda
al menos un administrador activo.
"""

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.setup import MIN_PASSWORD_LENGTH
from app.auth.deps import admin_user
from app.auth.reset import ResetError, reset_password
from app.auth.security import hash_password
from app.categories import seed_user_defaults
from app.db import get_db
from app.models import User, UserSession

router = APIRouter(prefix="/api/admin/users", tags=["admin"])

# Nombre de usuario: minúsculas, números, punto, guion y guion bajo (se escribe al entrar)
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,39}$")
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
DEFAULT_COLOR = "#5B616B"


class AdminUser(BaseModel):
    id: int
    username: str
    display_name: str
    initial: str
    color: str
    is_admin: bool
    is_active: bool
    locked: bool  # bloqueado ahora por intentos fallidos
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    display_name: DisplayName
    color: Color = DEFAULT_COLOR
    password: str
    is_admin: bool = False

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        value = value.strip().lower()
        if not USERNAME_RE.fullmatch(value):
            raise ValueError(
                "El usuario tiene que tener de 2 a 40 letras sin acentos, números, «.», «-» o «_»"
            )
        return value


class UserUpdate(BaseModel):
    display_name: DisplayName | None = None
    color: Color | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    password: str


def _out(user: User) -> AdminUser:
    now = datetime.now(UTC)
    return AdminUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        initial=user.display_name[:1].upper(),
        color=user.color,
        is_admin=user.is_admin,
        is_active=user.is_active,
        locked=user.locked_until is not None and user.locked_until > now,
        created_at=user.created_at,
    )


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"La contraseña tiene que tener al menos {MIN_PASSWORD_LENGTH} caracteres",
        )


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No existe ese usuario")
    return user


@router.get("")
def list_users(db: Session = Depends(get_db), _: User = Depends(admin_user)) -> list[AdminUser]:
    return [_out(u) for u in db.scalars(select(User).order_by(User.id))]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate, db: Session = Depends(get_db), _: User = Depends(admin_user)
) -> AdminUser:
    """Crea un usuario con sus categorías y reglas iniciales, como el asistente."""
    _check_password(body.password)
    if db.scalar(select(User.id).where(User.username == body.username)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Ya existe el usuario «{body.username}»"
        )
    user = User(
        username=body.username,
        display_name=body.display_name,
        color=body.color,
        is_admin=body.is_admin,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.flush()
        seed_user_defaults(db, user.id)
        db.commit()
    except IntegrityError:
        # Dos altas a la vez con el mismo nombre: la segunda choca con el UNIQUE
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Ya existe el usuario «{body.username}»"
        ) from None
    db.refresh(user)
    return _out(user)


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(admin_user),
) -> AdminUser:
    user = _get(db, user_id)
    changes = body.model_dump(exclude_unset=True)
    if user.id == me.id and (changes.get("is_active") is False or changes.get("is_admin") is False):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="No puedes desactivarte ni quitarte el permiso de administrador a ti mismo",
        )
    for field in ("display_name", "color", "is_admin", "is_active"):
        value = changes.get(field)
        if value is not None:
            setattr(user, field, value)
    if changes.get("is_active") is False:
        db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()
    db.refresh(user)
    return _out(user)


@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: PasswordReset,
    db: Session = Depends(get_db),
    _: User = Depends(admin_user),
) -> AdminUser:
    """Contraseña nueva: además desbloquea al usuario y cierra todas sus sesiones (también la
    del administrador si se la cambia a sí mismo)."""
    user = _get(db, user_id)
    _check_password(body.password)
    try:
        reset_password(db, user.username, body.password)
    except ResetError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    db.refresh(user)
    return _out(user)
