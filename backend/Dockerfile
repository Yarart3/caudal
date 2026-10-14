# Imagen de Caudal en tres etapas:
#   1. frontend: compila React con Node.
#   2. runtime:  Python + FastAPI, que sirve la API y el frontend compilado (la que se usa).
#   3. dev:      runtime + pytest y ruff, para las comprobaciones (servicio "tests").
# Se construye desde la raíz del proyecto (contexto ".", ver docker-compose.yml).

# ---------- 1. Frontend ----------
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

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

# ---------- 2. Runtime (la imagen de la app) ----------
FROM base AS runtime
RUN uv sync --locked --no-dev
COPY backend/ ./
COPY --from=frontend /frontend/dist ./static
RUN useradd --system --uid 10001 caudal
USER caudal
EXPOSE 8000
# Aplica las migraciones pendientes y arranca la app
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# ---------- 3. Dev (tests y lint, servicio "tests") ----------
FROM base AS dev
RUN uv sync --locked
COPY backend/ ./
CMD ["pytest"]
