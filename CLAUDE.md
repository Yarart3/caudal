# CLAUDE.md: cómo trabajar en Caudal, de la Fase 0 al final

> Este archivo es para **Claude**. Explica cómo arrancar, ejecutar y cerrar **cada fase** del proyecto hasta terminarlo entero.
> Léelo **al principio de cada conversación**, junto con `docs/DISENO.md`.

---

## 1. Documentos y prioridad

| Documento | Qué es | Prioridad |
|---|---|---|
| Lo que diga Gerard en la conversación | Instrucción actual | 1 (manda sobre todo; si contradice un documento, avisa y propón actualizarlo) |
| `docs/DISENO.md` | **Fuente de verdad**: decisiones, formatos de bancos, modelo de datos, lógica, backups, seguridad, roadmap | 2 |
| `CLAUDE.md` (este archivo) | Cómo trabajar y el detalle de cada fase | 3 |
| `maqueta/caudal-maqueta.html` | Diseño visual de referencia (datos inventados) | 4 |
| `README.md` | Presentación del proyecto (se actualiza al cerrar cada fase) | — |
| `CHANGELOG.md` | Qué se ha hecho en cada fase. **Sirve para saber en qué punto está el proyecto.** | — |

## 2. Con quién trabajas

- **Gerard**, estudiante de 4º de Ingeniería Informática. Sabe programar; no hace falta explicar lo básico, pero sí **por qué** se elige cada cosa cuando no es obvio.
- Desarrolla sobre todo en un **MacBook Air M5** (macOS, Apple Silicon, zsh). También tiene un portátil y el PC de casa con **Windows** (PowerShell); la instancia real, con los datos de verdad, funciona en el PC de casa. Todo tiene que funcionar en los dos sistemas.
- Prefiere **archivos completos y comandos exactos para copiar y pegar**, paso a paso, en **español**.
- Valora la **honestidad**: si algo es mala idea o tiene riesgos, díselo y propón una alternativa.
- Los usuarios finales son **Gerard** y **sus padres** (que no son técnicos).

## 3. Lenguajes, versiones y convenciones

### Lenguajes
| Parte | Lenguaje | Stack |
|---|---|---|
| Backend | **Python 3.12** | FastAPI, SQLAlchemy 2 (estilo `Mapped[...]`), Alembic, Pydantic v2, openpyxl, python-multipart, argon2-cffi, httpx, APScheduler, cryptography, pytest, ruff |
| Frontend | **TypeScript** (`strict`) | React + Vite, React Router, Recharts, ESLint + Prettier |
| Base de datos | **SQL** | PostgreSQL 16 |
| Infraestructura | YAML, Batch, Bash | Docker Compose, scripts `.bat` (Windows) y `.command` (Mac) |

- Usa las **versiones estables actuales** al empezar la Fase 1a y **fíjalas** (`pyproject.toml` + lock, `package.json` + `package-lock.json`, imágenes Docker con etiqueta concreta: `python:3.12-slim`, `postgres:16`, `node:<LTS>`). No uses versiones beta.
- Si dudas de que una API de una librería exista en la versión fijada, dilo y propón cómo comprobarlo. **No inventes funciones.**

### Idioma del código
- **Identificadores del código, tablas y columnas: en inglés.** Textos de la interfaz, mensajes de error al usuario y documentación: en **castellano**. Los comentarios pueden ir en castellano.
- **Equivalencia con `docs/DISENO.md`:**

| DISENO.md | Código / BD |
|---|---|
| usuarios | `users` |
| cuentas (tipo gasto / inversion / mixta) | `accounts` (`kind`: `spending` / `investment` / `mixed`) |
| categorias | `categories` |
| movimientos | `transactions` (concepto → `description`) |
| estado_categoria (auto / manual / revisar) | `category_status` (`auto` / `manual` / `review`) |
| es_transferencia_interna | `is_internal_transfer` |
| huella | `fingerprint` |
| reglas | `rules` |
| formatos_importacion | `import_formats` |
| productos | `products` |
| operaciones_inversion | `investment_operations` |
| precios | `prices` |
| valores_manuales | `manual_valuations` |
| objetivos | `goals` |
| registro_backups | `backup_log` (destino → `destination`: `usb` / `onedrive`) |
| sesiones | `sessions` (`token_hash`, `last_seen_at`) |
| subtipo_liquidez (efectivo / fondo_monetario) | `accounts.liquidity_type` (`cash` / `money_market`) |

