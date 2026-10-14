"""Punto de entrada de Caudal. De momento solo la API; el frontend se añade en la parte 1.6."""

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

app = FastAPI(title="Caudal", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Errores de validación con el formato {"detail": "mensaje en castellano"}."""
    fields = sorted({str(err["loc"][-1]) for err in exc.errors() if err.get("loc")})
    detail = "Datos no válidos" + (f": revisa {', '.join(fields)}" if fields else "")
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """La usan el healthcheck de Docker y los scripts de arranque."""
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
