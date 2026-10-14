"""Conexión a PostgreSQL y sesión de SQLAlchemy por petición."""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Nombres de restricciones estables, para que Alembic genere migraciones predecibles
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=Europe/Madrid"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión de BD por petición, cerrada siempre al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
