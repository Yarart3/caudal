# Caudal

**Tus finanzas personales y familiares en un solo panel: patrimonio, movimientos e inversiones.**
Funciona en tu propio ordenador, con usuario y contraseña, sin publicar nada en internet y con copias de seguridad cifradas automáticas.

> 🚧 **Estado: Fase 0 terminada** (entorno preparado). El código empieza en la Fase 1a. Este README se irá actualizando al terminar cada fase.

![Pestaña Patrimonio (maqueta con datos inventados)](docs/capturas/01_patrimonio.png)

---

## Índice

- [Qué es](#qué-es)
- [Funciones](#funciones)
- [Lenguajes y tecnologías](#lenguajes-y-tecnologías)
- [Cómo funciona en casa](#cómo-funciona-en-casa)
- [Instalación](#instalación)
- [Trabajar desde varios ordenadores](#trabajar-desde-varios-ordenadores)
- [Uso diario](#uso-diario)
- [Copias de seguridad](#copias-de-seguridad)
- [Privacidad y seguridad](#privacidad-y-seguridad)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Roadmap](#roadmap)
- [Documentación](#documentación)
- [Créditos](#créditos)
- [Aviso](#aviso)

---

## Qué es

Caudal reúne en una sola app todo el dinero de una familia:

- **Cuentas del día a día** (imagin, Wise, CaixaBank, Sabadell…): se **importan los extractos** del banco y la app detecta sola qué es gasto y qué es ingreso, los **categoriza** y aprende de tus correcciones.
- **Inversiones** (Trade Republic, Scalable Capital…): ETFs, acciones, cripto y fondos. Las compras y ventas **se apuntan a mano** en un formulario rápido, y los **precios se actualizan solos**, con plusvalías, rentabilidad real (TIR) y comparativa con un indexado.
- **Patrimonio:** la suma de todo y cómo evoluciona mes a mes.

Cada usuario (por ejemplo, *Gerard* y *Padres*) entra con su contraseña y **solo ve lo suyo**.

## Funciones

| Acceso | Patrimonio | Movimientos | Inversiones |
|---|---|---|---|
| ![Acceso](docs/capturas/00_acceso.png) | ![Patrimonio](docs/capturas/01_patrimonio.png) | ![Movimientos](docs/capturas/02_movimientos.png) | ![Inversiones](docs/capturas/03_inversiones.png) |

**1. Patrimonio (portada)**
- Patrimonio neto, liquidez, inversiones y ahorro del mes.
- Evolución a 12 meses (inversiones + liquidez), patrimonio por entidad y reparto por tipo de activo.
- Objetivo de patrimonio con hitos.

**2. Movimientos**
- Importar extractos (Excel/CSV) **sin duplicados**, aunque se importe dos veces lo mismo.
- Categorización automática por reglas y pantalla para revisar lo dudoso (por ejemplo, los Bizum).
- Detección de **transferencias entre tus propias cuentas**, para que no cuenten como gasto.
- Ingresos vs gastos, gasto por categoría, presupuestos con avisos y pagos recurrentes.
- Alta, edición y borrado de movimientos a mano.

**3. Inversiones**
- Posiciones con precio actual, plusvalía y peso en la cartera.
- Cálculo **FIFO** (como Hacienda), **TIR**, rentabilidad por año y peor caída.
- "¿Y si todo fuera a un indexado?" con tus mismas aportaciones.
- Aportaciones mes a mes, comisiones anuales (TER), intereses y dividendos.

**Además:** usuarios con contraseña, copias de seguridad cifradas en el pendrive y en OneDrive, y funcionamiento en Windows y Mac.

## Lenguajes y tecnologías

| Parte | Lenguaje | Tecnologías |
|---|---|---|
| **Backend** (lógica, importadores, cálculos, API) | **Python 3.12** | FastAPI, SQLAlchemy 2, Alembic, Pydantic, pandas + openpyxl, argon2-cffi, httpx, APScheduler, cryptography, pytest |
| **Frontend** (la web que ves) | **TypeScript** | React, Vite, Recharts |
| **Base de datos** | **SQL** | PostgreSQL 16 |
| **Puesta en marcha** | YAML + scripts | Docker Compose; accesos directos `.bat` (Windows) y `.command` (Mac) |

**Por qué estos:**
- **Python** es el mejor lenguaje para leer Excel/CSV de bancos y hacer cálculos financieros. Con `Decimal`, el dinero se calcula sin errores de redondeo.
- **TypeScript + React** permite hacer el panel con gráficos interactivos como el de la maqueta. TypeScript avisa de errores antes de ejecutar.
- **PostgreSQL** es una base de datos robusta, con tipos exactos para el dinero (`NUMERIC`) y copias de seguridad fáciles.
- **Docker** hace que todo funcione igual en Windows y en Mac con un doble clic.

## Cómo funciona en casa

```text
 Doble clic en "Caudal" ──▶ arranca Docker ──▶ se abre el navegador en http://localhost:8080
                                   │
             ┌─────────────────────┴─────────────────────┐
             │ app (Python + web)  ◀──▶  base de datos   │   ← todo en tu PC
             └─────────────────────┬─────────────────────┘
                                   │ copias cifradas
                         pendrive  +  OneDrive
```

- **Solo se ejecuta cuando tú la abres.** Docker no arranca al encender el PC.
- Desde el móvil o el portátil de casa: `http://<IP-del-PC>:8080`, con el PC encendido y la app abierta.
- **Nunca** se expone a internet.

## Instalación

> ⏳ **Disponible a partir de la Fase 1d.** Pasos previstos:

1. Instalar **Docker Desktop** y desactivar *"Start Docker Desktop when you sign in"*.
2. Descargar o clonar este repositorio.
3. Copiar `.env.example` a `.env` y rellenar la ruta de OneDrive, el nombre del pendrive (`Gerard`) y la contraseña de backup.
4. Doble clic en **`scripts/windows/Caudal.bat`** (en Mac, `scripts/mac/Caudal.command`).
5. La primera vez, un asistente crea los usuarios y sus contraseñas.

## Trabajar desde varios ordenadores

El código se desarrolla en varios equipos (MacBook Air, portátil con Windows y PC de casa) y se sincroniza **solo con Git a través de GitHub**. Hay que tener claras tres cosas:

- **Git solo lleva el código y la documentación.** Los datos de la app (la base de datos, en el volumen de Docker) y el archivo `.env` **no viajan con Git**, y nunca deben subirse.
- **La instancia real, con los datos de verdad, solo funciona en el PC de casa** (ver `docs/DISENO.md`). En el resto de equipos solo se desarrolla y se prueba con los ejemplos inventados de `samples/`. Para mover los datos de un ordenador a otro se usa el script *Restaurar backup* (Fase 1d).
- **Regla de oro:** antes de empezar, `git pull`; al terminar, `git commit` + `git push`. Así nunca hay dos equipos con cambios distintos sin subir.

Los comandos son para **PowerShell** (Windows). En Mac, los comandos de Git son los mismos en la app Terminal, y la preparación del equipo está en la sección 16.1 de `docs/DISENO.md`.

### Caso 1: equipo nuevo (primera vez)

**1. Prepara Docker** (solo en Windows; en Mac, ver la sección 16.1 de `docs/DISENO.md`):
1. Comprueba la virtualización: Administrador de tareas → **Rendimiento** → **CPU** → *Virtualización: Habilitada*. Si está deshabilitada, actívala en la BIOS.
2. En PowerShell **como administrador** (cada comando puede tardar varios minutos):
   ```powershell
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   bcdedit /set hypervisorlaunchtype auto
   wsl --install --no-distribution
   wsl --update
   ```
3. Limita la memoria de WSL (si el PC tiene 8 GB de RAM, usa `memory=3GB`):
   ```powershell
   Set-Content -Path "$env:USERPROFILE\.wslconfig" -Value "[wsl2]","memory=4GB" -Encoding ascii
   ```
4. **Reinicia** el PC (Reiniciar, no Apagar).
5. Instala Docker Desktop:
   ```powershell
   winget install -e --id Docker.DockerDesktop
   ```
6. En Docker Desktop, **Settings → General**: marca *Use the WSL 2 based engine*, desmarca *Start Docker Desktop when you sign in to your computer* y pulsa **Apply & restart**.
7. Comprueba que funciona (debe salir "Hello from Docker!" y unos 4.000.000.000 bytes):
   ```powershell
   docker run hello-world
   docker info --format "{{.MemTotal}}"
   ```

**2. Instala y configura Git y VS Code**
```powershell
winget install -e --id Git.Git
winget install -e --id Microsoft.VisualStudioCode
```
Cierra PowerShell, ábrelo de nuevo y configura Git (pon tu nombre y tu email):
```powershell
git config --global user.name "TU_NOMBRE"
git config --global user.email "TU_EMAIL"
git config --global init.defaultBranch main
git config --global core.autocrlf true
git config --global pull.rebase true
```
`pull.rebase true` hace que `git pull` coloque tus commits locales encima de los de GitHub, en lugar de crear commits de "merge" innecesarios.

Instala las extensiones de VS Code:
```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension charliermarsh.ruff
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension ms-azuretools.vscode-docker
```

**3. Clona el repositorio** en tu carpeta de usuario (`C:\Users\<tu usuario>\Proyectos\caudal`; en Mac, `~/Proyectos/caudal`). Así está en la misma ruta en todos los equipos y **fuera de OneDrive**: nunca lo pongas en Documentos ni en el Escritorio, que suelen sincronizarse con OneDrive y darían conflictos con `node_modules` y los entornos de Python. Hazlo en un PowerShell **normal**, no de administrador:
```powershell
mkdir $env:USERPROFILE\Proyectos -Force
cd $env:USERPROFILE\Proyectos
git clone https://github.com/Yarart3/Caudal.git caudal
cd caudal
code .
```
La primera vez que hagas `git clone` o `git push`, se abre una ventana para iniciar sesión en GitHub.

**4. Crea el `.env` de este equipo** *(a partir de la Fase 1a)*:
```powershell
Copy-Item .env.example .env
```
Rellénalo con las rutas de **este** equipo. El `.env` lleva contraseñas: **no se sube a Git** (está en `.gitignore`) ni se envía por correo o chat.

### Caso 2: equipo que ya tenía el proyecto, pero está atrasado

**1. Mira si tienes cambios sin guardar en este equipo:**
```powershell
cd $env:USERPROFILE\Proyectos\caudal
git status
```

**2. Según lo que diga:**

- **"nothing to commit, working tree clean":** no hay cambios locales. Descarga lo nuevo:
  ```powershell
  git pull
  ```
- **Aparecen archivos modificados** y **quieres conservarlos:** guárdalos en un commit y después descarga lo nuevo:
  ```powershell
  git add -A
  git commit -m "describe aquí el cambio"
  git pull
  git push
  ```
- **Aparecen archivos modificados** y **no los quieres** (pruebas que no sirven). ⚠️ Esto **borra** esos cambios para siempre:
  ```powershell
  git restore .
  git clean -fd
  git pull
  ```
  `git clean -fd` borra los archivos nuevos que no están en Git. `.env`, `node_modules` y similares están en `.gitignore` y no se tocan.

**3. Si `git pull` dice `CONFLICT`:** el mismo archivo se cambió en dos equipos. **No toques nada más**: pega la salida de `git status` en Claude y lo resolvemos. Para volver a como estabas antes del `pull`:
```powershell
git rebase --abort
```

**4. Comprueba que estás al día:**
```powershell
git log --oneline -5
```
El último commit tiene que coincidir con el que aparece en GitHub.

**5. Actualiza la app** *(a partir de la Fase 1a)*. Si han cambiado dependencias, el `Dockerfile` o la base de datos, reconstruye los contenedores:
```powershell
docker compose up -d --build
```
Mira también si `.env.example` tiene variables nuevas y añádelas a tu `.env`:
```powershell
git diff ORIG_HEAD HEAD -- .env.example
```

### Antes de dejar un equipo

Sube siempre lo que hayas hecho, aunque esté a medias:
```powershell
git status
git add -A
git commit -m "describe aquí el cambio"
git push
```
Si `git push` dice `rejected`, es que otro equipo subió algo antes: haz `git pull` y vuelve a hacer `git push`.

**Comprueba** que `git status` dice **"Your branch is up to date with 'origin/main'"** y **"nothing to commit"**. Si es así, puedes cambiar de equipo sin perder nada.

### Qué es de cada equipo y qué se comparte

| Se comparte por Git | Es de cada equipo (no va a Git) |
|---|---|
| Código, documentación, `samples/` inventados, `.env.example` | `.env`, `.wslconfig`, Docker Desktop, la base de datos (volumen `pgdata`), `node_modules` y entornos de Python |

## Uso diario

1. Doble clic en **Caudal** → eliges tu usuario → contraseña.
2. **Movimientos → Importar extracto:** eliges la cuenta y arrastras el Excel/CSV del banco.
3. Revisas los movimientos marcados **"Revisar"**. Lo que corrijas, la app lo aprende.
4. **Inversiones:** apuntas cada compra o venta en **+ Añadir compra / venta** (puedes duplicar una anterior); los precios se actualizan solos. El historial antiguo se puede cargar de golpe con la plantilla de Excel.
5. Al terminar, doble clic en **Cerrar Caudal**: hace un backup y apaga todo.

## Copias de seguridad

- **Automáticas:** después de cada importación, cada hora si hubo cambios, al cerrar y al abrir si la última tiene más de una semana.
- **En dos sitios:** el pendrive (detectado por su nombre, no por la letra) y OneDrive.
- **Cifradas** (AES-256) con una contraseña propia. Se guardan las 30 últimas.
- **Restaurar:** script *Restaurar backup*. Sirve también para pasar a otro ordenador.

## Privacidad y seguridad

- Los datos **no salen de tu PC**, salvo las copias **cifradas**.
- Contraseñas con **Argon2**, sesión que caduca a los 30 minutos y bloqueo tras 5 intentos fallidos.
- Cada usuario **solo puede ver sus datos**. Lo comprueba el servidor, no solo la pantalla.
- **No se guardan** IBAN, números de tarjeta ni titulares, ni el archivo original del extracto.
- Para los precios solo se consulta el identificador del producto (ISIN o ticker), nunca cantidades.
- **Nunca** se suben datos reales al repositorio: los ejemplos de `samples/` son inventados.

## Estructura del proyecto

```text
caudal/
├── README.md                       ← este archivo
├── CLAUDE.md                       ← cómo trabaja Claude, fase a fase
├── CHANGELOG.md                    ← qué cambia en cada fase
├── INSTRUCCIONES_PROYECTO_CLAUDE.md← cómo montar el proyecto en Claude
├── docs/
│   ├── DISENO.md                   ← decisiones, modelo de datos y roadmap detallado
│   ├── fases/                      ← qué se hizo en cada fase, cómo y apuntes
│   └── capturas/
├── maqueta/caudal-maqueta.html     ← diseño de referencia (datos inventados)
├── backend/                        ← Python (FastAPI)          [Fase 1a]
├── frontend/                       ← TypeScript (React)        [Fase 1a]
├── scripts/windows · scripts/mac   ← accesos directos          [Fase 1d]
├── samples/                        ← extractos de ejemplo INVENTADOS
├── tests/
├── docker-compose.yml · .env.example · .gitignore              [Fase 1a]
```

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Preparar el entorno (Docker, Git, pendrive, OneDrive, ejemplos) | ✅ |
| 1a | Base del proyecto + inicio de sesión | ⬜ |
| 1b | Importadores de imagin y Wise | ⬜ |
| 1c | Categorización + pestañas Movimientos y Patrimonio | ⬜ |
| 1d | Backups + accesos directos | ⬜ |
| 2 | Presupuestos, avisos, recurrentes, objetivos | ⬜ |
| 3 | Patrimonio e inversiones (alta manual, precios, FIFO, TIR) | ⬜ |
| 4 | Los padres: CaixaBank, Sabadell, asistente genérico, gestión de usuarios | ⬜ |
| 5 | Previsión, IA local, informes, extras | ⬜ |
| 6 | Migración a Mac | ⬜ |
| 7 | (Opcional) Versión demo para el CV | ⬜ |

✅ hecha · ⏳ en curso · ⬜ pendiente. El detalle de cada fase está en [`docs/DISENO.md`](docs/DISENO.md#15-roadmap-por-fases) y [`CLAUDE.md`](CLAUDE.md).

## Documentación

- [`docs/DISENO.md`](docs/DISENO.md): **fuente de verdad**. Decisiones, cuentas y formatos de los bancos, modelo de datos, lógica, backups, seguridad y roadmap.
- [`CLAUDE.md`](CLAUDE.md): cómo debe trabajar Claude cada fase, de la 0 al final.
- [`docs/fases/`](docs/fases/): resumen de cada fase terminada, con los comandos y apuntes para aprender ([Fase 0](docs/fases/FASE_0.md)).
- [`INSTRUCCIONES_PROYECTO_CLAUDE.md`](INSTRUCCIONES_PROYECTO_CLAUDE.md): cómo montar el proyecto en Claude.
- [`maqueta/caudal-maqueta.html`](maqueta/caudal-maqueta.html): diseño de referencia (se abre con doble clic).

## Créditos

- La parte de inversiones se inspira en **[RUMBO](https://github.com/danidm98/rumbo)** de Dani Dominguez Quant (licencia MIT). Si se reutiliza código suyo, se mantendrá su aviso de copyright.
- Precios: Yahoo Finance, Morningstar y CoinGecko (servicios gratuitos y no oficiales).

## Aviso

Caudal es una herramienta **de uso personal e informativo**. **No es asesoramiento financiero** ni recomienda comprar o vender nada. Los precios vienen de servicios gratuitos y pueden tener errores o retrasos.

*Uso personal. Todos los derechos reservados por ahora; si se publica (Fase 7), se elegirá una licencia.*
