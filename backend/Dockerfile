# Imagen de Caudal. Se construye desde la raíz del proyecto (contexto ".", ver docker-compose.yml).
# En la parte 1.6 se añade la etapa que compila el frontend.

# ---------- Base común de Python ----------
FROM python:3.12-slim AS base
RUN pip install --no-cache-dir --root-user-action=ignore uv==0.11.32
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH" \
    TZ=Europe/Madrid
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./

# ---------- Runtime (la imagen de la app) ----------
FROM base AS runtime
RUN uv sync --locked --no-dev
COPY backend/ ./
RUN useradd --system --uid 10001 caudal
USER caudal
EXPOSE 8000
# Aplica las migraciones pendientes y arranca la app
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
