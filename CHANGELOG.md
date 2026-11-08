# Changelog de Caudal

Aquí se apunta qué se hace en cada fase. El formato está en `CLAUDE.md` (sección 9).

## [Sin publicar] · Fase R (en curso)
### Añadido
- **Sincronización entre el Mac y el PC** por los backups cifrados de Google Drive (`backend/app/sync/`, migración `0008`): versión de cada base con identificador y su historia, candado `caudal-sync.json` y `python -m app.sync open | close | status | adopt`. Al abrir restaura sola la última versión, espera a que baje de Drive, pregunta si los dos equipos tienen cambios (y guarda las dos en `conflictos/`), no abre si está abierto en el otro equipo y pide `git pull` si la copia es de un código más nuevo.
- «Última copia: equipo, fecha y hora» en «¿Quién entra?» (`GET /api/sync/status`, sin sesión).
- «Restaurar backup» lista también las copias de `conflictos/`.
- Variables del `.env`: `DEVICE_NAME` (`mac` / `pc`) y `USB_FOLDER` (carpeta del pendrive de cada instancia).
- 70 tests nuevos (693 en total), con dos «equipos» de verdad (dos bases y una carpeta de Drive compartida).
- `docs/fases/FASE_R.md`.
### Cambiado
- El destino en la nube es **Google Drive** con una cuenta solo para Caudal. En el código se llama `cloud` (`CLOUD_DIR`, `/backups/cloud`; migración `0007` para `backup_log`).
- Los scripts de abrir, cerrar y restaurar usan la sincronización. «Caudal» reconstruye la imagen antes de abrir, para no arrancar con el código viejo después de un `git pull`.
- **Pendrive en Windows:** ya no se monta en Docker (no ve las unidades extraíbles). La app guarda sus copias en `backups\pendrive` y los scripts las llevan al pendrive al abrir y al cerrar, y las traen antes de restaurar.
- «Restablecer contraseña» cuenta como cambio sin copia.
### Corregido
- `«�` en el aviso del pendrive de los scripts del Mac (bash 3.2).
### Notas
- Instancia real y de desarrollo separadas en cada equipo (pendiente 9). Pendiente 12 resuelto.
- Quedan R.4 (movimientos reales), R.5 (inversiones reales) y R.6 (arreglos).

## [0.6.0] – 2026-11-05 · Fase 3
### Añadido
- **Inversiones** (migraciones `0004`, `0005` y `0006`): productos (ETF, acciones, fondos, cripto, planes, materias primas), operaciones (compra, venta, dividendo y comisión), precios, valores anotados a mano, tipos de cambio y cierres de los índices de referencia.
- **Precios automáticos** de Yahoo Finance (`backend/app/prices/`): histórico, paso a euros con tipos de cambio, aviso de precio desactualizado, refresco al arrancar y cada `PRICE_REFRESH_MIN`, botón «↻ Actualizar precios» y el comando `python -m app.prices probe|quote`. Solo viajan símbolos, nunca cantidades.
- **Productos:** buscador por ISIN, símbolo o nombre, con vista previa del precio; no se guardan si no tienen precio.
- **Operaciones** con «+ Añadir compra / venta», «Duplicar» y «Editar», sin vender nunca más de lo que hay en la cuenta.
- **Plantilla Excel/CSV** para cargar el historial: descarga, vista previa y confirmar (todo o nada, sin duplicados al reimportar).
- **Cálculos** (`backend/app/investments/`): FIFO por producto, plusvalía latente y realizada, TIR (XIRR), rentabilidad por año (Dietz modificado), peor caída, aportaciones y racha, coste anual por TER y comparativa «¿Y si todo fuera a un indexado?» con MSCI World (IWDA), S&P 500 (SXR8) y monetario del euro (XEON).
- API: `/api/products`, `/api/investments/operations`, `/api/investments/template`, `/api/investments/import`, `/api/investments/summary`, `/api/investments/positions`, `/api/investments/benchmark`, `/api/prices/status` y `/api/prices/refresh`.
- **Pestaña Inversiones completa:** indicadores, «Mis posiciones», aportaciones, comparativa, dividendos, rentabilidad por año, riesgo y costes, y debajo operaciones, productos, importar y cuentas.
- **Patrimonio con inversiones:** patrimonio neto = liquidez + inversiones, evolución apilada, entidades con invertido + efectivo, reparto por tipo de producto y objetivo que cuenta las inversiones.
- 296 tests nuevos (623 en total), con casos de FIFO y TIR calculados a mano, el ejemplo de `XIRR` de Excel y aislamiento entre usuarios en cada endpoint nuevo.
- `docs/fases/FASE_3.md`.
### Cambiado
- `GET /api/dashboard/net-worth` da también `investments_gain`, `investments_by_kind` y lo invertido de cada cuenta (`invested`).
- Configuración de los precios en el `.env`: `PRICE_REFRESH_MIN` y `PRICE_MAX_AGE_HOURS` (ya estaban en `.env.example`) y `PRICE_AUTO` (por defecto `true`; `false` apaga el refresco automático).
- Contrato de la API actualizado (CLAUDE.md §6).
### Corregido
- En el móvil la página ya no se desplaza a lo ancho (Movimientos con pendientes de revisar, tablas anchas): los textos para lectores de pantalla ensanchaban la página.
### Notas
- **Aplazado** a la revisión final (DISENO §17, pendiente 11): comparar el valor de la cartera con los brokers (menos del 1 % de diferencia) con las operaciones reales, y comprobar con Yahoo real la búsqueda, «Comprobar precio» y los índices de la comparativa.
- Sin importadores de Trade Republic ni Scalable ni de RUMBO: las operaciones van a mano o con la plantilla. No se ha copiado código de RUMBO.
- Solo Yahoo: Morningstar (fondos) y CoinGecko (cripto) se añadirán si hace falta.

