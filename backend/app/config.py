"""Configuración de Caudal, leída de las variables de entorno (el .env de docker compose)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_host: str = "db"
    database_port: int = 5432

    session_timeout_min: int = 30
    login_max_attempts: int = 5
    login_lockout_min: int = 5

    @property
    def database_url(self) -> URL:
        # URL.create escapa la contraseña, por si lleva caracteres como @ o /
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.database_host,
            port=self.database_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # los valores vienen del entorno
