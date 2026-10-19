# Fase 1a · Base del proyecto e inicio de sesión

> **Versión:** `0.1.0` · **Fechas:** 2026-10-14 → 2026-10-19 · **Estado:** ✅ terminada

El objetivo de la Fase 1a es tener el **esqueleto completo de Caudal funcionando en Docker**, con inicio de sesión y dos usuarios aislados (`gerard` y `padres`). Todavía no se importan extractos: eso empieza en la 1b.

Este documento explica **qué se ha hecho**, **cómo** (con los comandos exactos) y **por qué**, con apuntes para aprender cada concepto. La fase se hizo en 14 partes pequeñas, cada una probada y guardada con su commit, trabajando en el Mac y en el PC de casa.

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Cómo trabajamos en esta fase](#2-cómo-trabajamos-en-esta-fase)
3. [Estructura del proyecto](#3-estructura-del-proyecto)
4. [Parte 1.1: archivos de la raíz](#4-parte-11-archivos-de-la-raíz)
5. [Parte 1.2: PostgreSQL con Docker](#5-parte-12-postgresql-con-docker)
6. [Parte 1.3: backend mínimo con FastAPI](#6-parte-13-backend-mínimo-con-fastapi)
7. [Parte 1.4: modelos y primera migración](#7-parte-14-modelos-y-primera-migración)
8. [Parte 1.5: tests y lint en Docker](#8-parte-15-tests-y-lint-en-docker)
9. [Parte 1.6: frontend servido por FastAPI](#9-parte-16-frontend-servido-por-fastapi)
10. [Pasos 2 y 3: inicio de sesión y pantallas](#10-pasos-2-y-3-inicio-de-sesión-y-pantallas)
11. [Decisiones de la fase](#11-decisiones-de-la-fase)
12. [Problemas encontrados y cómo se resolvieron](#12-problemas-encontrados-y-cómo-se-resolvieron)
13. [Chuleta de comandos](#13-chuleta-de-comandos)
14. [Glosario](#14-glosario)

---

## 1. Resumen y estado

| Paso | Parte | Qué | Estado |
|---|---|---|---|
| 1 | 1.1 | `.gitignore`, `.gitattributes`, `.env.example` y `.env` de cada equipo | ✅ |
| 1 | 1.2 | `docker-compose.yml` con PostgreSQL 16 y el volumen `pgdata` | ✅ |
| 1 | 1.3 | Backend mínimo: FastAPI, `config.py`, `db.py`, `/api/health`, Dockerfile | ✅ |
| 1 | 1.4 | Modelos de las 7 tablas + Alembic + migración `0001` | ✅ |
| 1 | 1.5 | Tests (pytest) y lint (ruff) en Docker, con la BD `caudal_test` | ✅ |
| 1 | 1.6 | Frontend (Vite + React + TypeScript) compilado en la imagen y servido por FastAPI | ✅ |
| 2 | 2.1 | Seguridad: Argon2, tokens de sesión, cookie, caducidad, `current_user` | ✅ |
| 2 | 2.2 | Asistente de primer arranque: `GET /api/setup/status` y `POST /api/setup` | ✅ |
| 2 | 2.3 | `GET /api/auth/users`, login, logout, `me` y bloqueo tras 5 intentos | ✅ |
| 2 | 2.4 | `GET/POST/PATCH /api/accounts` filtrado por usuario + test de aislamiento | ✅ |
| 3 | 3.x | Pantallas según la maqueta: asistente, "¿Quién entra?", contraseña, panel vacío | ✅ |
| — | Cierre | Criterios de "hecho", CHANGELOG `0.1.0`, README, DISENO y CLAUDE.md | ✅ |

**Funciona igual en los dos equipos:** el MacBook Air M5 (zsh) y el PC de casa con Windows (Git Bash y PowerShell).

---

## 2. Cómo trabajamos en esta fase

- **Paso a paso, en partes pequeñas** que se prueban por separado. Cada parte trae:
  - los **archivos completos** como bloques `cat > ruta <<'EOF' … EOF`, que se pegan en la **terminal**, no en un archivo abierto en el editor;
  - una explicación breve de qué hace cada archivo y por qué;
  - las **comprobaciones** con lo que debería salir.
- **No se entregan zips:** la idea es ver y entender cada archivo.
- **Al final de cada parte:** `git add -A`, commit con prefijo (`feat:`, `test:`, `fix:`, `chore:`, `docs:`) y `git push`, directamente en `main`, sin ramas.
- **Cambio de equipo a mitad de una parte:**
  1. en el equipo que dejas, commit `wip: …` y push;
  2. en el otro, `git pull` y `docker compose up -d --build --wait`.
- **Windows:** los bloques `cat > … <<'EOF'` **no funcionan en PowerShell**, así que se pegan en **Git Bash** (terminal de VS Code → flecha **˅** junto al **+** → *Git Bash*). En Git Bash se pega con Ctrl+V dentro de VS Code, o con Shift+Insert en la ventana suelta.

---

## 3. Estructura del proyecto

```text
caudal/
├── .env                     ← de cada equipo, NUNCA en git
├── .env.example             ← plantilla sin secretos
├── .gitignore  .gitattributes  .dockerignore
├── docker-compose.yml       ← db + app (+ tests y web, perfil dev)
├── backend/
│   ├── Dockerfile           ← etapas: frontend → base → runtime / dev
│   ├── pyproject.toml       ← dependencias fijadas + config de pytest y ruff
│   ├── uv.lock              ← versiones exactas de TODO (se genera, no se edita)
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/0001_initial_schema.py
│   ├── app/
│   │   ├── config.py        ← lee el .env (pydantic-settings)
│   │   ├── db.py            ← motor, sesión por petición, Base
│   │   ├── main.py          ← /api/health + sirve el frontend
│   │   └── models/          ← user, session, account, category, transaction, rule, backup_log
│   └── tests/
│       ├── conftest.py      ← BD caudal_test, limpieza, TestClient
│       └── test_health.py
└── frontend/
    ├── package.json  package-lock.json
    ├── vite.config.ts  tsconfig*.json  eslint.config.js  .prettierrc.json
    ├── index.html  public/favicon.svg
    └── src/                 ← main.tsx, App.tsx, Logo.tsx, styles.css
```

---

## 4. Parte 1.1: archivos de la raíz

### Qué se hizo

- **`.gitignore`**: excluye de git:
  - `.env` y los secretos;
  - `pgdata/`, `backups/`, `*.dump` y `*.enc`;
  - los extractos (`*.xlsx`, `*.xls`, `*.csv`), **excepto** los de `samples/`;
  - las cachés de Python, `node_modules/` y `frontend/dist/`;
  - `.DS_Store` y `Thumbs.db`.
- **`.gitattributes`**: `* text=auto eol=lf` (todo con `LF`), salvo `*.bat` y `*.cmd` (`CRLF`); los binarios no se tocan.
- **`.env.example`**: la plantilla de configuración. Cada equipo crea su `.env` a partir de ella:

```zsh
# Mac
cp .env.example .env
sed -i '' "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
ONEDRIVE=$(ls -d ~/Library/CloudStorage/OneDrive-*/Proyectos/CaudalBackups) && \
sed -i '' "s|^ONEDRIVE_DIR=.*|ONEDRIVE_DIR=\"$ONEDRIVE\"|" .env
```

```powershell
# Windows: copiar, generar la contraseña al portapapeles y pegarla en VS Code
Copy-Item .env.example .env
-join ((1..24) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) }) | Set-Clipboard
code .env
```

**Rutas de OneDrive:**
- Mac: `/Users/gerard/Library/CloudStorage/OneDrive-udl.cat/Proyectos/CaudalBackups`
- Windows: `C:\Users\gerar\OneDrive - udl.cat\Proyectos\CaudalBackups`

### Apuntes para aprender

- **`!` en `.gitignore`** crea una excepción: `*.xlsx` ignora todos los Excel, y `!samples/*.xlsx` deja pasar los de ejemplo.
- **`git check-ignore -v archivo`** dice qué regla ignora un archivo, y **`git check-attr eol -- archivo`** qué final de línea se le aplica.
- **El `.gitignore` sí va a git**, así que los dos equipos tienen las mismas reglas. Lo que ignora (`.env`, la BD, `node_modules`) **no se copia** entre equipos: cada uno lo crea o lo regenera. El único que se hace a mano es el `.env`, una vez por equipo.
- **La contraseña de la BD puede ser distinta en cada equipo**, porque cada uno tiene su propia BD. No hace falta recordarla: solo la usan la app y PostgreSQL. ⚠️ PostgreSQL solo la lee **la primera vez** que crea el volumen. Si se cambia después, hay que borrar el volumen (`docker compose down -v`), y eso **borra los datos**.
- **`eol=lf` para todo:** Prettier exige `LF`, y con `core.autocrlf true` Windows convertía los archivos a `CRLF`, lo que habría hecho fallar el lint del frontend en el PC. VS Code, Docker y Python trabajan bien con `LF` también en Windows.

---

## 5. Parte 1.2: PostgreSQL con Docker

### Qué se hizo

Servicio `db` con la imagen `postgres:16`:
- usuario, contraseña y BD tomados del `.env`;
- zona horaria `Europe/Madrid`;
- datos en el volumen `pgdata`;
- un **healthcheck** con `pg_isready`;
- **sin puerto abierto** al equipo.

```zsh
docker compose up -d --wait
docker compose exec db psql -U caudal -d caudal -P pager=off -c "SELECT version(), now();"
```

Prueba de que los datos sobreviven:
1. Se creó una tabla de prueba.
2. `docker compose down` borró el contenedor.
3. `docker compose up -d --wait` lo creó de nuevo.
4. La fila seguía ahí.

### Apuntes para aprender

- **Contenedor y volumen:** `docker compose down` **borra los contenedores**, pero no los volúmenes. Los datos de PostgreSQL viven en el volumen `caudal_pgdata`. ⚠️ `docker compose down -v` **sí borra el volumen**: nunca con datos reales.
- **`name: caudal`** fija el nombre del proyecto. Los contenedores (`caudal-db-1`) y los volúmenes (`caudal_pgdata`) se llaman igual en todos los equipos.
- **`${POSTGRES_USER}`** en `docker-compose.yml` se sustituye por el valor del `.env`. **`$${…}`** (doble `$`) deja la variable sin sustituir, para que la lea el propio contenedor.
- **Healthcheck:** Docker ejecuta un comando cada pocos segundos y marca el contenedor como `healthy` o `unhealthy`. `--wait` espera a que todo esté `healthy`.
- **Sin `ports` en la BD:** solo la ve la app, por la red interna de Docker, en la que la BD se llama `db`. Ni el Mac ni la red de casa pueden conectarse a ella.
- **`docker compose exec db …`** ejecuta un comando **dentro** del contenedor. `psql` es el cliente de PostgreSQL.

---

## 6. Parte 1.3: backend mínimo con FastAPI

### Qué se hizo

- **`backend/pyproject.toml`**: las dependencias con versión fija y la configuración de pytest y ruff.
- **`backend/uv.lock`**: generado con uv dentro de un contenedor, sin instalar nada en el equipo:

```zsh
docker run --rm -v "$PWD/backend:/app" -w /app python:3.12-slim \
  sh -c "pip install -q --root-user-action=ignore uv==0.11.32 && uv lock"
```

- **`app/config.py`**: lee la configuración del entorno con `pydantic-settings`. `URL.create` escapa la contraseña.
- **`app/db.py`**:
  - `engine` con `pool_pre_ping`;
  - `get_db()`, que abre una sesión de BD por petición y la cierra siempre;
  - `Base` con `NAMING_CONVENTION`.
- **`app/main.py`**:
  - `/api/health`, que hace un `SELECT 1`;
  - errores de validación en castellano;
  - documentación de la API en `/api/docs`.
- **`backend/Dockerfile`**:
  - instala uv, y con él las dependencias exactas del lock;
  - **después** copia el código;
  - ejecuta la app con un usuario sin privilegios (`caudal`).
- **Servicio `app` en compose:**
  - se construye desde la raíz;
  - recibe el `.env`;
  - `DATABASE_HOST=db`;
  - publica el puerto `APP_PORT` (8080) hacia el 8000 del contenedor;
  - espera a que la BD esté `healthy`;
  - tiene su propio healthcheck contra `/api/health`.

### Apuntes para aprender

- **Lock:** `pyproject.toml` fija las 8 dependencias directas, pero cada una trae otras (44 paquetes en total). `uv.lock` fija **todas** con su huella. `uv sync --locked` instala exactamente eso, y **falla** si `pyproject.toml` y `uv.lock` no coinciden.
- **Capas de Docker y caché:** cada instrucción del Dockerfile es una capa. Si sus entradas no cambian, Docker la reutiliza (`CACHED`). Por eso primero se copian `pyproject.toml` y `uv.lock`, se instalan las dependencias y **después** se copia el código. Si solo cambia el código, la reconstrucción tarda segundos.
- **El código se copia dentro de la imagen.** Si cambias un `.py`, hace falta `--build` para que la app lo vea.
- **Inyección de dependencias de FastAPI:** `db: Session = Depends(get_db)` hace que FastAPI llame a `get_db()` en cada petición y le pase la sesión. Con el `try/finally`, la sesión se cierra aunque haya un error.
- **`pool_pre_ping`:** antes de reutilizar una conexión, comprueba que sigue viva. Con la BD parada, `/api/health` da 500. Al volver, se recupera sola, sin reiniciar la app.
- **`localhost:8080` → contenedor `:8000`:** `ports: "8080:8000"` publica el puerto 8000 del contenedor en el 8080 del equipo.

---

## 7. Parte 1.4: modelos y primera migración

### Qué se hizo

- **`app/models/`**: una clase por tabla, con el estilo de SQLAlchemy 2 (`Mapped[...]` + `mapped_column`):
  - `users`
  - `sessions`
  - `accounts`
  - `categories`
  - `transactions`
  - `rules`
  - `backup_log`
- **Alembic:** `alembic.ini`, `alembic/env.py` (usa la URL de `config.py` y `Base.metadata`) y `script.py.mako` (la plantilla de las migraciones).
- **Migración generada** comparando los modelos con la BD vacía:

```zsh
docker compose run --rm --user root -v "$PWD/backend:/app" app \
  alembic revision --autogenerate -m "initial schema" --rev-id 0001
```

- **Migraciones automáticas:** la app aplica las pendientes al arrancar. Es la última línea del Dockerfile:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

**Resultado:** 8 tablas (las 7 de los modelos más `alembic_version`), y `alembic_version = 0001`. Al reiniciar, Alembic no vuelve a aplicar nada.

### Apuntes para aprender

- **Modelo ORM:** una clase Python que representa una tabla. `Mapped[int]` es el tipo en Python, y `mapped_column(...)` añade el tipo de la BD y sus opciones. `Mapped[str | None]` = columna que admite `NULL`.
- **Migración:** un script con `upgrade()` y `downgrade()` que cambia el esquema de la BD de forma controlada y reproducible. Nunca se usa `create_all` en producción: cada cambio de tablas lleva su migración.
- **`alembic_version`:** la tabla donde Alembic apunta qué migración tiene aplicada la BD. `alembic upgrade head` aplica las que falten.
- **Autogenerate es una ayuda, no un oráculo:** el archivo generado **se revisa siempre**. Por ejemplo, un cambio de nombre lo interpreta como un borrado más un alta.
- **Restricciones que protegen los datos:**
  - `NUMERIC(12,2)` para el dinero, nunca `float`;
  - `CHECK` para los valores permitidos (`kind IN ('spending', 'investment', 'mixed')`);
  - `UNIQUE (account_id, fingerprint)`, el anti-duplicados de la 1b. Los movimientos a mano no llevan huella, y dos `NULL` no chocan en un `UNIQUE`.
  - Claves foráneas con `ON DELETE CASCADE` (al borrar una cuenta se borran sus movimientos) o `SET NULL` (al borrar una categoría, el movimiento se queda sin categoría).
- **`default` y `server_default`:** `default` lo pone Python al crear un objeto. `server_default` lo pone la BD, así que también funciona con un `INSERT` hecho a mano.
- **`NAMING_CONVENTION`:** da nombres predecibles a las restricciones (`fk_accounts_user_id_users`, `uq_users_username`…). Las migraciones salen iguales en todos los equipos.
- **Aislamiento entre usuarios:** las cuentas tienen `user_id`, y los movimientos cuelgan de una cuenta. Por eso "cada uno ve solo lo suyo" se consigue filtrando por el usuario de la sesión.

---

## 8. Parte 1.5: tests y lint en Docker

### Qué se hizo

- **Etapa `dev` en el Dockerfile:** igual que la de la app, pero con `uv sync --locked` sin `--no-dev`, así que lleva pytest, ruff y httpx2.
- **Servicio `tests` en compose:**
  - perfil `dev`, así que no arranca con `docker compose up`;
  - monta `./backend:/app`, para que vea siempre el código actual sin reconstruir la imagen.
- **`backend/tests/conftest.py`**:
  - antes de importar la app, cambia la BD a `caudal_test`;
  - la crea si no existe y le aplica las migraciones;
  - después de cada test, vacía las tablas con `TRUNCATE`;
  - ofrece la fixture `client`, un `TestClient`.
- **`test_health.py`**: dos tests, `/api/health` y el 404 en JSON de las rutas `/api/…` que no existen.
- **`ruff format .`** formateó la migración generada por Alembic.

### Apuntes para aprender

- **Fixture de pytest:** una función que prepara algo para los tests.
  - `autouse=True` hace que se aplique a todos los tests.
  - `scope="session"` hace que se ejecute una sola vez por ejecución de pytest.
  - Lo que va después de `yield` es la limpieza.
- **BD de tests separada:** los tests nunca tocan la BD `caudal`. Además, aplicar las migraciones a una BD vacía prueba que la migración funciona.
- **`TestClient`:** hace peticiones a la app como si fuera un navegador, pero sin levantar un servidor.
- **Ruff:**
  - `ruff check` busca errores y malas prácticas: imports sin usar, `datetime` sin zona horaria, `assert` fuera de los tests…
  - `ruff format` aplica un formato estándar.
  - `--check` solo comprueba, sin cambiar nada.
- **Un test que falla:** se rompió uno a propósito para ver el informe de pytest, con la diferencia entre lo esperado y lo obtenido.

---

## 9. Parte 1.6: frontend servido por FastAPI

### Qué se hizo

- **`frontend/`**:
  - Vite 8 + React 19 + TypeScript 6.0.3 (`strict`);
  - ESLint y Prettier;
  - las fuentes Space Grotesk y Manrope con `@fontsource`;
  - las variables CSS de la maqueta;
  - una pantalla provisional que llama a `/api/health`.
- **`package-lock.json`** generado sin instalar nada en la carpeta:

```bash
docker compose run --rm web npm install --package-lock-only --no-audit --no-fund
```

- **Etapa `frontend` del Dockerfile:** `node:24-slim` hace `npm ci` y `npm run build`, y `COPY --from=frontend /frontend/dist ./static` lo lleva a la imagen de Python. Node no queda en la imagen final.
- **`main.py`:**
  - una ruta *catch-all* devuelve `index.html` para cualquier ruta que no sea `/api/...`, de modo que React decide qué mostrar;
  - sirve los archivos de `static/`;
  - devuelve un 404 en JSON para las rutas `/api/...` que no existen;
  - impide salir de `static/` con rutas como `../../`.
- **Servicio `web`** (perfil `dev`):
  - ejecuta `npm ci`, `npm run lint` y `npm run build`;
  - guarda `node_modules` en un volumen de Docker, no en la carpeta del equipo.

### Apuntes para aprender

- **SPA (*single page application*):** el servidor siempre devuelve el mismo `index.html`, y React muestra una pantalla u otra según la URL. Por eso `/patrimonio` también devuelve `index.html`.
- **Build multietapa:** una etapa compila con Node y la siguiente solo copia el resultado. La imagen final es más pequeña y no lleva herramientas de compilación.
- **`npm ci` y `npm install`:** `npm ci` instala **exactamente** lo que dice `package-lock.json` y falla si no coincide con `package.json`. Es el equivalente de `uv sync --locked`.
- **`node_modules` en un volumen:** los paquetes con binarios (rolldown, lightningcss) se instalan para Linux dentro del contenedor y no servirían en macOS ni en Windows. En un volumen no ensucian la carpeta del proyecto.
- **Fuentes dentro de la app:** funcionan sin internet y no hacen ninguna petición a Google, lo que es más privado.

---

## 10. Pasos 2 y 3: inicio de sesión y pantallas

### Parte 2.1: seguridad (`backend/app/auth/`)

**Qué se hizo:**
- **`security.py`**:
  - `hash_password` y `verify_password` con Argon2 (`argon2-cffi`);
  - `new_session_token`, que genera 32 bytes aleatorios con `secrets`;
  - `hash_token`, que calcula el SHA-256 del token.
- **`sessions.py`**:
  - crea la sesión en la tabla `sessions` (solo con el hash del token);
  - la busca por la cookie y la **renueva en cada uso** (`last_seen_at`), o la borra si lleva más de `SESSION_TIMEOUT_MIN` sin uso;
  - pone y quita la cookie `caudal_session` (`HttpOnly`, `SameSite=Strict`, sin `Secure`).
- **`deps.py`**: las dependencias `current_user`, que responde 401 *"Inicia sesión para continuar"* si no hay sesión, y `admin_user`, que responde 403.
- **Tests:** fixtures `db` y `make_user` en `conftest.py` y 9 tests en `test_auth_security.py`.

**Apuntes para aprender:**
- **Hash y cifrado no son lo mismo.** Un hash **no se puede deshacer**: para comprobar una contraseña se calcula el hash de lo que escribes y se compara con el guardado. Argon2 es **lento a propósito** y usa una **sal** aleatoria, así que la misma contraseña da hashes distintos y probar millones de contraseñas cuesta muchísimo.
- **Por qué solo se guarda el hash del token:** si alguien copiara la BD o un backup, no podría usar las sesiones, porque para entrar hace falta el token, que solo está en la cookie del navegador.
- **Inactividad y no tiempo total:** cada uso renueva `last_seen_at`. Por eso la sesión caduca a los 30 minutos **sin usarla**, no a los 30 minutos de haber entrado.
- **Cookie `HttpOnly`:** el JavaScript de la página no la puede leer, lo que protege frente a XSS. **`SameSite=Strict`:** otras webs no pueden lanzar peticiones a Caudal con tu cookie, lo que protege frente a CSRF.

### Parte 2.2: asistente de primer arranque (`app/api/setup.py`)

**Qué se hizo:** `GET /api/setup/status` y `POST /api/setup`.
- Crea `gerard` (admin, `#0E6B58`) y `padres` (`#3555A0`).
- Las contraseñas tienen que tener al menos 8 caracteres.
- Solo funciona si no hay usuarios: si no, responde 409. Si llegan dos peticiones a la vez, el `UNIQUE` de `username` hace que también falle la segunda.
- 5 tests.

**Apuntes para aprender:**
- **`APIRouter`** agrupa endpoints con un prefijo y se registra en `main.py` con `include_router`. Los routers van **antes** de la ruta del frontend, que lo captura todo.
- **Modelos de Pydantic** (`SetupRequest`…): definen la forma del JSON de entrada y de salida. FastAPI los valida solo.

### Parte 2.3: login, logout y bloqueo (`app/api/auth.py`)

**Qué se hizo:**
- `GET /api/auth/users`: las tarjetas, solo con `username`, nombre, inicial y color.
- `POST /api/auth/login`, `POST /api/auth/logout` y `GET /api/auth/me`.
- El mismo error 401 si falla el usuario o la contraseña.
- Bloqueo con 429 tras 5 fallos, por usuario.
- 8 tests.

**Apuntes para aprender:**
- **Enumeración de usuarios:** si el error o el **tiempo de respuesta** cambiaran según exista o no el usuario, se podría averiguar quién existe. Por eso, si el usuario no existe, se verifica igualmente contra un hash falso (`_DUMMY_HASH`).
- **Códigos HTTP:**
  - `401`: no has entrado o la contraseña no es correcta;
  - `403`: has entrado pero no tienes permiso;
  - `404`: no existe;
  - `409`: conflicto;
  - `422`: datos no válidos;
  - `429`: demasiados intentos.
- **Probar con cookies desde la terminal:** `curl -c archivo` guarda las cookies y `curl -b archivo` las envía, igual que un navegador.

### Parte 2.4: cuentas y aislamiento (`app/api/accounts.py`)

**Qué se hizo:**
- `GET/POST/PATCH /api/accounts` y `GET /api/accounts/{id}`. Todos sacan el usuario de la sesión y filtran por `user_id`.
- `get_own_account()` centraliza el "solo si es tuya".
- El dinero sale como texto (`"1234.50"`).
- Nombre único por usuario (409).
- El saldo de referencia y su fecha van juntos (422).
- 7 tests, entre ellos el de **aislamiento**: Padres no ve ni puede tocar las cuentas de Gerard.

**Apuntes para aprender:**
- **El usuario nunca sale del JSON**, siempre de la sesión. Aunque alguien envíe `"user_id": 1`, se ignora.
- **404 y no 403** para lo de otro usuario: así no se revela ni siquiera que existe.
- **`Decimal` y no `float`:** `0.1 + 0.2` en `float` da `0.30000000000000004`. Con `Decimal` las cuentas salen exactas, y en el JSON el dinero viaja como texto para no perder céntimos.
- **PATCH** cambia solo los campos enviados (`model_dump(exclude_unset=True)`).
- **Pruebas desde el navegador:** `http://localhost:8080/api/docs`, con *Try it out → Execute*. Una ventana privada sirve como "otro navegador" con sus propias cookies.

### Parte 3.1: base del frontend

**Qué se hizo:**
- **`src/api.ts`**: el único sitio que habla con la API. Envía la cookie y convierte los errores en `ApiError`, con el mensaje en castellano.
- **`src/auth/`**:
  - `AuthProvider` pregunta `/me` al abrir la app;
  - `useAuth` da el usuario y el `logout` a cualquier pantalla;
  - `RequireAuth` protege las pantallas.
- **Rutas con React Router:**
  - `/` decide a dónde ir;
  - `/bienvenida`, `/entrar` y `/panel` (protegida);
  - cualquier otra ruta vuelve a `/`.
- **Servicio `vite`** en Docker Compose (perfil `dev`): frontend en vivo en `http://localhost:5173`. Las llamadas a `/api` las reenvía a la app de Docker.

**Apuntes para aprender:**
- **Contexto de React:** comparte datos (quién ha entrado) con todas las pantallas sin pasarlos a mano de componente en componente.
- **Servidor de desarrollo y build:** Vite en `:5173` recarga al guardar y solo se usa para desarrollar. `localhost:8080` es la app compilada, que se actualiza con `--build`.
- **Proxy:** el navegador habla solo con `localhost:5173`, y Vite reenvía `/api` a la app. Las cookies son por **nombre de host**, no por puerto, así que `localhost:8080` y `localhost:5173` comparten la cookie, pero `127.0.0.1` no.
- **La app solo pregunta `/me` al cargarse.** Si entras desde `/api/docs` con la app ya abierta, hay que recargar la pestaña.

### Parte 3.2: asistente

**Qué se hizo:**
- **`styles.css`** usa las clases de la maqueta (`.login-wrap`, `.login`, `.field`, `.btn-primary`, `.err`, `.note`…).
- **`SetupPage`** tiene un bloque por usuario con contraseña y repetición, y la casilla "Mostrar las contraseñas".
- Se valida en el navegador antes de enviar: al menos 8 caracteres, la repetición coincide y las dos contraseñas son **distintas**.

**Apuntes para aprender:**
- **Validar en los dos lados:** en el navegador, para avisar al momento; en el servidor, porque es el único sitio en el que se puede confiar.
- **Formularios accesibles:** `<label htmlFor>`, `role="alert"` para los errores y `autoComplete="new-password"`, para que el navegador ofrezca guardar la contraseña.

### Parte 3.3: "¿Quién entra?" y contraseña

**Qué se hizo:**
- Tarjetas grandes (`.user-btn`) con la inicial y el color de cada usuario.
- Paso de contraseña con el cursor ya en el campo.
- Muestra los errores del backend: 401, 429 y "Escribe la contraseña".
- Botón "← Cambiar de usuario".
- Si ya hay sesión, `/entrar` lleva al panel.

**Apuntes para aprender:**
- **Un campo `username` oculto** con `autoComplete="username"` ayuda al gestor de contraseñas del navegador a saber de qué usuario es la contraseña.

### Parte 3.4: panel vacío y caducidad de la sesión

**Qué se hizo:**
- **El panel con la estructura de la maqueta:**
  - barra lateral oscura, con Patrimonio activa y Movimientos, Inversiones y Ajustes desactivadas hasta la 1c;
  - la "pastilla" con el usuario y "Cerrar sesión";
  - la tarjeta *Todavía no hay datos*.

  En móvil, la barra pasa arriba.
- **Caducidad de la sesión:** cualquier 401 de la API estando dentro vuelve a "¿Quién entra?" con el aviso *"Tu sesión se ha cerrado tras 30 minutos sin usarla"*. Al volver a la pestaña (`visibilitychange`), se comprueba la sesión.

**Apuntes para aprender:**
- **Por qué no se comprueba la sesión cada X segundos:** cada consulta a `/me` **renueva** la sesión, así que un sondeo periódico haría que nunca caducara. Solo se comprueba cuando hay actividad real: al volver a la pestaña o al llamar a la API.
- **CSS Grid en móvil:** con una sola columna, las filas se reparten la altura mínima de la pantalla. Hace falta `grid-template-rows: auto 1fr` para que la barra no se estire.

### Cierre: criterios de "hecho" de CLAUDE.md

| Criterio | Cómo se comprobó | Resultado |
|---|---|---|
| `docker compose up -d --build` → `http://localhost:8080` muestra el asistente | Con la BD vacía (`docker compose down -v` + `up`), la app lleva a `/bienvenida` | ✅ |
| Se crean `gerard` (admin) y `padres` | Desde el asistente; en la tabla `users` aparecen los dos, con su color y su hash `$argon2id$` | ✅ |
| Cada uno entra y ve su panel vacío | Gerard en una ventana y Padres en una ventana privada, a la vez | ✅ |
| Los tests pasan | `docker compose run --rm tests` → **31 passed**; ruff, ESLint y Prettier sin avisos; build correcto | ✅ |
| Los datos sobreviven a `docker compose down` + `up` | Después de `down` + `up`, los dos usuarios siguen ahí | ✅ |

---

## 11. Decisiones de la fase

Todas están ya pasadas a DISENO, CLAUDE.md, README o CHANGELOG.

| Decisión | Motivo | Dónde está |
|---|---|---|
| Sesiones en BD (tabla `sessions`) con el **SHA-256 del token**; sin `SESSION_SECRET` | Permiten cerrar sesión de verdad y caducar por inactividad en el servidor; un backup robado no da sesiones válidas | DISENO §4, §8.4 y §10 |
| Cookie sin `Secure` | La app va por HTTP en la red de casa; con `Secure`, el navegador no la enviaría | DISENO §4 |
| Mismo error 401 (y mismo tiempo) si falla el usuario o la contraseña | No revelar qué usuarios existen | DISENO §4 |
| Lo de otro usuario da **404**, no 403 | No revelar ni siquiera que existe | DISENO §4 |
| Contraseñas del asistente: al menos 8 caracteres, repetidas y **distintas** entre Gerard y Padres | Cada uno solo debe poder entrar en lo suyo | DISENO §4 |
| `users.color` | Colores de las tarjetas (verde `gerard`, azul `padres`) | DISENO §8.4 |
| Nombres en inglés: `transactions.description`, `accounts.liquidity_type` (`cash` / `money_market`), `backup_log.destination` (`usb` / `onedrive`), `sessions` | No estaban en la tabla de equivalencias | CLAUDE.md §3 |
| `GET /api/accounts/{id}` | Lo usará la pantalla de editar cuenta; permite probar el aislamiento | CLAUDE.md §6 |
| Tests en `backend/tests/`, con la BD `caudal_test`, y `httpx2` como cliente de pruebas | Un solo montaje en el contenedor; nunca tocan la BD real | DISENO §10, CLAUDE.md §7 |
| Fuentes con `@fontsource`, sin Google Fonts | Funcionan sin internet y no hacen peticiones a Google | DISENO §14 |
| Versiones fijadas, con **TypeScript 6.0.3** | La 7 todavía no es compatible con `typescript-eslint` | DISENO §10, CHANGELOG |
| Migraciones automáticas al arrancar | Nadie tiene que acordarse de migrar; los padres nunca lo harán | DISENO §10 |
| Servicio `vite` para desarrollar el frontend en vivo | Ver los cambios al guardar sin `--build` y sin instalar Node | DISENO §10, README |
| `.gitattributes` con `eol=lf` en todo, salvo `.bat` y `.cmd` | Prettier exige `LF`; con `autocrlf`, Windows los pasaba a `CRLF` | DISENO §10, README |
| Ruta de OneDrive en el Mac: `OneDrive-udl.cat/Proyectos/CaudalBackups` | Confirmada en el Mac | DISENO §10 y §16 |
| Fases en partes pequeñas, con un commit por parte en `main` (`wip:` al cambiar de equipo) | Se trabaja en dos equipos a mitad de fase | CLAUDE.md §3 y §5, README |
| Entrega con bloques `cat > … <<'EOF'` para la terminal; Git Bash en Windows | Archivos exactos, sin errores al copiar; PowerShell no entiende los *heredoc* | CLAUDE.md §5 |
| Documentos de fases con nombre `FASE_<n>.md`, sin espacios | Los espacios obligan a poner comillas en cada comando | Esta carpeta |
| **Pendiente:** el repositorio de GitHub es público | Solo tiene código y datos inventados; la seguridad no depende de que el código sea secreto | DISENO §17 (pendiente 8) |
| **Pendiente para la 1d:** en el PC de casa, borrar la BD de pruebas y separar el desarrollo con `COMPOSE_PROJECT_NAME=caudal-dev` antes de meter datos reales | Ahora el desarrollo y la instancia real usarían el mismo volumen | DISENO §17 (pendiente 9) |

---

## 12. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| El Mac iba 6 commits por detrás de GitHub | Se habían editado archivos desde la web de GitHub | `git pull` antes de empezar |
| Aviso de VS Code: *"An environment file is configured but terminal environment injection is disabled"* | La extensión de Python ve el `.env` | Ignorarlo; no activarlo, o metería la contraseña en todas las terminales |
| `psql` abría una especie de editor | Es el **paginador**: la salida no cabía a lo ancho | Salir con `q`, y usar siempre `-P pager=off` |
| La app salía con el código 3: *Attribute "app" not found in module "app.main"* | `main.py` estaba **vacío**: se creó pero no se guardó | Crear los archivos con bloques `cat > … <<'EOF'` desde la terminal |
| La app salía con el código 1: *NameError: name 'cat' is not defined* | El bloque `cat > …` se pegó **dentro del archivo abierto** en el editor, no en la terminal | `sed -i '' -e '/^cat > backend\/app\//d' -e '/^EOF$/d' …`, y a partir de ahí hacer clic en la terminal antes de pegar |
| `WARN: DuplicateStageName "dev"` | El bloque con `cat >>` (añadir al final) se pegó dos veces | Reescribir el Dockerfile entero con `cat >` |
| `ruff`: `W291 Trailing whitespace` en `Revises: ` | La plantilla de Alembic deja un espacio cuando no hay migración anterior | `sed -i '' 's/^Revises: $/Revises:/' …`. Solo pasa en la primera migración |
| `ruff format --check` marcaba la migración | Alembic no escribe con el estilo de ruff | `docker compose run --rm tests ruff format .` |
| Windows: `warning: LF will be replaced by CRLF` en todos los archivos nuevos | `core.autocrlf true` habría pasado los archivos a `CRLF`, y Prettier fallaría | `.gitattributes` con `* text=auto eol=lf` + `git add --renormalize .` |
| Windows: los bloques `cat > … <<'EOF'` no funcionan | PowerShell no tiene *heredoc* | Pegarlos en **Git Bash** |
| Git Bash: `docker run -v "$PWD/…:/…"` | Git Bash convierte las rutas al estilo de Windows | Usar servicios de compose (`docker compose run --rm web …`) o `MSYS_NO_PATHCONV=1` |
| VS Code: *"Failed to save… The content of the file is newer"* | Una pestaña abierta desde la 1.4 tenía una versión vieja de la migración, que después habían cambiado `ruff`, `sed` y `git pull` | No sobrescribir: cerrar la pestaña sin guardar y `git restore` del archivo. Cerrar los archivos que solo se abren para leer |
| `npm ci` se quedaba cargando en la red de la universidad | La red ralentiza la descarga de paquetes de `registry.npmjs.org` | Esperar (tardó un par de minutos) o compartir datos del móvil. Después quedan guardados en el volumen |
| Tras entrar desde `/api/docs`, la app no mostraba el panel | La app solo pregunta "¿quién soy?" al cargarse | Recargar la pestaña de la app (Cmd+R) |
| Con `TRUNCATE users` el login daba 401 | Se habían borrado los usuarios de prueba para ver el asistente | Volver a crearlos con el asistente o con `POST /api/setup` |
| En móvil, la barra lateral ocupaba media pantalla | Con una sola columna, CSS Grid repartía la altura entre las dos filas | `grid-template-rows: auto 1fr` |

---

## 13. Chuleta de comandos

```bash
# --- Arrancar, parar, ver ---
docker compose up -d --build --wait        # construir si hace falta y arrancar
docker compose ps                          # estado (healthy)
docker compose logs app --tail 50          # últimos logs de la app
docker compose restart app
docker compose down                        # parar (los datos se quedan)
docker compose down -v                     # ⚠️ parar y BORRAR la BD

# --- Comprobar ---
curl http://localhost:8080/api/health      # en PowerShell: curl.exe
# Navegador: http://localhost:8080  ·  API: http://localhost:8080/api/docs

# --- Tests y lint ---
docker compose run --rm tests                        # pytest
docker compose run --rm --build tests                # reconstruyendo la imagen dev
docker compose run --rm tests ruff check .
docker compose run --rm tests ruff format .          # formatear
docker compose run --rm tests ruff format --check .  # solo comprobar
docker compose run --rm web                          # npm ci + lint + build del frontend

# --- Frontend en vivo (desarrollo) ---
docker compose --profile dev up -d vite    # http://localhost:5173 (recarga al guardar)
docker compose logs vite --tail 5          # listo cuando pone "Local: http://localhost:5173/"
docker compose stop vite                   # pararlo (y antes de "run --rm web")

# --- Usuarios de prueba ---
docker compose exec db psql -U caudal -d caudal -P pager=off -c "TRUNCATE users CASCADE;"   # volver a ver el asistente
docker compose exec db psql -U caudal -d caudal -P pager=off -c "UPDATE users SET locked_until = NULL, failed_attempts = 0;"   # desbloquear

# --- Base de datos ---
docker compose exec db psql -U caudal -d caudal -P pager=off -c "\dt"
docker compose exec db psql -U caudal -d caudal -P pager=off -c "\d transactions"
docker compose exec db psql -U caudal -d caudal -P pager=off -c "SELECT * FROM alembic_version;"

# --- Migraciones ---
docker compose run --rm --user root -v "$PWD/backend:/app" app \
  alembic revision --autogenerate -m "describe el cambio"   # en Git Bash: MSYS_NO_PATHCONV=1 delante

# --- Locks ---
docker compose run --rm web npm install --package-lock-only --no-audit --no-fund
docker run --rm -v "$PWD/backend:/app" -w /app python:3.12-slim \
  sh -c "pip install -q --root-user-action=ignore uv==0.11.32 && uv lock"

# --- Git ---
git pull                                   # al empezar
git add -A && git commit -m "feat: ..." && git push   # al acabar cada parte
git check-ignore -v .env                   # ¿qué regla lo ignora?
git check-attr eol -- archivo              # ¿qué final de línea usa?

# --- Diferencias entre equipos ---
# sed:    Mac → sed -i '' '…' archivo   ·   Git Bash → sed -i '…' archivo
# curl:   PowerShell → curl.exe
# heredoc (cat > … <<'EOF'): zsh (Mac) o Git Bash (Windows), nunca PowerShell
```

---

## 14. Glosario

| Término | Qué es |
|---|---|
| **Docker Compose** | Herramienta que arranca varios contenedores juntos (`db` + `app`) a partir de `docker-compose.yml` |
| **Volumen** | Almacenamiento de Docker que sobrevive a los contenedores (`caudal_pgdata`) |
| **Healthcheck** | Comando periódico con el que Docker sabe si un contenedor funciona (`healthy`) |
| **Perfil (compose)** | Servicios que solo se usan si se piden (`tests` y `web`, perfil `dev`) |
| **Build multietapa** | Dockerfile con varias etapas (`FROM … AS nombre`); la final copia solo lo necesario |
| **Lock** | Archivo con las versiones exactas de todas las dependencias (`uv.lock`, `package-lock.json`) |
| **uv** | Gestor de paquetes de Python, rápido y con lock |
| **FastAPI** | Framework web de Python para crear la API |
| **Uvicorn** | Servidor que ejecuta la app FastAPI |
| **ORM / SQLAlchemy** | Librería que traduce entre clases de Python y tablas de la BD |
| **Migración / Alembic** | Script versionado que cambia el esquema de la BD / la herramienta que los gestiona |
| **Dependencia (FastAPI)** | Función que FastAPI ejecuta y pasa a un endpoint (`Depends(get_db)`) |
| **Fixture (pytest)** | Preparación reutilizable para los tests (`client`, `database`) |
| **Lint** | Revisión automática del código en busca de errores y malas prácticas (ruff, ESLint) |
| **Formateador** | Herramienta que deja el código con un estilo uniforme (ruff format, Prettier) |
| **Vite** | Herramienta que compila el frontend (TS + React → HTML, CSS y JS) |
| **SPA** | Aplicación de una sola página: el servidor da siempre `index.html` y React elige la pantalla |
| **Heredoc** | `cat > archivo <<'EOF' … EOF`: escribir un archivo con el texto que va hasta `EOF` |
| **Git Bash** | Terminal de Linux (bash) que viene con Git for Windows |
| **Paginador** | Visor de salidas largas (`less`); se sale con `q` |
| **Argon2** | Algoritmo de hash lento y con sal para guardar contraseñas |
| **Hash** | Huella de un dato que no se puede deshacer; sirve para comprobar sin guardar el original |
| **Sal** | Valor aleatorio que se mezcla con la contraseña para que dos iguales den hashes distintos |
| **Token de sesión** | Valor aleatorio de la cookie que identifica una sesión |
| **Cookie `HttpOnly` / `SameSite`** | Atributos que impiden leer la cookie desde JavaScript / enviarla desde otras webs |
| **401 / 403 / 404 / 409 / 422 / 429** | No autenticado / sin permiso / no existe / conflicto / datos no válidos / demasiados intentos |
| **Router (FastAPI)** | Grupo de endpoints con un prefijo común (`/api/auth`) |
| **Contexto (React)** | Datos compartidos por todas las pantallas sin pasarlos a mano (`AuthProvider`) |
| **Proxy** | Servidor intermedio que reenvía peticiones (Vite reenvía `/api` a la app) |
| **React Router** | Librería que decide qué pantalla mostrar según la URL |

---

**Siguiente fase:** 1b, importadores de imagin y Wise. Para empezarla, en una conversación nueva del proyecto, con los dos ejemplos adjuntos (`samples/imagin_ejemplo.xlsx` y `samples/wise_ejemplo.xlsx`):
```text
Empezamos la Fase 1b de Caudal (importadores imagin + Wise). Te adjunto los ejemplos inventados. Sigue CLAUDE.md.
```
