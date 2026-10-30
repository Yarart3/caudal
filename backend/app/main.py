"""Punto de entrada de Caudal: API bajo /api y, en el resto de rutas, el frontend compilado."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import (
    accounts,
    auth,
    backups,
    categories,
    dashboard,
    imports,
    rules,
    setup,
    transactions,
)
from app.backup.auto import auto_backup
from app.db import get_db

# El Dockerfile copia aquí el frontend compilado (frontend/dist)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Al arrancar: hilo de backups automáticos (backup si el último es antiguo y luego cada
    BACKUP_INTERVAL_MIN si hubo cambios). Al parar: lo detiene."""
    auto_backup.start()
    yield
    auto_backup.stop()


app = FastAPI(
    lifespan=lifespan,
    title="Caudal",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# Los routers de la API van ANTES de la ruta del frontend, que lo captura todo
app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(imports.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(rules.router)
app.include_router(dashboard.router)
app.include_router(backups.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Errores de validación con el formato {"detail": "mensaje en castellano"}."""
    errors = exc.errors()
    # Validaciones propias (ValueError en un validador): su mensaje ya está en castellano
    own = [e["msg"].removeprefix("Value error, ") for e in errors if e.get("type") == "value_error"]
    if own:
        return JSONResponse(status_code=422, content={"detail": own[0]})
    fields = sorted({str(err["loc"][-1]) for err in errors if err.get("loc")})
    detail = "Datos no válidos" + (f": revisa {', '.join(fields)}" if fields else "")
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """La usan el healthcheck de Docker y los scripts de arranque."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str) -> FileResponse:
    """Sirve el frontend. Cualquier ruta desconocida devuelve index.html (React Router decide)."""
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="No encontrado")
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="El frontend no está compilado")
    if full_path:
        candidate = (STATIC_DIR / full_path).resolve()
        # Evita salir de la carpeta static con rutas como ../../etc/passwd
        if candidate.is_relative_to(STATIC_DIR) and candidate.is_file():
            return FileResponse(candidate)
    return FileResponse(index)