### Reglas técnicas
- **Dinero:** `Decimal` en Python y `NUMERIC(12,2)` en la BD; participaciones con `NUMERIC(18,8)`; precios con `NUMERIC(18,6)`. **Nunca `float`** para importes. En el frontend, el dinero viaja como **string** en el JSON y se formatea con `Intl.NumberFormat('es-ES', {style:'currency', currency:'EUR'})`. Ojo: `es-ES` no agrupa los miles en números de 4 cifras; usa `useGrouping: 'always'` o un formateador propio para que salga `1.234 €`.
- **Fechas:** tipo `DATE` para movimientos y `TIMESTAMPTZ` para eventos; zona horaria `Europe/Madrid`.
- **API:** todo bajo `/api/...`, JSON, errores con `{"detail": "mensaje en castellano"}`, autenticación con cookie de sesión. **Cada endpoint filtra por el usuario de la sesión.**
- **Migraciones:** todo cambio de esquema va con una migración de Alembic. Nunca `create_all` en producción.
- **Configuración:** solo por `.env`. Nada escrito a fuego (rutas, contraseñas, puertos).
- **Calidad:** `ruff check` + `ruff format`, `pytest`, `npm run lint`, `npm run build` sin errores antes de dar una fase por buena. Todo se ejecuta en Docker: `docker compose run --rm tests`, `docker compose run --rm tests ruff check .`, `docker compose run --rm tests ruff format --check .` y `docker compose run --rm web`.
- **Commits:** en **inglés**, en imperativo y con el estilo Conventional Commits: `feat: …`, `fix: …`, `docs: …`, `test: …`, `chore: …` (por ejemplo, `docs: keep USB volume label Gerard`). Se hace commit y push **al final de cada parte** de la fase, directamente en `main`. Si Gerard cambia de equipo a mitad de una parte: commit `wip: …` y push.

## 4. Protocolo de cada conversación

### Al empezar
1. **Lee** `docs/DISENO.md` y este archivo.
2. **Averigua el estado.** Pide a Gerard, en una sola petición:
   - qué dice `CHANGELOG.md` (o qué fase cerró la última vez);
   - la salida de `git log --oneline -10` y `git status`;
   - si la fase toca código ya existente, los archivos concretos que vas a modificar (no todo el proyecto).
3. **Comprueba los prerrequisitos** de la fase (sección 7). Si falta algo, pídelo antes de escribir código.
4. **Presenta el plan** en 3 a 6 líneas: qué vas a hacer, en qué orden, qué archivos se crean o cambian y qué necesitas de él. Si la fase es grande, divídela en **pasos** que se puedan probar por separado.

### Durante
5. Entrega **paso a paso**. Cada paso, con:
   - los **archivos completos** con su ruta;
   - los **comandos exactos** en zsh (Mac) y, si cambian, en PowerShell (Windows);
   - **cómo comprobar** que funciona (qué debería ver o qué test debería pasar).
6. Espera la confirmación ("funciona" o el error) antes del siguiente paso, salvo que Gerard pida todo de golpe.
7. Ante un error: pide la salida exacta (`docker compose ps`, `docker compose logs app --tail 100`, la traza de `pytest`, la consola del navegador), encuentra la **causa raíz**, explícala en 1-2 frases y corrige.

