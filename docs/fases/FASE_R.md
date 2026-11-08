# Fase R · Puesta en marcha en el Mac y en el PC

> **Versión:** `0.6.1` (al cerrar) · **Fechas:** desde 2026-11-05 · **Estado:** ⏳ en curso. R.1, R.2 y R.3 terminadas; quedan R.4 a R.6 (datos reales)

El objetivo de la Fase R es **usar Caudal de verdad**, con los datos de Gerard, **tanto en el MacBook como en el PC de casa**, sin estar atado a un equipo. Cada equipo tiene su propia instancia real, y las dos se sincronizan a través de los **backups cifrados en Google Drive**: al cerrar en uno se guarda una versión nueva, y al abrir en el otro se restaura sola. Para programar, cada equipo tiene además una instancia de desarrollo aparte, con datos inventados.

Este documento explica qué se ha hecho, cómo y por qué. Se irá completando hasta el cierre de la fase.

---

## Índice

1. [Resumen y estado](#1-resumen-y-estado)
2. [Decisiones de la fase](#2-decisiones-de-la-fase)
3. [Cómo funciona la sincronización](#3-cómo-funciona-la-sincronización)
4. [Dos instancias en cada equipo](#4-dos-instancias-en-cada-equipo)
5. [El pendrive en Windows](#5-el-pendrive-en-windows)
6. [Problemas encontrados y cómo se resolvieron](#6-problemas-encontrados-y-cómo-se-resolvieron)
7. [Criterios de "hecho"](#7-criterios-de-hecho)
8. [Chuleta de comandos](#8-chuleta-de-comandos)

---

## 1. Resumen y estado

| Parte | Qué | Commit | Estado |
|---|---|---|---|
| R.1a | El destino en la nube pasa a llamarse `cloud` (`CLOUD_DIR`), con la etiqueta «Google Drive»; migración `0007` | `rename onedrive backup destination to cloud with google drive label (phase R, step R.1a)` | ✅ |
| R.1b | Google Drive en el Mac y en el PC; desarrollo y real separados en cada equipo | `fix volume name in mac script messages (phase R, step R.1b)` | ✅ |
| R.2a | Versión de cada base (`sync_state`, migración `0008`), candado y decisión al abrir | `add sync state, lock file and open decision (phase R, step R.2a)` | ✅ |
| R.2b | Comandos `python -m app.sync` open, close y status: esperar, restaurar, conflictos, `git pull` | `add sync open and close commands with conflict handling (phase R, step R.2b)` | ✅ |
| R.2c | Los scripts de abrir, cerrar y restaurar usan la sincronización; «Última copia» en la pantalla de inicio | `add sync to open, close and restore scripts and last copy on login (phase R, step R.2c)` | ✅ |
| R.3 | Mac → PC → Mac de verdad; pendrive en Windows copiado desde los scripts; restauraciones reales | `copy backups to the windows pendrive from the scripts instead of mounting it (phase R, step R.3)` | ✅ |
| R.4 | Movimientos con los extractos reales (imagin y Wise) | | ⬜ |
| R.5 | Inversiones con las operaciones reales (Trade Republic y Scalable) | | ⬜ |
| R.6 | Arreglos de lo que falle o moleste en el uso real | | ⬜ |

**Tests:** 693 en total (70 nuevos). ruff, ESLint, Prettier y el build, sin avisos. Los scripts de Windows se han probado en el PC; los del Mac, en el Mac.

---

## 2. Decisiones de la fase

- **Instancia real en el Mac y en el PC**, sincronizadas por los backups (2026-11-05). Otras opciones, como tener la base solo en un equipo y entrar desde el otro, obligaban a dejar un equipo encendido y en casa.
- **Google Drive con una cuenta de Google creada solo para Caudal**, con verificación en dos pasos, en modo **«Replicar archivos»**: todo está en el disco, así que Docker ve la carpeta aunque no haya conexión. Sustituye a OneDrive de la UdL, que se desactivará al acabar la carrera. Los backups van cifrados, así que Google no puede leerlos.
- **En el código, el destino se llama `cloud`** (`CLOUD_DIR`, `/backups/cloud`, `backup_log.destination = 'cloud'`) y la etiqueta visible es «Google Drive». Si algún día se cambia de proveedor, solo cambia la etiqueta.
- **Versiones con identificador único y su historia (`lineage`)**, no un simple contador: con un contador, dos versiones 6 hechas en equipos distintos no se distinguirían.
- **«Cambios sin copia» quiere decir «la sesión no se cerró con Cerrar Caudal»**, no un recuento de filas. Ante la duda, pregunta: si se añadiera una tabla y se olvidara contarla, se perderían datos sin avisar.
- **Abrir a la fuerza se queda el candado.** Lo normal es forzar cuando el otro equipo se apagó sin cerrar.
- **El correo de la cuenta de Google no está en el repositorio**, que es público: en la documentación sale como `GoogleDrive-<correo>`.
- **Carpeta del pendrive por instancia** (`USB_FOLDER`): `CaudalBackups` para la real y `CaudalBackupsDev` para desarrollo.

El detalle técnico está en `docs/DISENO.md` (sección 10, «Decisiones de implementación (Fase R)»).

---

## 3. Cómo funciona la sincronización

Cada base guarda en la tabla `sync_state` **qué versión tiene**: un número para enseñarlo, un identificador único y la lista de versiones de las que viene. Esa fila viaja dentro de los backups.

En la carpeta de Google Drive hay un **candado**, `caudal-sync.json`, que dice qué equipo tiene Caudal abierto o cuál lo cerró el último, con qué versión y en qué copia (nombre, tamaño y SHA-256).

**Al abrir** («Caudal», antes de arrancar la app), según el candado y la versión de este equipo:

| Situación | Qué hace |
|---|---|
| Todavía no hay candado | Abre con lo que hay |
| La versión es la misma | Abre |
| Hay una versión más nueva que contiene la de aquí, y aquí no quedó nada sin cerrar | **La restaura sola** |
| Base vacía (equipo nuevo) | Restaura sola la última |
| Los dos equipos tienen cambios | **Pregunta**: 1 = la del otro, 2 = la de aquí. Las dos se guardan en `conflictos/` |
| Caudal está abierto en el otro equipo | No abre, salvo que lo confirmes |
| La copia es de un código más nuevo | Pide hacer `git pull` |
| La copia todavía no ha bajado de Drive | Espera hasta 5 minutos y después deja abrir con lo de aquí, sin perder la otra |

**Al cerrar** («Cerrar Caudal»): versión nueva → backup → candado «cerrado en este equipo, versión N». Si la copia no llega a Google Drive, el candado no se toca y el otro equipo no ve esa versión.

**Restaurar a mano** («Restaurar backup»): lo restaurado recibe una versión nueva que contiene las del candado. Si no, al abrir se cambiaría sola por la última.

**«¿Quién entra?»** enseña «Última copia: Mac, hoy 22:30 · versión 3». Sirve para notar el riesgo aceptado: si se cambia de equipo antes de que Drive suba el candado, el otro equipo no sabe que hay algo nuevo.

---

## 4. Dos instancias en cada equipo

| | Real (para usar) | Desarrollo (para programar) |
|---|---|---|
| Carpeta en el Mac | `~/Caudal` | `~/Desktop/proyectos/caudal` |
| Carpeta en el PC | `C:\Users\gerar\Caudal` | `C:\Users\gerar\Proyectos\caudal` |
| `COMPOSE_PROJECT_NAME` | `caudal` | `caudal-dev` |
| Navegador | `localhost:8080` | `localhost:8081` |
| Google Drive (`CLOUD_DIR`) | `Mi unidad/CaudalBackups` | `Mi unidad/CaudalBackupsDev` |
| Pendrive (`USB_FOLDER`) | `CaudalBackups` | `CaudalBackupsDev` |
| `BACKUP_PASSWORD` | La definitiva, la misma en los dos equipos y en papel | Una de prueba, la misma en los dos equipos |
| `DEVICE_NAME` | `mac` / `pc` | `mac` / `pc` |

En la carpeta real **solo se hace `git pull`**: nunca se edita código ahí. Las dos instancias pueden estar abiertas a la vez, porque usan puertos distintos.

---

## 5. El pendrive en Windows

En el PC se comprobó que **Docker Desktop no ve las unidades extraíbles** de Windows: con el pendrive `Gerard` (exFAT) conectado, dentro del contenedor salía una carpeta vacía creada por el propio Docker. Por eso, en Windows el pendrive ya no se monta:

1. La app guarda las copias del «pendrive» en `backups\pendrive`, dentro de la carpeta de la instancia, en el disco `C:`, que Docker sí ve.
2. Al abrir y al cerrar, el script lleva al pendrive las copias nuevas y deja solo las `BACKUP_KEEP` más recientes. Cada copia se escribe primero como `.partial` y después se renombra.
3. Antes de restaurar, el script trae del pendrive las copias que falten, para que «Restaurar backup» las liste.
4. «Pendrive ✓» solo sale si el pendrive estaba conectado al abrir.

En el Mac se sigue montando `/Volumes/Gerard` directamente. Todavía no se ha probado allí con el pendrive.

---

## 6. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| El script del Mac se quedaba esperando y la app no arrancaba | El `.env` no acababa en salto de línea y `set_env` pegó una variable a la anterior (`PRICE_MAX_AGE_HOURS=6COMPOSE_PROJECT_NAME=…`) | `set_env` añade el salto de línea que falte antes de escribir |
| El Mac arrancaba con el código viejo | «Caudal» hacía `up -d` sin reconstruir la imagen | «Caudal» hace `docker compose build --quiet app` antes de abrir (con caché, segundos) |
| En el Mac salía `«�` en el aviso del pendrive | El bash 3.2 de macOS lee el primer byte de `»` como parte del nombre de la variable | `${etiqueta}»` |
| El `.env` de desarrollo del Mac tenía la configuración real | El `git clone` de `~/Caudal` no se hizo y el resto de comandos se ejecutaron en la carpeta de desarrollo | Se rehízo cada `.env` y se borraron las bases afectadas (solo datos de prueba). Los comandos que crean un `.env` comprueban ahora en qué carpeta están |
| Dos copias del mismo minuto se pisaban en `conflictos/` | Los backups se llaman por minuto | Las copias de conflicto llevan delante el equipo y la versión: `pc-v1_caudal_….dump.enc` |
| Un candado «sin versión» hacía intentar restaurar una copia que no existe | El primer equipo abrió y cerró sin que la copia llegara a Drive | Un candado sin versión no trae nada |
| En Git Bash, Docker recibía rutas rotas | Git Bash convierte las rutas tipo `/x` | `MSYS_NO_PATHCONV=1` delante de `docker run` / `docker exec` con rutas |
| Una comprobación decía que todos los archivos tenían CRLF | En Git Bash, el patrón `$'\r'` llega vacío a `grep` | Se usa `git ls-files --eol` y `file` |
| Seis archivos del PC tenían CRLF | Se sacaron del repositorio antes de que existiera `.gitattributes` | Se borraron y se volvieron a sacar con `git checkout` |
| «Pendrive ✗» en Windows con el pendrive conectado | Docker Desktop no ve las unidades extraíbles | Copiar desde los scripts (sección 5) |
| La instancia real y la de desarrollo escribían en la misma carpeta del pendrive | Solo había `CaudalBackups` | `USB_FOLDER` por instancia |

---

## 7. Criterios de "hecho"

| Criterio | Estado |
|---|---|
| Al pasar de un equipo a otro se ve lo último que se hizo | ✅ Probado con las dos instancias (desarrollo PC → Mac → PC, y real Mac → PC) |
| Restauración real desde Google Drive | ✅ Es lo que hace cada equipo al traer la versión del otro |
| Restauración real desde el pendrive | ✅ En el PC, borrando antes la copia intermedia |
| Con el pendrive desconectado, aviso y Google Drive sigue | ✅ |
| Gerard usa Caudal con sus datos reales en los dos equipos | ⬜ R.4 y R.5 |
| Tras importar un mes, todo lo que no es Bizum queda categorizado | ⬜ R.4 |
| El valor de la cartera difiere menos del 1 % del de los brokers | ⬜ R.5 |

---

## 8. Chuleta de comandos

| Para qué | Comando |
|---|---|
| Ver la versión de aquí y lo que dice Google Drive | `docker compose exec app python -m app.sync status` |
| Abrir / cerrar / restaurar | Accesos directos «Caudal», «Cerrar Caudal», «Restaurar backup» de la carpeta de la instancia |
| Saber en qué carpeta estás | `pwd` (y mira el puerto del navegador: 8080 real, 8081 desarrollo) |
| Ver el candado | `cat ".../Mi unidad/CaudalBackups/caudal-sync.json"` |
| Ver qué ve Docker en el pendrive (Windows, Git Bash) | `MSYS_NO_PATHCONV=1 docker exec caudal-app-1 ls -la /backups/usb` |
