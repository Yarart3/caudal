# Fase 1d · Backups + accesos directos

> **Versión:** `0.4.0` · **Fechas:** 2026-10-30 · **Estado:** ✅ terminada (con criterios aplazados a la revisión final)

El objetivo de la Fase 1d es **no perder nunca datos** y **abrir o cerrar Caudal con doble clic**. Caudal hace copias cifradas solas en el pendrive y en OneDrive, enseña su estado en la cabecera y tiene cuatro accesos directos: abrir, cerrar, restaurar y restablecer contraseña.

Este documento explica **qué se ha hecho**, **cómo** y **por qué**, con apuntes para aprender cada concepto. La fase se hizo en 6 partes, todas en el Mac, en un solo día. El pendrive real no estaba: se simuló con una imagen de disco y la prueba con el pendrive y en Windows quedó aplazada.

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Cómo trabajamos en esta fase](#2-cómo-trabajamos-en-esta-fase)
3. [Archivos nuevos y cambiados](#3-archivos-nuevos-y-cambiados)
4. [Parte 1.1: formato cifrado y pg_dump 16](#4-parte-11-formato-cifrado-y-pg_dump-16)
5. [Parte 1.2: servicio de backup, restaurar y terminal](#5-parte-12-servicio-de-backup-restaurar-y-terminal)
6. [Parte 1.3: backups automáticos y API](#6-parte-13-backups-automáticos-y-api)
7. [Parte 1.4: indicador y «Hacer copia ahora»](#7-parte-14-indicador-y-hacer-copia-ahora)
8. [Parte 1.5: scripts de Mac](#8-parte-15-scripts-de-mac)
9. [Parte 1.6: scripts de Windows](#9-parte-16-scripts-de-windows)
10. [Cierre: criterios de "hecho"](#10-cierre-criterios-de-hecho)
11. [Decisiones de la fase](#11-decisiones-de-la-fase)
12. [Problemas encontrados y cómo se resolvieron](#12-problemas-encontrados-y-cómo-se-resolvieron)
13. [Chuleta de comandos](#13-chuleta-de-comandos)
14. [Glosario](#14-glosario)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| 1.1 | Cifrado AES-256-GCM + scrypt, cliente de PostgreSQL 16 en la imagen | `feat: add encrypted backup format…` | ✅ |
| 1.2 | Servicio de backup (dos destinos, rotación, registro), restaurar y `python -m app.backup` | `feat: add backup service, restore and cli…` | ✅ |
| 1.3 | Los 4 momentos automáticos y `GET/POST /api/backups/...` | `feat: add automatic backups and backups api…` | ✅ |
| 1.4 | Indicador en la cabecera y Ajustes → Copias de seguridad | `feat: add backup indicator…` | ✅ |
| 1.5 | `scripts/mac/*.command` y `python -m app.auth.reset` | `feat: add mac launcher…` | ✅ |
| 1.6 | `scripts/windows/*.bat` + `.ps1` | `feat: add windows launcher…` | ✅ (sin probar en Windows) |
| Cierre | Criterios, CHANGELOG `0.4.0`, README, DISENO y CLAUDE.md | `docs: close phase 1d` | ✅ |

**Tests:** 231 en total (59 nuevos). ruff, ESLint, Prettier y el build, sin avisos. Las pantallas se probaron en Chromium (escritorio y móvil) y los scripts de Mac, con doble clic.

---

## 2. Cómo trabajamos en esta fase

Igual que en la 1c: partes pequeñas con archivos completos, comprobaciones y un commit por parte.

Novedades:
- **Sin pendrive:** se simuló con una **imagen de disco** de macOS (`hdiutil create … -volname CaudalPrueba`), que se monta en `/Volumes/` igual que un pendrive. Para probar con ella, `USB_LABEL=CaudalPrueba` en el `.env`.
- **Carpeta de OneDrive de desarrollo:** el `.env` del Mac apuntaba al principio a la carpeta **real** (`CaudalBackups`). Se cambió a `CaudalBackupsDev` antes de hacer ninguna copia.
- **Scripts de Windows escritos sin Windows:** se comprobó que PowerShell 7 los entiende y se probaron las partes que no dependen de Windows. La prueba de verdad, en el PC, queda aplazada.

---

## 3. Archivos nuevos y cambiados

```text
backend/
├── Dockerfile                    ← cliente de PostgreSQL 16 (PGDG) (1.1)
├── pyproject.toml · uv.lock      ← cryptography (1.1)
├── app/
│   ├── backup/
│   │   ├── crypto.py             ← AES-256-GCM + scrypt, formato del archivo (1.1)
│   │   ├── service.py            ← pg_dump, destinos, marcador, rotación, bloqueo, backup_log (1.2)
│   │   ├── restore.py            ← lista de copias, descifrar, comprobar, restaurar (1.2)
│   │   ├── __main__.py           ← python -m app.backup run | list | restore (1.2)
│   │   ├── auto.py               ← tras importar, periódico, al arrancar (1.3)
│   │   └── status.py             ← estado para el indicador (1.3)
│   ├── api/backups.py            ← GET /api/backups/status · POST /api/backups/run (1.3)
│   ├── api/imports.py            ← copia en segundo plano tras importar (1.3)
│   ├── auth/reset.py             ← python -m app.auth.reset (1.5)
│   ├── config.py                 ← BACKUP_* y carpetas de los destinos (1.2, 1.3)
│   └── main.py                   ← arranca y para el hilo de backups (1.3)
└── tests/
    ├── test_backup_crypto.py     ← 15 (1.1)
    ├── test_backup_service.py    ← 16, con una restauración completa comparada tabla a tabla (1.2)
    ├── test_backup_auto.py       ← 10 (1.3)
    ├── test_backups_api.py       ← 10 (1.3)
    └── test_auth_reset.py        ← 8 (1.5)
frontend/src/
├── api.ts · events.ts · format.ts · styles.css   ← tipos, aviso de cambios, fechas, estilos (1.4)
├── hooks/useBackupStatus.ts      ← estado que se actualiza solo (1.4)
├── components/BackupIndicator.tsx · BackupCard.tsx · backupText.ts (1.4)
├── AppShell.tsx                  ← indicador debajo del título (1.4)
└── pages/SettingsPage.tsx        ← tarjeta de copias de seguridad (1.4)
scripts/
├── mac/      _comun.sh + Caudal, Cerrar Caudal, Restaurar backup, Restablecer contraseña (.command) (1.5)
└── windows/  _comun.ps1 + caudal, cerrar, restaurar, restablecer (.ps1) + sus .bat (1.6)
docker-compose.yml · .env.example ← destinos montados, BACKUP_PASSWORD (1.2)
```

---

## 4. Parte 1.1: formato cifrado y pg_dump 16

### Qué se hizo
- `crypto.py`: `encrypt(datos, contraseña)` y `decrypt(archivo, contraseña)`. La clave sale de la contraseña con **scrypt** y una **sal** aleatoria; se cifra con **AES-256-GCM** y un **nonce** aleatorio.
- Formato: `CAUDALBK` + versión + parámetros de scrypt + sal + nonce (40 bytes) + datos cifrados + etiqueta de 16 bytes.
- En el `Dockerfile`, `postgresql-client-16` del repositorio oficial de PostgreSQL.

### Apuntes para aprender
- **¿Por qué no cifrar directamente con la contraseña?** AES necesita una clave de 32 bytes aleatoria. Una función de derivación (**KDF**) convierte la contraseña en una clave y, además, es **lenta a propósito** (scrypt usa unos 128 MB de memoria): probar millones de contraseñas cuesta muchísimo.
- **Sal:** número aleatorio que se mezcla con la contraseña. Con la misma contraseña, cada copia tiene una clave distinta y no sirven las tablas precalculadas. No es secreta: va en la cabecera.
- **GCM** cifra y **autentica**: si alguien cambia un byte, o la contraseña es incorrecta, el descifrado falla en lugar de devolver basura. Por eso el mensaje es «contraseña incorrecta **o** archivo dañado»: GCM no puede distinguirlos.
- **Nonce:** número que no se puede repetir nunca con la misma clave. Con sal y nonce aleatorios en cada copia, no hay riesgo.
- **Datos asociados (AAD):** la cabecera no va cifrada, pero sí protegida. Si se cambia N en la cabecera para pedir 128 GB de memoria, se rechaza antes de calcular.
- **¿Por qué `pg_dump` 16?** Un `pg_dump` más nuevo puede generar instrucciones que PostgreSQL 16 no entiende al restaurar.

---

## 5. Parte 1.2: servicio de backup, restaurar y terminal

### Qué se hizo
- `run_backup(disparador)`: `pg_dump` **una vez** → cifrar → escribir en cada destino → rotar → apuntar en `backup_log`. Si un destino falla, el otro sigue.
- **Marcador `.caudal-backups`:** un destino solo cuenta si lo tiene.
- **Escritura atómica** y **bloqueo** para que no haya dos copias a la vez.
- `restore_backup`: descifrar → `pg_restore --list` → borrar y crear la base → `pg_restore --single-transaction`.
- Terminal: `python -m app.backup run [--trigger close]`, `list` y `restore` (lista numerada, contraseña, `RESTAURAR`, copia previa).
- `docker-compose.yml`: la app monta `/backups/usb` y `/backups/onedrive`.

### Apuntes para aprender
- **¿Por qué el marcador?** Docker monta la carpeta del pendrive al arrancar. Si se desconecta con la app abierta, dentro del contenedor puede quedar una carpeta vacía que **parece** buena. Sin marcador, la app escribiría ahí y diría ✓.
- **Escritura atómica:** escribir en `.archivo.partial` y renombrarlo. Renombrar es instantáneo: nunca hay un backup a medias con su nombre definitivo (OneDrive sube lo que ve).
- **`pg_advisory_lock`:** un candado con nombre (un número) que da PostgreSQL. Lo comparten la app y la herramienta de terminal porque los dos hablan con la misma base.
- **`--single-transaction`:** la restauración entra entera o no entra. Si falla a medias, la base queda vacía (no a medias) y se restaura otra copia.
- **Restaurar en otro orden sería peligroso:** si se borrara la base antes de descifrar, una contraseña mal escrita dejaría Caudal vacío. Por eso primero se comprueba todo.
- **`PGPASSWORD`:** la contraseña de la BD va por variable de entorno, no en la línea de órdenes (que cualquiera ve con `ps`).

---

## 6. Parte 1.3: backups automáticos y API

### Qué se hizo
- `auto.py`: un **hilo** que arranca con la app. Al empezar, copia si la última buena tiene más de 7 días; luego, cada `BACKUP_INTERVAL_MIN`, copia si hubo cambios.
- Tras importar, la copia va en **segundo plano** (`BackgroundTasks`), después de responder, y solo si entró algo nuevo.
- `GET /api/backups/status` y `POST /api/backups/run`.
- Los tests ponen `BACKUP_AUTO=false`: si no, cada test que importa haría una copia.

### Apuntes para aprender
- **`lifespan`** de FastAPI: código que se ejecuta al arrancar (antes del `yield`) y al parar (después).
- **`pg_stat_user_tables`:** PostgreSQL cuenta las filas insertadas, cambiadas y borradas de cada tabla. Si el total no cambia, no hubo cambios. Se quitan `sessions` y `backup_log`: entrar o hacer una copia no cuenta.
- **Los contadores llegan tarde:** cada conexión los publica como mucho una vez por segundo. Los tests usan `pg_stat_force_next_flush()` para no depender de eso.
- **Un hilo en segundo plano nunca debe morir:** `run_quietly` captura cualquier excepción y la apunta en el log. La copia manual sí devuelve el error (409) para enseñarlo.

---

## 7. Parte 1.4: indicador y «Hacer copia ahora»

### Qué se hizo
- Debajo del título de cada pantalla: «Último backup: hoy 18:42 · Pendrive ✗ · OneDrive ✓», como en la maqueta. En rojo, lo que necesita atención; al pasar el ratón, el motivo.
- Ajustes → **Copias de seguridad**: estado de cada destino y «Hacer copia ahora».
- `useBackupStatus`: pregunta cada 60 s, 5 s después de importar o editar, y justo después de una copia manual.

### Apuntes para aprender
- **Eventos del navegador como bus:** `notifyBackupChanged()` lanza un evento en `window` y el indicador lo escucha. Así la tarjeta de Ajustes y la cabecera no necesitan conocerse.
- **`react-refresh/only-export-components`:** un archivo `.tsx` solo debe exportar componentes para que la recarga en caliente funcione. Por eso `lastBackupText` está en `backupText.ts`.
- **Fechas relativas:** «hoy» y «ayer» se calculan comparando el inicio de cada día en hora local, no restando 24 h.

---

## 8. Parte 1.5: scripts de Mac

### Qué se hizo
- `_comun.sh` con lo compartido: leer el `.env` (sin ejecutarlo), abrir Docker y esperar, buscar el pendrive con `mount`, comprobar OneDrive y esperar a `/api/health`.
- `Caudal`, `Cerrar Caudal`, `Restaurar backup` y `Restablecer contraseña` (`.command`).
- `python -m app.auth.reset`: contraseña nueva (dos veces), desbloqueo y cierre de sesiones.

### Apuntes para aprender
- **`.command`:** un script de shell que macOS abre en Terminal con doble clic. Necesita permiso de ejecución (`chmod +x`), que Git guarda.
- **El PATH del doble clic es mínimo:** por eso el script añade las rutas de `docker`.
- **bash 3.2:** es el que trae macOS (por licencia). No tiene arrays asociativos ni `${var,,}`.
- **Por qué no `source .env`:** el `.env` no es un script. Una contraseña con `$` o espacios se interpretaría mal o ejecutaría algo.
- **Si no existe la carpeta de OneDrive, Docker la crearía** (`create_host_path`). El script lo evita apuntando a una carpeta vacía de `backups/`.

---

## 9. Parte 1.6: scripts de Windows

### Qué se hizo
- `_comun.ps1` y un `.ps1` por acceso directo, con la misma lógica que en el Mac. El pendrive se busca con `Get-CimInstance Win32_LogicalDisk` por su nombre.
- Cada `.bat` es una línea: `powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0caudal.ps1"`.

### Apuntes para aprender
- **¿Por qué `.bat` + `.ps1`?** Con doble clic, Windows abre un `.bat` pero no un `.ps1`. Y la lógica (esperar, buscar volúmenes, peticiones HTTP) en `.bat` puro sería frágil.
- **`-ExecutionPolicy Bypass`:** Windows no ejecuta scripts `.ps1` por defecto; así se permite solo este, sin cambiar la configuración del sistema.
- **BOM en los `.ps1`:** Windows PowerShell 5.1 lee los archivos sin BOM como si no fueran UTF-8 y rompe los acentos.
- **`%~dp0`:** la carpeta del propio `.bat`, con la barra final.
- **Nombres sin acentos en los `.ps1`:** `cmd` lee el `.bat` con otra codificación y una «ñ» en la ruta podría fallar.

---

## 10. Cierre: criterios de "hecho"

| Criterio (CLAUDE.md, Fase 1d) | Cómo se comprobó | Resultado |
|---|---|---|
| Restauración completa sobre una base vacía **desde OneDrive**, y los datos coinciden | A mano en el Mac (borrar un movimiento → restaurar → vuelve) y con `test_restauracion_completa_sobre_una_base_vacia`, que compara todas las tablas fila a fila | ✅ |
| Restauración completa **desde el pendrive** | Con la imagen de disco en el Mac (copia ✓ en los dos destinos). Con el **pendrive real**, aplazado (DISENO §17, pendiente 11) | ⏸️ aplazado |
| Con el pendrive desconectado, el aviso aparece y OneDrive sigue | Expulsado a la fuerza con la app abierta → «Pendrive ✗ · Pendrive no conectado», OneDrive ✓. Tests `test_sin_marcador_el_pendrive_no_cuenta` y `test_pendrive_desconectado_despues_de_un_backup_bueno` | ✅ |
| Cifrar y descifrar ida y vuelta, rotación y contraseña incorrecta | `test_backup_crypto.py`, `test_rotacion_…`, `test_restaurar_con_contrasena_incorrecta_no_toca_la_base` | ✅ |
| Los 4 momentos | Tras importar, periódica y manual vistas en `backup_log`; al cerrar con `Cerrar Caudal.command`; al arrancar, `test_al_arrancar_…` | ✅ |
| Accesos directos | Los cuatro `.command`, con doble clic en el Mac. Los `.bat`, sin probar en Windows (pendientes 11 y 12) | ✅ Mac · ⏸️ Windows |
| Los tests pasan | **231 passed**; ruff, ESLint, Prettier y build sin avisos | ✅ |

---

## 11. Decisiones de la fase

Todas están ya pasadas a DISENO, CLAUDE.md, README o CHANGELOG.

| Decisión | Motivo | Dónde está |
|---|---|---|
| Cabecera propia con los parámetros de scrypt | Poder subirlos en el futuro sin dejar de abrir las copias antiguas | DISENO §10 |
| `pg_dump` 16 de PGDG | Que coincida con el servidor | DISENO §10 |
| Marcador `.caudal-backups` | Un pendrive desconectado no debe parecer un destino bueno | DISENO §10 |
| Sin APScheduler | Una sola tarea periódica: basta un hilo | DISENO §10, CLAUDE.md §3 |
| «Si hubo cambios» con `pg_stat_user_tables` | Detecta cualquier cambio, también los de SQL directo, sin tocar cada endpoint | DISENO §10 |
| Copia manual para cualquier usuario | El backup es de la BD entera y no enseña datos de nadie | DISENO §10, CLAUDE.md §6 |
| Restaurar con lista numerada, copia previa y `RESTAURAR` | Más fácil que un selector de archivos y sin borrar nada por error | DISENO §12 |
| `.bat` que llama a `.ps1` | La lógica en `.bat` puro sería frágil | DISENO §11, CLAUDE.md §3 |
| `CaudalBackupsDev` en el Mac | No mezclar copias de prueba con las reales (la rotación las borraría) | DISENO §10, README |
| Separar la BD de desarrollo del PC y la contraseña definitiva, antes del primer uso real | No se hizo en la 1d porque se trabajó en el Mac | DISENO §17, pendiente 9 |

---

## 12. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| `zsh: number expected` al pegar un comando con comentario | zsh no trata `#` como comentario en la terminal; `(cryptography)` se leyó como patrón | `setopt interactivecomments` en `~/.zshrc` |
| `hdiutil create … Operación no permitida` | Formato ExFAT en la imagen de disco | `-fs HFS+` |
| `error while creating mount source path '/host_mnt/Volumes/CaudalPrueba…'` | `USB_BACKUP_DIR` apuntaba a un pendrive que no estaba montado | Los scripts solo ponen la variable si encuentran el pendrive |
| `Falta BACKUP_PASSWORD en el .env` | La línea seguía comentada (`# BACKUP_PASSWORD=`) desde la 1a | Quitar el `#` y `docker compose up -d --force-recreate app` |
| `ONEDRIVE_DIR` apuntaba a la carpeta real | El `.env` del Mac se hizo antes de la 1d | `CaudalBackupsDev`; se quitó el marcador de la carpeta real |
| Se pegó la `POSTGRES_PASSWORD` en el chat | Al enseñar el `.env` entero | Cambiarla (`\password caudal` en psql + `.env`). La próxima vez, tapar los secretos |
| `couldn't unmount "disk5" - Recurso ocupado` | Docker tenía montada la imagen de disco | `hdiutil detach -force` (es lo que se quería simular) |
| La restauración «se cancelaba» | Se pulsaba Enter en la pregunta del número | En cada pregunta se escribe algo; solo la contraseña admite Enter |
| `ruff format --check`: `config.py` | Un comentario pegado con 8 espacios de sangría | `docker compose run --rm tests ruff format .` |
| `RWLayer of container … is unexpectedly nil` | Docker Desktop se cerró con los contenedores creados | `docker compose down` (sin `-v`) y `up -d`. Cerrar siempre con «Cerrar Caudal» antes que Docker |
| Un test fallaba a veces | PostgreSQL publica los contadores de cambios con retraso | `pg_stat_force_next_flush()` y esperar a que el total no se mueva |

---

## 13. Chuleta de comandos

```bash
# --- Copias desde la terminal ---
docker compose exec app python -m app.backup run                   # copia ahora
docker compose exec app python -m app.backup list                  # copias disponibles
docker compose stop app && docker compose run --rm app python -m app.backup restore && docker compose up -d
docker compose run --rm app python -m app.auth.reset               # cambiar una contraseña

# --- Registro de copias ---
docker compose exec db psql -U caudal -d caudal -P pager=off \
  -c "SELECT created_at, destination, result, message FROM backup_log ORDER BY id DESC LIMIT 10"

# --- Pendrive de prueba en el Mac (USB_LABEL=CaudalPrueba en el .env) ---
hdiutil attach ~/caudal-pendrive-prueba.dmg
hdiutil detach -force /Volumes/CaudalPrueba

# --- Contenedor dañado (RWLayer … nil): los datos NO se tocan ---
docker compose down          # nunca con -v
docker compose up -d

# --- Comprobaciones ---
docker compose run --rm tests                                      # pytest (231)
docker compose run --rm tests ruff check .
docker compose run --rm tests ruff format --check .
docker compose run --rm web                                        # lint + build del frontend
```

---

## 14. Glosario

| Término | Qué es |
|---|---|
| **AES-256-GCM** | Cifrado simétrico con clave de 256 bits que además detecta cualquier cambio en los datos |
| **scrypt** | Función que deriva una clave de una contraseña; lenta y con mucha memoria a propósito |
| **KDF** | *Key derivation function*: convierte una contraseña en una clave |
| **Sal** | Valor aleatorio que se mezcla con la contraseña para que cada clave sea distinta |
| **Nonce** | Número que se usa una sola vez con cada clave |
| **AAD** | Datos asociados: no se cifran, pero se protegen contra cambios |
| **`pg_dump -Fc`** | Volcado de la BD en formato *custom*: comprimido y restaurable con `pg_restore` |
| **Escritura atómica** | Escribir en un temporal y renombrar: el archivo final está entero o no está |
| **Advisory lock** | Candado de PostgreSQL con un número como nombre, para coordinar procesos |
| **`lifespan`** | Código de FastAPI que se ejecuta al arrancar y al parar la app |
| **Imagen de disco (`.dmg`)** | Archivo que macOS monta como si fuera un disco |
| **BOM** | Tres bytes al principio de un archivo UTF-8 que dicen «esto es UTF-8» |
| **`.command`** | Script de shell que macOS abre en Terminal con doble clic |