### Al terminar la fase
8. Repasa los **criterios de "hecho"** de la fase uno a uno, con Gerard.
9. Entrega las actualizaciones de documentación:
   - **`CHANGELOG.md`:** una entrada nueva para la fase (sección 9).
   - **`README.md`:** estado del roadmap (⬜ → ✅) y lo que cambie en instalación o uso.
   - **`docs/DISENO.md`:** solo si cambió alguna decisión, con el texto exacto que hay que sustituir.
   - **`docs/fases/FASE_<n>.md`** (por ejemplo, `FASE_1a.md`): qué se ha hecho y cómo (comandos y archivos), decisiones, problemas encontrados y su solución, **apuntes para aprender** los conceptos nuevos, chuleta de comandos y glosario. Mismo formato que `docs/fases/FASE_0.md`.
10. Propón el **mensaje de commit** y el comando (`git add -A` + `git commit -m "…"`).
11. Termina con el **mensaje para empezar la siguiente fase** en un chat nuevo (copia el de la sección 7).

## 5. Formato de entrega

- **Fases en partes pequeñas** (1.1, 1.2…), cada una con sus comprobaciones y su commit. El estado de la fase se lleva en `docs/fases/FASE_<n>.md`.
- **Archivos como bloques para pegar en la terminal:** `cat > ruta <<'EOF' … EOF`, con la **ruta completa desde la raíz** (por ejemplo `backend/app/importers/imagin.py`). Funcionan en zsh (Mac) y en **Git Bash** (Windows); en PowerShell no. Recordar que se pegan en la terminal, no en un archivo abierto, y una sola vez. Después de cada bloque, `wc -l` para comprobar que ningún archivo quedó vacío.
- Antes de entregar, **probarlo**: ruff, pytest, lint y build y, si hay pantallas, en un navegador.
- **Archivo nuevo o cambio grande:** entero. **Cambio pequeño en un archivo largo:** indica exactamente qué bloque sustituir, con el texto anterior y el nuevo.
- **Comandos:** siempre desde la raíz del proyecto (`caudal/`), en zsh (Mac); si en Windows son distintos, añade debajo los de Git Bash o PowerShell. Diferencias habituales: `sed -i ''` (Mac) / `sed -i` (Git Bash); `curl.exe` en PowerShell; `psql` siempre con `-P pager=off`.
- **Sin TODOs**, sin `pass` de relleno y sin "implementa aquí". Si algo queda fuera a propósito, dilo y en qué fase se hará.
- No repitas archivos que no cambian.

## 6. Contrato de la API (previsto)

| Fase | Método y ruta | Uso |
|---|---|---|
| 1a | `GET /api/setup/status` · `POST /api/setup` | Saber si hay usuarios y crear los iniciales |
| 1a | `GET /api/auth/users` | Tarjetas de "¿Quién entra?" (solo nombre visible, inicial y color) |
| 1a | `POST /api/auth/login` · `POST /api/auth/logout` · `GET /api/auth/me` | Sesión |
| 1a | `GET/POST/PATCH /api/accounts` · `GET /api/accounts/{id}` | Cuentas del usuario (404 si es de otro) |
| 1b | `POST /api/imports` (multipart: `account_id` + archivo, máx. 5 MB) | Importar extracto → `{read, new, duplicates, review, internal, errors, warnings, closing_balance, closing_date}` (`errors`: lista de `{row, field, value, message}`) |
| 1b | `POST /api/transactions` | Alta manual de un movimiento (filas que no se han podido leer); busca pareja de transferencia |
| 1c | `GET /api/transactions?month=&q=&category=&status=` · `PATCH /{id}` · `DELETE /{id}` | Movimientos |
| 1c | `GET/POST/PATCH/DELETE /api/categories` · `/api/rules` · `POST /api/rules/apply` | Categorías y reglas |
| 1c | `GET /api/dashboard/net-worth?month=` · `GET /api/dashboard/cashflow?month=` | Datos de Patrimonio y Movimientos |
| 1d | `GET /api/backups/status` · `POST /api/backups/run` | Indicador y backup manual |
| 2 | `GET/PUT /api/budgets` · `GET /api/alerts` · `GET /api/recurring` · `GET/PUT /api/goals` | Control del gasto |
| 3 | `GET /api/products/search?q=` · `GET/POST/PATCH /api/products` | Productos |
| 3 | `GET/POST/PATCH/DELETE /api/investments/operations` · `POST /api/investments/import` | Operaciones |
| 3 | `GET /api/investments/summary` · `GET /api/investments/positions` · `GET /api/investments/benchmark` | Pestaña Inversiones |
| 3 | `POST /api/prices/refresh` · `GET /api/prices/status` | Precios |
| 4 | `GET/POST/PATCH /api/admin/users` · `POST /api/admin/users/{id}/reset-password` · `GET/POST /api/import-formats` | Administración y asistente genérico |

