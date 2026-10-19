# Changelog de Caudal

Aquí se apunta qué se hace en cada fase. El formato está en `CLAUDE.md` (sección 9).

## [0.1.0] – 2026-10-19 · Fase 1a
### Añadido
- Docker Compose con `db` (PostgreSQL 16, volumen `pgdata`, healthcheck) y `app` (FastAPI + frontend compilado, puerto `APP_PORT`, healthcheck en `/api/health`). Servicios de desarrollo en el perfil `dev`: `tests` (pytest y ruff), `web` (lint y build del frontend) y `vite` (frontend en vivo en `localhost:5173`).
- `.env.example`, `.gitignore`, `.gitattributes` (`* text=auto eol=lf`) y `.dockerignore`.
- Backend: `Dockerfile` en tres etapas (frontend con Node → runtime con Python → dev), dependencias fijadas con `uv.lock`, configuración con pydantic-settings y conexión con SQLAlchemy 2.
- Modelos `users`, `sessions`, `accounts`, `categories`, `transactions`, `rules` y `backup_log`, y la migración inicial `0001` de Alembic, que se aplica sola al arrancar la app.
- Inicio de sesión: contraseñas con hash Argon2; sesiones guardadas en la BD con el hash SHA-256 del token; cookie `HttpOnly` + `SameSite=Strict`; caducidad tras 30 minutos sin actividad; bloqueo de 5 minutos tras 5 intentos fallidos.
- API: `GET /api/setup/status`, `POST /api/setup`, `GET /api/auth/users`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET/POST/PATCH /api/accounts` y `GET /api/accounts/{id}`. Errores en castellano con el formato `{"detail": "…"}`.
- Frontend (Vite + React 19 + TypeScript 6, React Router 8): asistente de primer arranque, "¿Quién entra?", contraseña, y panel vacío con la barra lateral, el usuario y "Cerrar sesión", según la maqueta. Al caducar la sesión, vuelve a "¿Quién entra?" con un aviso. Las fuentes van dentro de la app (`@fontsource`).
- 31 tests: contraseñas, sesiones y caducidad, asistente, login, bloqueo, cuentas y **aislamiento entre usuarios** (404 al pedir recursos de otro).
- `docs/fases/FASE_1a.md`: qué se hizo, cómo, decisiones, problemas y apuntes para aprender.
### Cambiado
- Sesiones en BD en lugar de firmadas: se quita `SESSION_SECRET` del `.env` y se añaden `LOGIN_MAX_ATTEMPTS` y `LOGIN_LOCKOUT_MIN`.
- Los tests van en `backend/tests/` (no en `tests/` en la raíz) y usan una BD aparte, `caudal_test`.
- Fuentes con `@fontsource` en lugar de Google Fonts.
- Forma de trabajar (CLAUDE.md): fases en partes pequeñas con un commit cada una, archivos como bloques `cat > … <<'EOF'` para pegar en la terminal, Git Bash en Windows y commits `wip:` al cambiar de equipo.
- Documentos de fases renombrados a `FASE_<n>.md`.
### Notas
- El asistente exige contraseñas de al menos 8 caracteres y distintas para Gerard y Padres.
- Pendiente de decidir: el repositorio de GitHub es público (DISENO, pendiente 8).
- Antes de meter datos reales en el PC de casa: borrar la BD de pruebas y separar la de desarrollo (DISENO, pendiente 9, Fase 1d).
- El logo definitivo se integrará cuando esté listo (`frontend/public/favicon.svg` y `frontend/src/Logo.tsx`).

## [0.0.1] – 2026-10-01 · Fase 0
### Añadido
- Entorno preparado en el portátil y en el PC de casa: WSL2, Docker Desktop (sin arranque automático, WSL limitado a 4 GB), Git y VS Code con sus extensiones.
- Repositorio privado en GitHub (`Yarart3/Caudal`), clonado en `C:\Users\gerar\Proyectos\caudal`.
- Ejemplos con **datos inventados**: `samples/imagin_ejemplo.xlsx` (7 filas, con dos compras idénticas el mismo día y una transferencia a Wise) y `samples/wise_ejemplo.xlsx` (4 filas, con la pareja de esa transferencia y pagos con venta del fondo monetario).
- Carpetas de backup: `CaudalBackups/` en el pendrive `Gerard` y en `OneDrive - udl.cat\Proyectos\CaudalBackups`.
- README: sección "Trabajar desde varios ordenadores".
- `docs/fases/FASE_0.md`: qué se hizo en la fase, cómo, decisiones, problemas resueltos y apuntes para aprender.
- DISENO: sección 6.0 (el extracto se sube tal cual; columnas por nombre; comprobación de que el archivo es del banco de la cuenta elegida).
### Cambiado
- El pendrive mantiene su nombre de volumen, `Gerard` (`USB_LABEL=Gerard`), en lugar de `CAUDAL_BK`.
- Los commits se escriben en inglés (Conventional Commits).
- Formato de imagin confirmado: todo texto, fecha `dd/mm/aaaa`, importes con dos decimales, conceptos en catalán y a veces en minúsculas (`BIZUM ENVIAT`, `BIZUM REBUT`, `enviament de dine`). Reglas de Bizum actualizadas.
- Formato de Wise confirmado: columna `Fecha y hora`, celdas vacías como texto vacío, venta del fondo en la misma fila que el pago, ingreso desde imagin como `CREDIT` + `DEPOSIT` con `imaginBank` en `Referencia del pago`.
- **Trade Republic y Scalable se llevan a mano** (sin importadores): efectivo de Trade Republic en Movimientos y compras y ventas con el formulario, con "duplicar operación" y posición inicial por producto.
- Fase 1b: las filas que no se pueden leer se listan con su error y se pueden añadir a mano (`errors` en `/api/imports`).
### Notas
- Pendiente de Gerard: elegir la contraseña de backup y apuntarla en papel antes de la Fase 1d.
- La cuenta de OneDrive de la UdL caducará al acabar la carrera: antes, cambiar `ONEDRIVE_DIR` (pendiente 7 de DISENO).
- Las capturas del README (`docs/capturas/`) se harán en la Fase 7.
- 2026-10-11: MacBook Air M5 (macOS, Apple Silicon) preparado como equipo principal de desarrollo (sección 16.1 de DISENO). La instancia real sigue en el PC de casa. Los comandos se dan primero en zsh y, si cambian, en PowerShell.

## [0.0.0] – 2026-10-01 · Diseño
### Añadido
- Documento de diseño (`docs/DISENO.md`) con las decisiones, el modelo de datos, la lógica, los backups, la seguridad y el roadmap.
- Maqueta de referencia con tres pestañas: Patrimonio, Movimientos e Inversiones (`maqueta/caudal-maqueta.html`).
- `README.md`, `CLAUDE.md` e `INSTRUCCIONES_PROYECTO_CLAUDE.md`.
### Notas
- Pendiente para la Fase 0: ruta de OneDrive, ejemplos inventados de imagin y Wise, y comprobar si la `Fecha` de imagin es fecha o texto.
- Pendiente para la Fase 3: qué exportan Trade Republic y Scalable.