## [0.5.0] – 2026-11-02 · Fase 2
### Añadido
- **Presupuestos mensuales** por categoría de gasto (migración `0003`): estado OK (< 90 %), Al límite (90–100 %) y Superado (> 100 %). `GET/PUT /api/budgets`.
- **Pagos recurrentes** (`backend/app/recurring/`): mismo concepto, importe dentro de ±10 % de la mediana, mensuales (≥ 3 pagos) o anuales (≥ 2), con el total al mes, el próximo pago y la marca «nuevo». Excluye transferencias internas y Bizum. `GET /api/recurring`.
- **Avisos** (`backend/app/alerts/`): presupuesto superado, gasto alto (más de 1,5× la media de los 3 meses anteriores y ≥ 30 € más), cambio frente al mes anterior, recurrente nuevo y total de recurrentes. `GET /api/alerts`.
- **Objetivo de patrimonio** (un objetivo por usuario) con porcentaje, lo que falta e hitos de 1.000 € a 1.000.000 €. `GET/PUT/DELETE /api/goals`.
- **Selector de mes** (`?mes=AAAA-MM`) en Patrimonio y Movimientos.
- Pantallas: tarjetas «Presupuestos del mes» (con ventana para editarlos), «Avisos» y «Pagos recurrentes» en Movimientos; «Objetivo de patrimonio» en Patrimonio.
- Indicadores y gráficos de Patrimonio y Movimientos (rehechos: la parte 1.5 no estaba en el repositorio).
- 96 tests nuevos (327 en total), con aislamiento entre usuarios en cada endpoint nuevo.
- `docs/fases/FASE_2.md`.
### Cambiado
- Una categoría que pasa a ingreso pierde su presupuesto.
- Contrato de la API actualizado (CLAUDE.md §6).
### Corregido
- Avisos y recurrentes ya no fallan (500) cuando ningún pago está cerca de la mediana.
### Notas
- **Aplazado** a la revisión final (DISENO §17, pendiente 11): comprobar con extractos reales que se parece a la maqueta, que los Bizum no salen como recurrentes y que los umbrales de los avisos son razonables.
- En móvil (390 px) la tabla de Movimientos desborda a lo ancho: se arregla en la Fase 4.