Si durante una fase conviene cambiar el contrato, se cambia y se actualiza esta tabla.

## 7. Las fases, de principio a fin

Orden obligatorio: **0 → 1a → 1b → 1c → 1d → 2 → 3 → 4 → 5 → 6 → 7**. La Fase 6 (Mac) puede hacerse en cualquier momento después de la 1d; el Mac ya está preparado para desarrollar desde el 2026-10-11 (sección 16.1 de DISENO). La 7 es opcional.

---

### Fase 0: preparar el entorno
- **Objetivo:** dejar el PC listo, sin escribir código de la app.
- **Prerrequisitos:** ninguno.
- **Necesito de Gerard:** nada al empezar; durante la fase, capturas o salidas de comandos si algo falla.
- **Pasos:**
  1. Comprobar que la **virtualización** está activada (Administrador de tareas → Rendimiento → CPU → "Virtualización: habilitada"; si no, activarla en la BIOS). Instalar **WSL2** (`wsl --install`) y **Docker Desktop**, y desactivar *"Start Docker Desktop when you sign in"*. Limitar la memoria de WSL con `%UserProfile%\.wslconfig` (`[wsl2]` + `memory=4GB`), para que Docker no le quite RAM al resto del PC. Comprobar con `docker run hello-world`.
  2. Instalar Git y VS Code (extensiones: Python, Pylance, Ruff, ESLint, Prettier, Docker). Configurar `git config --global user.name/user.email`.
  3. Crear la carpeta `caudal/` con README, CLAUDE.md, CHANGELOG.md, INSTRUCCIONES, `docs/` y `maqueta/`. `git init`, primer commit. Repositorio **privado** en GitHub (opcional).
  4. Pendrive: se mantiene su nombre de volumen `Gerard` (exFAT) y se crea la carpeta `CaudalBackups/`.
  5. Carpeta `CaudalBackups/` en OneDrive y su **ruta exacta** (`Get-ChildItem $env:USERPROFILE -Filter "OneDrive*"`).
  6. `samples/imagin_ejemplo.xlsx` y `samples/wise_ejemplo.xlsx` con **datos inventados**, sin romper el formato. Comprobar si la `Fecha` de imagin es fecha de Excel o texto.
  7. (Opcional, no bloquea) Mirar qué exportan Trade Republic y Scalable. **Resuelto:** se llevan a mano (sección 6.3 de DISENO).
- **Hecho cuando:** `docker run hello-world` funciona; el repositorio tiene el primer commit; existen los dos ejemplos; se conoce la ruta de OneDrive.
- **Mensaje para empezar:** `Empezamos la Fase 0 de Caudal. Sigue CLAUDE.md.`

---

