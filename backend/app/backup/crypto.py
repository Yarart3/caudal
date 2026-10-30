"""Cifrado de los backups: AES-256-GCM con la clave derivada de BACKUP_PASSWORD por scrypt.

Formato de un archivo .dump.enc (todo en un bloque, los backups ocupan pocos MB):

    bytes  contenido
    0-7    b"CAUDALBK"           para reconocer que es un backup de Caudal
    8      versión del formato   (1)
    9      log2(N) de scrypt     (17 → N = 131072, unos 128 MB de memoria)
    10     r de scrypt           (8)
    11     p de scrypt           (1)
    12-27  sal aleatoria         (16 bytes, distinta en cada backup)
    28-39  nonce aleatorio       (12 bytes, distinto en cada backup)
    40-    datos cifrados + etiqueta GCM (16 bytes al final)

Los parámetros de scrypt van en la cabecera para poder subirlos en el futuro sin dejar de
abrir los backups antiguos. La cabecera entera va como "datos asociados" de GCM: si alguien
cambia un solo byte (de la cabecera o de los datos), el descifrado falla.
"""

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"CAUDALBK"
VERSION = 1
SALT_LEN = 16
NONCE_LEN = 12
TAG_LEN = 16
HEADER_LEN = len(MAGIC) + 4 + SALT_LEN + NONCE_LEN  # 40

# Parámetros de scrypt recomendados por OWASP (N = 2^17, r = 8, p = 1)
DEFAULT_LOG2_N = 17
DEFAULT_R = 8
DEFAULT_P = 1

# Límites al LEER un archivo: un archivo manipulado no puede pedir gigas de memoria
LOG2_N_RANGE = range(14, 21)
R_RANGE = range(1, 17)
P_RANGE = range(1, 5)

# AES-GCM con un solo nonce admite unos 64 GB, pero la librería trabaja en memoria: un límite
# claro evita sorpresas. Una BD de Caudal ocupa unos pocos MB tras años de uso.
MAX_DATA_LEN = 1024 * 1024 * 1024  # 1 GB


class BackupDecryptError(Exception):
    """El archivo no se puede descifrar. El mensaje va en castellano, para el usuario."""


def _derive_key(password: str, salt: bytes, log2_n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**log2_n, r=r, p=p).derive(password.encode("utf-8"))


def encrypt(
    data: bytes,
    password: str,
    *,
    log2_n: int = DEFAULT_LOG2_N,
    r: int = DEFAULT_R,
    p: int = DEFAULT_P,
) -> bytes:
    """Cifra `data` con la contraseña. Devuelve el archivo completo (cabecera + datos)."""
    if not password:
        raise ValueError("Falta la contraseña de backup (BACKUP_PASSWORD en el .env)")
    if len(data) > MAX_DATA_LEN:
        raise ValueError("La copia es demasiado grande para cifrarla (más de 1 GB)")
    if log2_n not in LOG2_N_RANGE or r not in R_RANGE or p not in P_RANGE:
        raise ValueError("Parámetros de scrypt fuera de rango")
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    header = MAGIC + bytes([VERSION, log2_n, r, p]) + salt + nonce
    key = _derive_key(password, salt, log2_n, r, p)
    return header + AESGCM(key).encrypt(nonce, data, header)


def decrypt(blob: bytes, password: str) -> bytes:
    """Descifra un archivo .dump.enc. Lanza BackupDecryptError si no se puede."""
    if not password:
        raise BackupDecryptError("Falta la contraseña de backup")
    if len(blob) < HEADER_LEN + TAG_LEN or not blob.startswith(MAGIC):
        raise BackupDecryptError("El archivo no es un backup de Caudal")
    version, log2_n, r, p = blob[8], blob[9], blob[10], blob[11]
    if version != VERSION:
        raise BackupDecryptError(f"Versión de backup no compatible ({version})")
    if log2_n not in LOG2_N_RANGE or r not in R_RANGE or p not in P_RANGE:
        raise BackupDecryptError("La cabecera del backup está dañada")
    header = blob[:HEADER_LEN]
    salt = header[12 : 12 + SALT_LEN]
    nonce = header[12 + SALT_LEN : HEADER_LEN]
    key = _derive_key(password, salt, log2_n, r, p)
    try:
        return AESGCM(key).decrypt(nonce, blob[HEADER_LEN:], header)
    except InvalidTag:
        # GCM no distingue entre contraseña incorrecta y archivo modificado
        raise BackupDecryptError("Contraseña incorrecta o archivo dañado") from None