## [0.4.0] – 2026-10-30 · Fase 1d
### Añadido
- Backups cifrados (`backend/app/backup/`): `pg_dump -Fc` → **AES-256-GCM** con la clave derivada de `BACKUP_PASSWORD` por **scrypt** (sal y nonce aleatorios en la cabecera) → `caudal_AAAA-MM-DD_HHMM.dump.enc`, en el pendrive y en OneDrive, con rotación de las 30 últimas y registro en `backup_log`.
- Los 4 momentos: **tras importar** (si entra algo nuevo), **cada 60 min** si hubo cambios, **al cerrar** (script) y **al arrancar** si la última copia buena tiene más de 7 días.
- Restauración sobre una base vacía (`python -m app.backup restore`): descifra y comprueba el archivo antes de tocar nada, hace una copia de lo actual y restaura en una sola transacción.
- API: `GET /api/backups/status` y `POST /api/backups/run`.
- Indicador «Último backup · Pendrive ✓/✗ · OneDrive ✓/✗» en la cabecera (como la maqueta) y **Ajustes → Copias de seguridad** con «Hacer copia ahora».
- Restablecer contraseña desde la terminal (`python -m app.auth.reset`): cambia la contraseña, desbloquea y cierra las sesiones del usuario.
- Accesos directos: `scripts/mac/*.command` y `scripts/windows/*.bat` (que llaman a un `.ps1`): **Caudal**, **Cerrar Caudal**, **Restaurar backup** y **Restablecer contraseña**.
- 59 tests nuevos (231 en total), entre ellos uno que vuelca la BD, la restaura en otra base y compara todas las tablas fila a fila.
- `docs/fases/FASE_1d.md`.
### Cambiado
- Imagen de Docker con el cliente de **PostgreSQL 16** (`pg_dump` y `pg_restore`) del repositorio oficial PGDG. Dependencia nueva: `cryptography`.
- `docker-compose.yml`: la app monta el pendrive (`USB_BACKUP_DIR`, lo pone el script de arranque) y OneDrive (`ONEDRIVE_DIR`) en `/backups/usb` y `/backups/onedrive`.
- `.env.example`: `BACKUP_PASSWORD` activo; en el Mac de desarrollo, `ONEDRIVE_DIR` apunta a `CaudalBackupsDev`, nunca a la carpeta real.
- **Sin APScheduler:** los backups periódicos los lleva un hilo de la app (DISENO §10, CLAUDE.md §3).
- Scripts de Windows: cada `.bat` llama a un `.ps1` con la lógica (DISENO §11).
### Notas
- Un destino solo se usa si tiene el marcador `.caudal-backups` (lo crean los scripts): así un pendrive desconectado con la app abierta sale ✗ en lugar de escribir en una carpeta vacía.
- **Aplazado** a la revisión final (DISENO §17, pendiente 11): restauración completa desde el pendrive real, scripts de Windows en el PC y montaje del pendrive en Docker con WSL2 (pendiente 12).
- Antes de meter datos reales en el PC: elegir la contraseña de backup definitiva y apuntarla en papel, y separar la BD de desarrollo (pendiente 9).

## [0.3.0] – 2026-10-30 · Fase 1c
### Añadido
- Categorías y reglas iniciales por usuario (DISENO 9.4): se crean al dar de alta el usuario, y la migración `0002` las crea para los que ya existían.
- Motor de reglas (`backend/app/categories/`): **palabra entera**, en mayúsculas y sin acentos, por prioridad; reglas sin categoría para dejar los Bizum por revisar. Se aplica al importar (después de las transferencias internas) y al apuntar a mano.
- API de movimientos: `GET /api/transactions` con mes, buscador, categoría, estado, cuenta y paginación (`{items, total}`), `PATCH` (categoría puesta a mano, marcar o desmarcar transferencia interna, editar campos) y `DELETE`.
- API de categorías y reglas: `GET/POST/PATCH/DELETE /api/categories` y `/api/rules`, `POST /api/rules/apply` (con `include_auto` para corregir lo automático).
- API de los paneles: `GET /api/dashboard/net-worth` y `/api/dashboard/cashflow` (saldos calculados, ingresos y gastos sin internas, 12 meses, gasto por categoría).
- **Estructura de 3 pestañas** con la barra lateral de la maqueta y el contador de «por revisar».
- **Movimientos:** 4 indicadores, ingresos vs gastos a 12 meses, gasto por categoría, tabla con buscador y filtros, y ventana para añadir, editar y borrar.
- **Revisar** (`/movimientos/revisar`) con «¿Aplicar siempre?» (texto editable; no se ofrece con los Bizum) y «Es un traspaso entre mis cuentas».
- **Patrimonio:** indicadores, evolución a 12 meses, patrimonio por entidad y reparto «Efectivo / Fondo monetario» (solo liquidez).
- **Inversiones:** estado vacío «Todavía no hay inversiones».
- **Ajustes → Categorías y reglas** (adelantado de la Fase 4).
- 75 tests nuevos (172 en total), con aislamiento entre usuarios en cada endpoint nuevo y totales comparados con sumas hechas a mano.
- `docs/fases/FASE_1c.md`.
### Cambiado
- Reglas por **palabra entera** en lugar de «contiene»: `BAR` ya no encaja con «BARCELONA» (DISENO 9.4).
- `rules.category_id` pasa a ser opcional (regla sin categoría = dejar por revisar).
- Gráficos en CSS, como la maqueta, en lugar de Recharts (DISENO 2 y 10, CLAUDE.md §3).
- Rutas del frontend: `/patrimonio`, `/movimientos`, `/movimientos/importar`, `/movimientos/revisar`, `/inversiones`, `/ajustes`. `/panel` e `/importar` redirigen.
- El resumen de Importar dice cuántos se han categorizado automáticamente y lleva a Revisar.
- Contrato de la API actualizado (CLAUDE.md §6).
### Notas
- Una devolución cuenta como ingreso aunque tenga categoría de gasto (DISENO 9.1).
- El panel enseña el mes del último movimiento; el selector de mes llega en la Fase 2.
- Forma de trabajar: las comprobaciones con datos reales y de uso se aplazan a una revisión final (DISENO §17, pendiente 11; CLAUDE.md §4). El criterio de la 1c «un mes real queda categorizado salvo Bizum» queda aplazado.
- El buscador no ignora los acentos; la tabla de Movimientos en el móvil se desplaza en horizontal (se mejora en la Fase 4).