### Fase 1a: base del proyecto + inicio de sesión
- **Objetivo:** el esqueleto completo funcionando en Docker, con login y dos usuarios aislados.
- **Prerrequisitos:** Fase 0.
- **Necesito de Gerard:** la ruta de OneDrive del equipo en el que trabaje (para el `.env`; las dos están en la sección 10 de DISENO), aunque los backups no se implementen hasta la 1d.
- **Entregables:**
  - `docker-compose.yml` (`app` + `db`, volumen `pgdata`, puerto `APP_PORT`, healthcheck de la BD), `.env.example`, `.gitignore` (sección 13 de DISENO), `.dockerignore`.
  - `.gitattributes` con los finales de línea correctos: `*.bat` y `*.cmd` → `eol=crlf`; `*.sh`, `*.command` y `*.py` → `eol=lf`. Así los scripts funcionan en Windows y en Mac.
  - Rutas con espacios (por ejemplo, `OneDrive - udl.cat`) **siempre entre comillas** en `.env`, `docker-compose.yml` y los scripts.
  - `backend/`: `Dockerfile` multietapa (construye el frontend con Node y lo sirve FastAPI como estáticos), `pyproject.toml`, `app/main.py`, `app/config.py` (pydantic-settings), `app/db.py`, modelos `users`, `accounts`, `categories`, `transactions`, `rules`, `backup_log`, migración inicial de Alembic, `app/auth/` (hash Argon2, sesiones en BD con el hash del token, caducidad por inactividad, bloqueo tras 5 intentos), endpoints de setup, auth y accounts.
  - `frontend/`: Vite + React + TS, estilos según la maqueta (variables CSS de la sección 14 de DISENO, fuentes Space Grotesk y Manrope), pantallas **Asistente de primer arranque**, **"¿Quién entra?"**, **Contraseña** y un **panel vacío** con la barra lateral, el usuario y "Cerrar sesión".
  - `backend/tests/`: login correcto e incorrecto, bloqueo, caducidad y **aislamiento** (el usuario A recibe 404 al pedir recursos de B).
- **Hecho cuando:** `docker compose up -d --build` → `http://localhost:8080` muestra el asistente; se crean `gerard` (admin) y `padres`; cada uno entra y ve su panel vacío; los tests pasan; los datos sobreviven a `docker compose down` + `up`.
- **Mensaje para empezar:** `Empezamos la Fase 1a de Caudal (base + inicio de sesión). Sigue CLAUDE.md.`

---

### Fase 1b: importadores imagin + Wise
- **Objetivo:** importar extractos reales sin duplicados ni transferencias infladas.
- **Prerrequisitos:** 1a. Archivos `samples/imagin_ejemplo.xlsx` y `samples/wise_ejemplo.xlsx`.
- **Necesito de Gerard:** **los dos archivos de ejemplo adjuntos** (inventados). **No escribas el importador sin verlos.**
- **Entregables:**
  - `backend/app/importers/base.py` (interfaz común: `detect(workbook) -> bool`, `parse(workbook) -> ParseResult`, con los movimientos, las filas con error y los avisos de saldo), `imagin.py`, `wise.py` y un registro de importadores.
  - Normalización: importes `-14,50EUR` → `Decimal('-14.50')`; fechas como texto `dd/mm/aaaa` (aceptar también fecha de Excel); conceptos de imagin en catalán y a veces en minúsculas (`BIZUM ENVIAT`, `enviament de dine`); concepto de Wise (Comercio → beneficiario o pagador → Descripción); columnas ignoradas.
  - `fingerprint` según la sección 9.2 de DISENO; inserción con `ON CONFLICT DO NOTHING` sobre `(account_id, fingerprint)`.
  - `app/transfers/`: emparejar transferencias internas (sección 9.3), dentro del mismo usuario.
  - Comprobación del saldo: el saldo calculado frente al último `Saldo` del extracto (avisar si no cuadra).
  - `POST /api/imports` y pantalla **Importar** (elegir cuenta, arrastrar archivo, resumen "leídos / nuevos / ya existían / por revisar / internos / con error"). Las filas que no se pueden leer se listan con la fila y el dato que ha fallado, y se pueden **añadir a mano** desde esa pantalla.
  - Tests con `samples/`: lectura, signos, duplicados (importar dos veces = 0 nuevos), dos compras iguales el mismo día **no** se toman por duplicado (imagin) y emparejado de transferencias, y que una fila con un importe ilegible aparece en `errors` sin abortar el resto.
- **Hecho cuando:** importar dos veces el mismo archivo da 0 nuevos; el saldo cuadra con el extracto; una recarga imagin → Wise queda marcada como interna; los tests pasan.
- **Mensaje para empezar:** `Empezamos la Fase 1b de Caudal (importadores imagin + Wise). Te adjunto los ejemplos inventados. Sigue CLAUDE.md.`

