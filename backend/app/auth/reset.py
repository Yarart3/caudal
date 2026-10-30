"""Restablecer la contraseña de un usuario desde la terminal (script «Restablecer contraseña»).

    python -m app.auth.reset              pregunta el usuario y la contraseña nueva
    python -m app.auth.reset padres       pregunta solo la contraseña nueva

Es la salida si alguien olvida su contraseña (la gestión de usuarios en Ajustes llega en la
Fase 4). Quien puede ejecutar esto ya tiene acceso al ordenador y al .env, así que no da más
poder del que ya tiene. Además del cambio, desbloquea el usuario y cierra sus sesiones abiertas.

Códigos de salida: 0 bien, 1 error, 2 cancelado.
"""

import getpass
import sys

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.setup import MIN_PASSWORD_LENGTH
from app.auth.security import hash_password
from app.db import SessionLocal
from app.models import User, UserSession


class ResetError(Exception):
    """Mensaje en castellano para el usuario."""


def reset_password(db: Session, username: str, new_password: str) -> User:
    """Cambia la contraseña, quita el bloqueo por intentos fallidos y cierra sus sesiones."""
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise ResetError(f"No existe el usuario «{username}»")
    if len(new_password) < MIN_PASSWORD_LENGTH:
        raise ResetError(f"La contraseña tiene que tener al menos {MIN_PASSWORD_LENGTH} caracteres")
    user.password_hash = hash_password(new_password)
    user.failed_attempts = 0
    user.locked_until = None
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()
    return user


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def _ask_secret(prompt: str) -> str:
    try:
        return getpass.getpass(prompt)
    except EOFError:
        return ""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.id)).all()
        if not users:
            print("Todavía no hay usuarios: abre Caudal y usa el asistente de primer arranque.")
            return 1
        names = [u.username for u in users]
        if args:
            username = args[0]
        else:
            print("Usuarios: " + ", ".join(names))
            username = _ask("¿De qué usuario quieres cambiar la contraseña? ")
        if not username:
            print("Cancelado.")
            return 2
        if username not in names:
            print(f"ERROR: no existe el usuario «{username}». Usuarios: {', '.join(names)}")
            return 1

        password = _ask_secret(f"Contraseña nueva para «{username}» (no se ve al escribir): ")
        if not password:
            print("Cancelado.")
            return 2
        if _ask_secret("Repítela: ") != password:
            print("ERROR: las dos contraseñas no coinciden. No se ha cambiado nada.")
            return 1
        try:
            reset_password(db, username, password)
        except ResetError as error:
            print(f"ERROR: {error}. No se ha cambiado nada.")
            return 1
    print(f"Contraseña de «{username}» cambiada. Si estaba bloqueado, ya puede entrar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