## [0.2.0] – 2026-10-21 · Fase 1b
### Añadido
- Importadores de **imagin** y **Wise** (`backend/app/importers/`): lectura por nombre de columna, comprobación de que el archivo es del banco de la cuenta, importes a `Decimal` sin pasar por `float`, fechas en texto o de Excel, concepto de Wise (Comercio → beneficiario o pagador → Descripción) y columnas del fondo de Wise ignoradas.
- Filas que no se pueden leer: van a `errors` con la fila, la columna, el dato y el motivo, sin abortar el resto.
- Comprobación del saldo fila a fila: aviso si no cuadra («puede faltar algún movimiento»). Al importar, el saldo de referencia de la cuenta pasa a ser el último del extracto (salvo que el extracto sea más antiguo).
- Huella anti-duplicados (DISENO 9.2) e inserción con `ON CONFLICT DO NOTHING`: importar dos veces el mismo archivo da 0 nuevos; dos compras iguales el mismo día no se toman por duplicadas.
- Transferencias internas (`backend/app/transfers/`): emparejado entre cuentas del mismo usuario (importes opuestos, ≤ 3 días y concepto o pista de transferencia); las conversiones de divisa de Wise son internas.
- API: `POST /api/imports` (multipart, máx. 5 MB) y `POST /api/transactions` (alta manual), con tests de aislamiento entre usuarios.
- Pantalla **Importar** (`/importar`, *Movimientos* en la barra lateral): elegir o crear la cuenta, arrastrar el Excel, resumen «leídos / nuevos / ya existían / por revisar / internos / con error», avisos de saldo y «Añadir a mano» para las filas con error.
- 66 tests nuevos (97 en total).
- `docs/fases/FASE_1b.md`.
### Cambiado
- `samples/imagin_ejemplo.xlsx` rehecho con datos inventados: todas las celdas en texto, dos decimales, saldos que cuadran, dos compras iguales el mismo día, la transferencia a Wise (pareja del `+50` del ejemplo de Wise) y una transferencia recibida (`TRANSFER IMMEDIATA`).
- Transferencias internas: el concepto o la pista del extracto pasan a ser **obligatorios** para emparejar (DISENO 9.3).
- Huella de Wise: `sha256(cuenta | ID)` en lugar del ID tal cual (DISENO 9.2).
- Lectura de extractos solo con openpyxl, sin pandas ni xlrd. Dependencias nuevas: `openpyxl` y `python-multipart`.
- El servicio `tests` monta `samples/` en solo lectura.
- `POST /api/transactions` se adelanta de la 1c a la 1b (CLAUDE.md §6).
- Frontend: la barra lateral y la cabecera pasan a `AppShell.tsx`, común a todas las pantallas con sesión.
### Notas
- El ejemplo antiguo de imagin no cubría los casos que decía la entrada 0.0.1 (no tenía dos compras iguales ni la pareja de la transferencia, y sus saldos no cuadraban). Por eso se rehízo.
- Pendiente (DISENO §17, pendiente 10): con el primer extracto real de Wise, comprobar si salen tipos de fila que los ejemplos no tienen.
- La categoría de los movimientos llega en la 1c: hasta entonces, todo lo importado queda «por revisar», salvo las transferencias internas.

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