---

### Fase 1c: categorización + pestañas Movimientos y Patrimonio
- **Objetivo:** la app ya es útil en el día a día.
- **Prerrequisitos:** 1b.
- **Necesito de Gerard:** que confirme o retoque las **categorías iniciales** (sección 9.4 de DISENO).
- **Entregables:**
  - Semilla de categorías y reglas por usuario al crearlo; motor de reglas (mayúsculas, sin acentos, prioridad); `category_status`.
  - Pantalla **Revisar** y el flujo "¿Aplicar siempre a 'X'?" → crea la regla y la reaplica a los pendientes.
  - **Estructura de 3 pestañas** (Patrimonio, Movimientos, Inversiones) con la barra lateral, igual que la maqueta.
  - **Movimientos:** 4 indicadores, ingresos vs gastos a 12 meses, gasto por categoría, tabla con buscador y filtros, alta, edición y borrado manual, botón de importar.
  - **Patrimonio:** indicadores, evolución y entidades **solo con liquidez** (saldo de referencia de cada cuenta + movimientos posteriores). Reparto por tipo con "Efectivo" y "Fondo monetario".
  - **Inversiones:** estado vacío "Todavía no hay inversiones".
  - Tests: reglas, reaplicación y totales del panel (que excluyen las internas).
- **Hecho cuando:** tras importar un mes real, todo lo que no sea Bizum queda categorizado; los totales del panel coinciden con una suma manual; se parece a la maqueta.
- **Mensaje para empezar:** `Empezamos la Fase 1c de Caudal (categorización + pestañas). Sigue CLAUDE.md.`

---

### Fase 1d: backups + accesos directos
- **Objetivo:** no perder nunca datos y abrir o cerrar la app con doble clic.
- **Prerrequisitos:** 1c. El pendrive `Gerard` con `CaudalBackups/` y la carpeta de OneDrive creados.
- **Necesito de Gerard:** la contraseña de backup en su `.env` (**nunca** en el chat).
- **Entregables:**
  - `app/backup/`: `pg_dump -Fc` → AES-256-GCM (clave por scrypt con sal aleatoria guardada en la cabecera del archivo) → `caudal_AAAA-MM-DD_HHMM.dump.enc`; rotación de 30; `backup_log`; los 4 disparadores (tras importar, cada 60 min si hubo cambios, al cerrar y al arrancar si hay más de 7 días).
  - Montaje de los destinos: OneDrive por `ONEDRIVE_DIR`; el pendrive lo **detecta el script de arranque** por su nombre de volumen y monta su ruta (si no está, el panel lo indica).
  - Indicador `Último backup · Pendrive ✓/✗ · OneDrive ✓/✗` y `POST /api/backups/run`.
  - Scripts `scripts/windows/`: `Caudal.bat` (abre Docker Desktop si hace falta y espera, detecta el pendrive, `docker compose up -d`, espera al healthcheck, abre el navegador), `Cerrar Caudal.bat` (backup y `down`), `Restaurar backup.bat`, `Restablecer contraseña.bat`. Equivalentes en `scripts/mac/*.command`.
  - Tests: cifrar y descifrar ida y vuelta, rotación y contraseña incorrecta.
- **Hecho cuando:** se hace una **restauración completa** sobre una base vacía, desde el pendrive y desde OneDrive, y los datos coinciden; con el pendrive desconectado, el aviso aparece y OneDrive sigue funcionando.
- **Mensaje para empezar:** `Empezamos la Fase 1d de Caudal (backups + accesos directos). Sigue CLAUDE.md.`

---

### Fase 2: control del gasto
- **Prerrequisitos:** 1d.
- **Necesito de Gerard:** presupuestos por categoría y objetivo de patrimonio (puede ser aproximado).
- **Entregables:** presupuestos mensuales (OK / Al límite ≥ 90 % / Superado), avisos (presupuesto superado, gasto muy por encima de la media de 3 meses, nuevo recurrente), detección de recurrentes (mismo concepto, importe ±10 %, periodicidad mensual o anual), selector de mes y comparativa con el anterior, objetivo de patrimonio con hitos. Con tests de recurrentes y avisos.
- **Hecho cuando:** Movimientos y Patrimonio se parecen a la maqueta completa con datos reales.
- **Mensaje para empezar:** `Empezamos la Fase 2 de Caudal (control del gasto). Sigue CLAUDE.md.`

