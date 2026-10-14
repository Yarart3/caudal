"""Asistente de primer arranque: crea los usuarios iniciales cuando la BD está vacía."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/setup", tags=["setup"])

MIN_PASSWORD_LENGTH = 8

# Usuarios iniciales (DISENO §4). Los colores son los de la maqueta.
INITIAL_USERS = (
    {"username": "gerard", "display_name": "Gerard", "color": "#0E6B58", "is_admin": True},
    {"username": "padres", "display_name": "Padres", "color": "#3555A0", "is_admin": False},
)


class SetupStatus(BaseModel):
    needs_setup: bool


class SetupRequest(BaseModel):
    gerard_password: str
    padres_password: str


class CreatedUser(BaseModel):
    username: str
    display_name: str
    is_admin: bool


def _has_users(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(User)) > 0


@router.get("/status")
def setup_status(db: Session = Depends(get_db)) -> SetupStatus:
    """¿Hay que mostrar el asistente? Solo si todavía no existe ningún usuario."""
    return SetupStatus(needs_setup=not _has_users(db))


@router.post("", status_code=status.HTTP_201_CREATED)
def run_setup(body: SetupRequest, db: Session = Depends(get_db)) -> list[CreatedUser]:
    """Crea gerard (admin) y padres. Solo funciona una vez, con la BD sin usuarios."""
    if _has_users(db):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Caudal ya está configurado")

    passwords = {"gerard": body.gerard_password, "padres": body.padres_password}
    for data in INITIAL_USERS:
        if len(passwords[data["username"]]) < MIN_PASSWORD_LENGTH:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"La contraseña de {data['display_name']} debe tener al menos "
                f"{MIN_PASSWORD_LENGTH} caracteres",
            )

    users = [
        User(**data, password_hash=hash_password(passwords[data["username"]]))
        for data in INITIAL_USERS
    ]
    db.add_all(users)
    try:
        db.commit()
    except IntegrityError:
        # Dos asistentes a la vez: el segundo choca con el UNIQUE de username
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Caudal ya está configurado") from None
    return [
        CreatedUser(username=u.username, display_name=u.display_name, is_admin=u.is_admin)
        for u in users
    ]
