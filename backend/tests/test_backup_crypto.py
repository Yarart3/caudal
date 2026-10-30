"""Cifrado de los backups (app/backup/crypto.py). No usan la BD."""

import os

import pytest

from app.backup.crypto import (
    DEFAULT_LOG2_N,
    HEADER_LEN,
    MAGIC,
    BackupDecryptError,
    decrypt,
    encrypt,
)

PASSWORD = "clave-de-prueba-1d"
FAST = {"log2_n": 14}  # scrypt más ligero para que los tests vayan rápidos
DATA = b"PGDMP" + os.urandom(5000)  # parecido a un pg_dump -Fc


def test_ida_y_vuelta():
    blob = encrypt(DATA, PASSWORD, **FAST)
    assert blob.startswith(MAGIC)
    assert DATA not in blob
    assert decrypt(blob, PASSWORD) == DATA


def test_ida_y_vuelta_con_los_parametros_por_defecto():
    blob = encrypt(DATA, PASSWORD)
    assert blob[9] == DEFAULT_LOG2_N
    assert decrypt(blob, PASSWORD) == DATA


def test_datos_vacios():
    assert decrypt(encrypt(b"", PASSWORD, **FAST), PASSWORD) == b""


def test_cada_copia_lleva_sal_y_nonce_distintos():
    a = encrypt(DATA, PASSWORD, **FAST)
    b = encrypt(DATA, PASSWORD, **FAST)
    assert a[12:HEADER_LEN] != b[12:HEADER_LEN]
    assert a != b


def test_contrasena_incorrecta():
    blob = encrypt(DATA, PASSWORD, **FAST)
    with pytest.raises(BackupDecryptError, match="Contraseña incorrecta"):
        decrypt(blob, "otra-clave")


def test_datos_modificados():
    blob = bytearray(encrypt(DATA, PASSWORD, **FAST))
    blob[HEADER_LEN + 10] ^= 0x01
    with pytest.raises(BackupDecryptError, match="archivo dañado"):
        decrypt(bytes(blob), PASSWORD)


def test_cabecera_modificada():
    blob = bytearray(encrypt(DATA, PASSWORD, **FAST))
    blob[20] ^= 0x01  # un byte de la sal
    with pytest.raises(BackupDecryptError):
        decrypt(bytes(blob), PASSWORD)


def test_archivo_cortado():
    blob = encrypt(DATA, PASSWORD, **FAST)
    with pytest.raises(BackupDecryptError):
        decrypt(blob[:-1], PASSWORD)


@pytest.mark.parametrize("blob", [b"", b"hola", b"PGDMP" + b"\0" * 100, os.urandom(200)])
def test_no_es_un_backup(blob):
    with pytest.raises(BackupDecryptError, match="no es un backup de Caudal"):
        decrypt(blob, PASSWORD)


def test_version_desconocida():
    blob = bytearray(encrypt(DATA, PASSWORD, **FAST))
    blob[8] = 99
    with pytest.raises(BackupDecryptError, match="Versión"):
        decrypt(bytes(blob), PASSWORD)


def test_parametros_de_scrypt_abusivos_se_rechazan_sin_calcular():
    blob = bytearray(encrypt(DATA, PASSWORD, **FAST))
    blob[9] = 30  # N = 2^30 pediría 128 GB de memoria
    with pytest.raises(BackupDecryptError, match="cabecera"):
        decrypt(bytes(blob), PASSWORD)


def test_sin_contrasena():
    with pytest.raises(ValueError, match="BACKUP_PASSWORD"):
        encrypt(DATA, "")
    with pytest.raises(BackupDecryptError):
        decrypt(encrypt(DATA, PASSWORD, **FAST), "")