---

### Fase 3: patrimonio e inversiones
- **Prerrequisitos:** 2.
- **Necesito de Gerard:** la lista de productos que tiene (ISIN o ticker y tipo: ETF o cripto), **sin cantidades**, para probar el buscador y los precios. Opcional: su `cartera.json` de RUMBO **con valores inventados** para probar el importador.
- **Entregables:**
  - Modelos `products`, `investment_operations`, `prices`, `manual_valuations`, `goals`; cuentas `mixed` (Trade Republic) e `investment` (Scalable), las dos con **alta manual** (sin importador).
  - `app/prices/`: clientes de Yahoo, Morningstar y CoinGecko con tiempo de espera, reintentos y caché; histórico; tarea cada `PRICE_REFRESH_MIN`; actualización al abrir si los precios tienen más de `PRICE_MAX_AGE_HOURS`; "último precio conocido" + aviso si está desactualizado. Solo se envían identificadores.
  - Buscador por ISIN, ticker o nombre, que comprueba que hay precio antes de guardar.
  - `app/investments/`: FIFO (lotes), plusvalía latente y realizada, **XIRR** (Newton con bisección de respaldo, o `pyxirr`), rentabilidad por año, peor caída, comparativa con IWDA / SXR8 / XEON repitiendo los flujos, TER anual, aportaciones y racha.
  - Formulario "+ Añadir compra / venta" (vía principal) con **duplicar operación**. Importadores: plantilla Excel/CSV (`plantilla_inversiones.py`, para el historial) y `rumbo.py` (`cartera.json`). **No** hay importadores de Trade Republic ni Scalable. Si se copia código de RUMBO: mantener su aviso MIT en `THIRD_PARTY_NOTICES.md`.
  - **Pestaña Inversiones** completa y **Patrimonio** con inversiones (evolución apilada, entidades con invertido + efectivo, reparto por tipo).
  - Tests: FIFO con ventas parciales, XIRR contra casos calculados a mano (y contra `XIRR` de Excel), dividendos, precio desactualizado, divisas.
- **Hecho cuando:** el valor de la cartera difiere menos del 1 % del que muestran los brokers el mismo día; los tests de FIFO y XIRR pasan; la pestaña se parece a la maqueta.
- **Mensaje para empezar:** `Empezamos la Fase 3 de Caudal (patrimonio e inversiones). Te paso la lista de productos que tengo (sin cantidades). Sigue CLAUDE.md.`

---

### Fase 4: los padres
- **Prerrequisitos:** 3 (o 2, si se quiere adelantar; no depende de inversiones).
- **Necesito de Gerard:** ejemplos **inventados** de CaixaBank y Sabadell.
- **Entregables:** importadores de CaixaBank y Sabadell; **asistente genérico** de importación con formatos guardados (`import_formats`); **Ajustes → Usuarios** (crear, desactivar, restablecer contraseña; solo admin); repaso de usabilidad (textos claros, botones grandes, uso en móvil por la red de casa).
- **Hecho cuando:** los padres importan y revisan un mes **solos**, desde su dispositivo.
- **Mensaje para empezar:** `Empezamos la Fase 4 de Caudal (los padres). Te adjunto los ejemplos inventados. Sigue CLAUDE.md.`

---

### Fase 5: inteligencia y extras
- **Prerrequisitos:** 4.
- **Entregables (Gerard elige y prioriza al empezar):** previsión del gasto del mes siguiente (media móvil + recurrentes); sugerencias de categoría con un **modelo local** (Ollama, opcional y desactivable; **nunca** APIs externas con datos reales); exportar informes (PDF / Excel); ganancias realizadas por año (informativo); multidivisa en Wise; etiquetas, notas, deshacer importación, tema oscuro, "solo largo plazo".
- **Hecho cuando:** lo elegido funciona, con tests.
- **Mensaje para empezar:** `Empezamos la Fase 5 de Caudal. Repasa los extras y ayúdame a priorizar. Sigue CLAUDE.md.`

