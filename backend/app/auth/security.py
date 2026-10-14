"""Contraseñas y tokens de sesión.

- Contraseñas: hash Argon2 (argon2-cffi). Nunca se guarda la contraseña.
- Tokens: 32 bytes aleatorios para la cookie. En la BD solo se guarda su SHA-256,
  así que quien lea la BD o un backup no puede usar las sesiones.
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True si la contraseña coincide. Nunca lanza excepciones por una contraseña incorrecta."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
