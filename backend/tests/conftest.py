"""Configuración común de los tests.

Los tests usan una BD aparte, "<POSTGRES_DB>_test", en el mismo PostgreSQL de docker compose.
Se crea si no existe, se le aplican las migraciones de Alembic y se vacía después de cada test.
"""

import os

# Tiene que ir ANTES de importar app.*: el motor de la BD se crea al importar app.db
os.environ["POSTGRES_DB"] = os.environ.get("POSTGRES_DB", "caudal") + "_test"

from collections.abc import Iterator  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from psycopg import sql  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


def _create_test_database() -> None:
    settings = get_settings()
    conninfo = psycopg.conninfo.make_conninfo(
        host=settings.database_host,
        port=settings.database_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (settings.postgres_db,)
        ).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.postgres_db)))


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    _create_test_database()
    command.upgrade(Config("alembic.ini"), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # noqa: S608


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