---

### Fase 6: migración a Mac
- **Estado:** el Mac ya está preparado para desarrollar (sección 16.1 de DISENO). Esta fase es solo para pasar al Mac la **instancia real**, que hasta entonces sigue en el PC de casa.
- **Prerrequisitos:** 1d como mínimo.
- **Pasos:** sección 16.2 de DISENO. Comprobar los scripts `.command`, la ruta de OneDrive en el Mac, `/Volumes/Gerard` y que las imágenes de Docker funcionan en ARM.
- **Hecho cuando:** se restaura el último backup en el Mac y los totales coinciden con los del PC.
- **Mensaje para empezar:** `Empezamos la Fase 6 de Caudal (migración a Mac). Sigue CLAUDE.md.`

---

### Fase 7 (opcional): versión para el CV
- **Entregables:** generador de **datos 100 % inventados**, instancia demo separada, README público en GitHub con capturas, CI (GitHub Actions: lint + tests + build), licencia, despliegue de la demo. **Nunca** se conecta a la instancia real.
- **Mensaje para empezar:** `Empezamos la Fase 7 de Caudal (versión demo para el CV). Sigue CLAUDE.md.`

## 8. Proyecto terminado

El proyecto se da por **terminado** (v1.0) cuando:
- [ ] Las fases 0 a 4 están cerradas y la 6 hecha (si ya hay Mac).
- [ ] Gerard y sus padres lo usan al menos **un mes seguido** importando sus extractos.
- [ ] Se ha probado una **restauración real** de backup.
- [ ] Todos los tests pasan y el README describe la instalación y el uso reales.
- [ ] `CHANGELOG.md` tiene la entrada `1.0.0`.

**Después del 1.0 (mantenimiento):**
- Si un banco cambia el formato del extracto: pedir un ejemplo inventado nuevo, ajustar el importador y añadir el test.
- Si una fuente de precios deja de funcionar: cambiar de fuente sin tocar los cálculos (por eso `app/prices/` está aislado).
- Revisar las dependencias cada pocos meses.
- **Antes de que Gerard se gradúe:** cambiar `ONEDRIVE_DIR` a una nube personal y copiar ahí los backups.

## 9. Formato de CHANGELOG.md

```markdown
## [0.2.0] – AAAA-MM-DD · Fase 1b
### Añadido
- Importadores de imagin y Wise con detección de duplicados.
### Cambiado
- …
### Corregido
- …
### Notas
- Decisiones o pendientes que salen de esta fase.
```

Versiones: Fase 0 = `0.0.1`, Fase 1a = `0.1.0`, 1b = `0.2.0`, 1c = `0.3.0`, 1d = `0.4.0`, 2 = `0.5.0`, 3 = `0.6.0`, 4 = `0.7.0`, 5 = `0.8.0`, proyecto terminado = `1.0.0`.

## 10. Reglas que no se rompen nunca

1. **No pidas ni uses datos reales.** Si Gerard pega datos reales, avísale y no los reutilices. Los ejemplos, siempre inventados.
2. **No inventes formatos** de bancos ni de brokers: pide un ejemplo.
3. **Nunca** expongas la app a internet ni sugieras abrir puertos.
4. **Nunca** envíes datos financieros a APIs externas (tampoco a IAs). Para los precios, solo identificadores.
5. **Nunca `float`** para el dinero.
6. **Cada consulta filtra por usuario.** Todo endpoint nuevo lleva su test de aislamiento.
7. **Contraseñas y secretos solo en `.env`**, nunca en el código, en el chat ni en git.
8. **No des la fase por terminada** sin repasar sus criterios de "hecho".
9. Caudal **no da recomendaciones de inversión**: muestra datos.
