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
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.categories import seed_user_defaults  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Account, User  # noqa: E402

TEST_PASSWORD = "contrasena-de-prueba"


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


@pytest.fixture
def db() -> Iterator[Session]:
    """Sesión de BD para preparar datos o comprobarlos directamente."""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def make_user(db: Session):
    """Crea usuarios de prueba: make_user("gerard", is_admin=True)."""

    def _make(username: str, password: str = TEST_PASSWORD, **fields) -> User:
        fields.setdefault("display_name", username.capitalize())
        fields.setdefault("color", "#0E6B58")
        user = User(username=username, password_hash=hash_password(password), **fields)
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def make_account(db: Session, make_user):
    """make_account("imagin") → cuenta de gasto con ese banco (None = cuenta a mano).

    Si el usuario no existe, lo crea: make_account("imagin", username="padres").
    """

    def _make(import_format: str | None, username: str = "gerard", **fields) -> Account:
        user = db.scalar(select(User).where(User.username == username)) or make_user(username)
        account = Account(
            user_id=user.id,
            name=fields.pop("name", import_format or "Efectivo"),
            kind="spending",
            import_format=import_format,
            **fields,
        )
        db.add(account)
        db.commit()
        return account

    return _make


@pytest.fixture
def login(make_user):
    """login("gerard") → TestClient con la sesión iniciada (crea el usuario con su semilla de
    categorías y reglas, como el asistente de primer arranque)."""

    def _login(username: str, **fields) -> TestClient:
        user = make_user(username, **fields)
        with SessionLocal() as session:
            seed_user_defaults(session, user.id)
            session.commit()
        client = TestClient(app)
        res = client.post("/api/auth/login", json={"username": username, "password": TEST_PASSWORD})
        assert res.status_code == 200
        return client

    return _login
