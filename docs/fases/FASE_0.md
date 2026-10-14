# Fase 0 · Preparar el entorno

> **Versión:** `0.0.1` · **Fecha:** 2026-10-01 · **Estado:** ✅ terminada (falta la contraseña de backup en papel)

En la Fase 0 no se programa nada. El objetivo es que los dos ordenadores (el portátil y el PC de casa) puedan **ejecutar** Caudal con Docker y **compartir** el código con Git. También se preparan los sitios donde irán los backups y los extractos de ejemplo con los que se programarán los importadores.

Este documento explica **qué se hizo**, **cómo** (con los comandos exactos) y **por qué**, con apuntes para aprender cada concepto.

---

## Índice

1. [Resumen](#1-resumen)
2. [Docker sobre WSL2](#2-docker-sobre-wsl2)
3. [Git, GitHub y VS Code](#3-git-github-y-vs-code)
4. [Trabajar desde varios ordenadores](#4-trabajar-desde-varios-ordenadores)
5. [Destinos de los backups](#5-destinos-de-los-backups)
6. [Ejemplos inventados de imagin y Wise](#6-ejemplos-inventados-de-imagin-y-wise)
7. [Trade Republic y Scalable](#7-trade-republic-y-scalable)
8. [Decisiones de la fase](#8-decisiones-de-la-fase)
9. [Problemas encontrados y cómo se resolvieron](#9-problemas-encontrados-y-cómo-se-resolvieron)
10. [Chuleta de comandos](#10-chuleta-de-comandos)
11. [Glosario](#11-glosario)

---

## 1. Resumen

| Tarea | Resultado |
|---|---|
| Virtualización, WSL2 y Docker Desktop | ✅ En los dos PCs. Docker no arranca solo y WSL está limitado a 4 GB de RAM |
| Git y VS Code con extensiones | ✅ En los dos PCs |
| Repositorio en GitHub | ✅ `Yarart3/Caudal`, **privado**, clonado en `C:\Users\gerar\Proyectos\caudal` |
| Pendrive de backups | ✅ Volumen `Gerard` (exFAT, 250 GB) con la carpeta `CaudalBackups\` |
| OneDrive de backups | ✅ `C:\Users\gerar\OneDrive - udl.cat\Proyectos\CaudalBackups` |
| Ejemplos de extractos | ✅ `samples/imagin_ejemplo.xlsx` y `samples/wise_ejemplo.xlsx`, con datos inventados |
| Trade Republic y Scalable | ✅ Decidido: se llevan **a mano**, sin importadores |
| Contraseña de backup en papel | ⏳ Pendiente, antes de la Fase 1d |

---

## 2. Docker sobre WSL2

### Qué se hizo

**Paso 1: comprobar la virtualización.** En el Administrador de tareas: **Rendimiento → CPU → Virtualización: Habilitada**.

**Paso 2: activar las funciones de Windows y el hipervisor.** En PowerShell **como administrador**. Los comandos de DISM pueden tardar varios minutos sin mostrar barra de progreso:
```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
bcdedit /set hypervisorlaunchtype auto
wsl --update
```
Después hay que **reiniciar** el PC (Reiniciar, no Apagar).

**Paso 3: limitar la RAM de WSL.**
```powershell
Set-Content -Path "$env:USERPROFILE\.wslconfig" -Value "[wsl2]","memory=4GB" -Encoding ascii
wsl --shutdown
```

**Paso 4: configurar Docker Desktop.** En **Settings → General**:
- marcada la opción *Use the WSL 2 based engine*;
- desmarcada la opción *Start Docker Desktop when you sign in*.

**Paso 5: comprobar que todo funciona.**
```powershell
wsl --status                              # Versión predeterminada: 2
docker version                            # Tienen que salir "Client" y "Server"
docker run hello-world                    # "Hello from Docker!"
docker info --format "{{.MemTotal}}"      # ~4.100.000.000 bytes
```

### Apuntes para aprender

- **Docker** ejecuta programas dentro de **contenedores**: entornos aislados que llevan todo lo que el programa necesita (Python, librerías, PostgreSQL…). Por eso Caudal funcionará igual en Windows y en Mac sin instalar Python ni PostgreSQL en el sistema.
- Una **imagen** es la "receta" congelada (por ejemplo, `postgres:16`). Un **contenedor** es esa imagen en marcha. `hello-world` es una imagen mínima que solo sirve para comprobar que todo funciona.
- Los contenedores de Docker son **Linux**. En Windows, Docker los ejecuta dentro de **WSL2** (*Windows Subsystem for Linux*), que es una máquina virtual ligera con un kernel Linux real.
- WSL2 necesita dos cosas:
  - la **virtualización del procesador** (Intel VT-x o AMD-V), que se activa en la BIOS;
  - el **hipervisor de Windows** (*Plataforma de máquina virtual*). `bcdedit /set hypervisorlaunchtype auto` hace que el hipervisor arranque con Windows. Algunos programas o juegos lo desactivan.
- **`docker version`** muestra dos partes:
  - **Client**: el comando `docker` que escribes;
  - **Server** (o *Engine*): el motor que ejecuta los contenedores.

  Si solo sale *Client*, el motor no está arrancado.
- **`.wslconfig`** es un archivo de texto en tu carpeta de usuario que configura WSL2. Por defecto, WSL puede usar **la mitad de la RAM**: en el PC de casa salían ~8 GB de 16. Con `memory=4GB` se queda en 4 GiB, que sobran para PostgreSQL y FastAPI. El `4GB` de WSL son **GiB** (1 GiB = 1024³ bytes), por eso `MemTotal` da 4.107.771.904 y no 4.000.000.000.
- Docker **no arranca solo** por diseño: Caudal solo consume recursos cuando tú lo abres.
- **"Quit Docker Desktop"** (clic derecho en la ballena junto al reloj) cierra Docker del todo. La X de la ventana solo la oculta.

---

## 3. Git, GitHub y VS Code

### Qué se hizo

**Configuración global de Git**, en los dos PCs:
```powershell
git config --global user.name "Yarart3"
git config --global user.email "gerardgurper@gmail.com"
git config --global init.defaultBranch main
git config --global core.autocrlf true
git config --global pull.rebase true
```

**Extensiones de VS Code:** Python, Pylance, Ruff, ESLint, Prettier y Docker.
```powershell
code --list-extensions                                   # ver cuáles tienes
code --install-extension dbaeumer.vscode-eslint          # instalar una
```

**Repositorio y clonado.** Se creó el repositorio **privado** `Yarart3/Caudal` en GitHub y se clonó, desde un PowerShell **normal** (no de administrador):
```powershell
mkdir $env:USERPROFILE\Proyectos -Force
cd $env:USERPROFILE\Proyectos
git clone https://github.com/Yarart3/Caudal.git caudal
```

**Primer arreglo:** el archivo `INSTRUCCIONES_PROYECTO_CLAUDE (1).md` se renombró, porque los enlaces del README apuntaban al nombre sin `(1)`:
```powershell
git mv "INSTRUCCIONES_PROYECTO_CLAUDE (1).md" INSTRUCCIONES_PROYECTO_CLAUDE.md
git commit -m "fix Instructions.md name"
git push
```

### Apuntes para aprender

- **Git** guarda el historial de cambios de una carpeta. **GitHub** es un servidor donde se guarda una copia de ese historial (el *remote*, llamado `origin`) para compartirla entre equipos.
- El ciclo básico:
  1. **modificas** archivos;
  2. `git add` los **prepara** (*staging*);
  3. `git commit` crea una **foto** con un mensaje;
  4. `git push` **sube** los commits a GitHub;
  5. `git pull` **baja** los commits que otros (u otro PC tuyo) han subido.
- **`git status`** es el comando más útil: dice qué ha cambiado y si vas por delante o por detrás de GitHub ("up to date with 'origin/main'").
- **`git mv`** renombra un archivo y Git lo registra como *renamed*, no como un borrado más un archivo nuevo. Las comillas hacen falta cuando el nombre tiene espacios o paréntesis.
- **`user.name` y `user.email`** aparecen en cada commit. En un repositorio **público** (Fase 7) conviene usar el email `...@users.noreply.github.com` que da GitHub, para no publicar tu email real.
- **`init.defaultBranch main`**: la rama principal se llama `main`, el estándar actual (antes era `master`).
- **Finales de línea (CRLF y LF):** Windows termina las líneas con dos caracteres (`\r\n`, *CRLF*); Linux y Mac, con uno (`\n`, *LF*). Con **`core.autocrlf true`**, Git guarda LF en el repositorio y te da CRLF en Windows. El aviso `LF will be replaced by CRLF` es normal e inofensivo. En la Fase 1a, el archivo `.gitattributes` lo fijará por tipo de archivo: los `.bat` en CRLF y los `.sh` y `.py` en LF. Un script `.sh` con CRLF **falla** en Linux y Mac.
- **`pull.rebase true`**: si los dos PCs tienen commits distintos, `git pull` coloca tus commits locales **encima** de los de GitHub, en lugar de crear un commit de "merge". El historial queda en línea recta.
- **Conventional Commits:** los mensajes de commit van en **inglés**, en **imperativo**, con un prefijo: `feat:` (función nueva), `fix:` (arreglo), `docs:` (documentación), `test:`, `chore:` (mantenimiento). Por ejemplo: `docs: keep USB volume label Gerard`.
- **No clones como administrador.** Si clonas desde un PowerShell de administrador (el que se abre en `C:\WINDOWS\System32`), los archivos quedan a nombre de "Administradores" y después Git da el error *"detected dubious ownership"* desde una ventana normal.
- **Nunca dentro de OneDrive.** Un proyecto de código no debe estar en una carpeta sincronizada (Documentos o Escritorio suelen estarlo), porque OneDrive intentaría subir miles de archivos de `node_modules` y entornos de Python, y crearía conflictos. `C:\Users\gerar\Proyectos` no se sincroniza.
- **Las extensiones de VS Code** se instalan una vez por equipo y sirven para todos los proyectos. No forman parte del repositorio.

---

## 4. Trabajar desde varios ordenadores

Está explicado en detalle en el README (sección **"Trabajar desde varios ordenadores"**). La regla de oro es:

```text
Al empezar:   git pull
Al terminar:  git add -A  →  git commit -m "..."  →  git push
```

### Apuntes para aprender

- **Git solo lleva el código y la documentación.** Lo que es de cada equipo no viaja:
  - el archivo `.env` (lleva contraseñas);
  - el `.wslconfig`;
  - Docker Desktop;
  - la base de datos de Caudal (vive en un volumen de Docker).
- **Los datos reales solo viven en el PC de casa.** El portátil sirve para desarrollar y probar con `samples/`. Para mover datos entre PCs se usará el script *Restaurar backup* (Fase 1d).
- Si editas un archivo **desde la web de GitHub**, en el PC tienes que hacer `git pull` antes de seguir trabajando. Si no, tu copia local queda atrasada.
- Si `git pull` dice **`CONFLICT`**, el mismo archivo se cambió en dos sitios. Para volver al estado anterior: `git rebase --abort`.

---

## 5. Destinos de los backups

### Qué se hizo

**Pendrive:** se comprobó su formato, se mantuvo su nombre de volumen y se creó la carpeta.
```powershell
Get-Volume | Where-Object DriveType -eq Removable | Format-Table DriveLetter, FileSystemLabel, FileSystem, Size
New-Item -ItemType Directory -Path "E:\CaudalBackups" -Force
```

**OneDrive:** se buscaron las carpetas sincronizadas y se creó la de backups dentro de la cuenta de la universidad.
```powershell
Get-ChildItem $env:USERPROFILE -Filter "OneDrive*"
New-Item -ItemType Directory -Path "$env:USERPROFILE\OneDrive - udl.cat\Proyectos\CaudalBackups" -Force
```

### Apuntes para aprender

- **Dos destinos de backup** porque cada uno falla de una forma distinta: el pendrive se puede romper o perder, y la nube puede fallar o cerrarse. Es una versión simplificada de la regla **3-2-1**: 3 copias, en 2 soportes distintos y 1 fuera de casa.
- **Sistema de archivos del pendrive:**

  | Formato | Windows | Mac | Límite por archivo |
  |---|---|---|---|
  | **exFAT** ✅ | Lee y escribe | Lee y escribe | Prácticamente ninguno |
  | NTFS | Lee y escribe | **Solo lee** | Prácticamente ninguno |
  | FAT32 | Lee y escribe | Lee y escribe | **4 GB** |

  El pendrive ya era exFAT, así que no hubo que formatearlo. **Formatear borra todo.**
- **Nombre de volumen y letra de unidad:** la letra (`E:`) la asigna Windows y **puede cambiar** cada vez que conectas el pendrive. El **nombre de volumen** (`Gerard`) va grabado en el propio pendrive. Por eso Caudal buscará el pendrive por su nombre (`USB_LABEL=Gerard`). Cambiar el nombre **no toca** los archivos; para hacerlo, desde PowerShell de administrador: `Set-Volume -DriveLetter E -NewFileSystemLabel NUEVO_NOMBRE`.
- **Riesgo asumido:** si otro pendrive se llamara también `Gerard`, la app podría guardar el backup en el equivocado. Basta con no repetir el nombre.
- **Icono verde en OneDrive** = archivo sincronizado. Una X roja indicaría un error de sincronización.
- **La cuenta de la UdL caducará** al acabar la carrera. Antes de que pase, hay que descargar los backups y cambiar `ONEDRIVE_DIR` en el `.env`. Está anotado como pendiente 7 en DISENO.

### La contraseña de backup (pendiente)

- Los backups se **cifrarán** con AES-256 usando la contraseña `BACKUP_PASSWORD` del `.env`. Sin ella, nadie puede leerlos, **tampoco tú**.
- Va en **papel** porque, si el PC se rompe, el `.env` se pierde con él, y la contraseña es lo único que permite restaurar los backups en otro equipo.
- **Formato recomendado:** una frase de 4 o 5 palabras al azar, con guiones y un número, usando solo letras sin acentos ni ñ, números y guiones. Los caracteres `$`, `#`, las comillas y los espacios pueden romperse en un `.env` de Docker: `$` se interpreta como una variable y `#` puede empezar un comentario.
- No debe estar en el repositorio, ni en OneDrive, ni en ningún chat.

---

## 6. Ejemplos inventados de imagin y Wise

### Qué se hizo

1. Se descargó un extracto real de cada banco y se guardó una **copia** con el nombre del ejemplo, siempre **fuera del repositorio** (en Descargas).
2. Se dejaron solo unas pocas filas y se **inventaron todos los datos**, sin tocar el formato.
3. Claude revisó y corrigió los archivos:
   - en imagin, fechas mezcladas entre texto y fecha, saldos que no cuadraban y casos de prueba que faltaban;
   - en Wise, IDs repetidos, datos reales que quedaban, la pareja de la transferencia y los metadatos con el nombre.
4. Se borraron los extractos reales.

**Casos de prueba incluidos:**
- **imagin:** dos compras **idénticas el mismo día** (para probar que no se toman por duplicado), Bizums y una **transferencia a Wise** de −50,00 € el 27/09.
- **Wise:** la **pareja** de esa transferencia (+50,00 € el 27/09, `DEPOSIT`) y pagos con tarjeta con venta del fondo monetario.

### Formatos confirmados

| | imagin | Wise |
|---|---|---|
| Archivo | `.xlsx` (también da PDF; no hay CSV) | `.xlsx`, hoja `All transactions`, 32 columnas |
| Fecha | **Texto** `dd/mm/aaaa` | Fecha de Excel, más la columna `Fecha y hora` |
| Importe | **Texto** `-23,00EUR` (siempre dos decimales) | Número (`-7`, `-12.4`) |
| Conceptos | En **catalán**, a veces en minúsculas o cortados: `BIZUM ENVIAT`, `BIZUM REBUT`, `enviament de dine` | `Comercio`, o si está vacío `Nombre del pagador` / `Nombre del beneficiario`, o si también, `Descripción` |
| ID único | No tiene: la huella usa el saldo | `Documento de identidad` |
| Transferencia desde imagin | `enviament de dine` (no dice el destino) | `CREDIT` + `DEPOSIT`, con `imaginBank` en `Referencia del pago` |

### Apuntes para aprender

- **Por qué ejemplos inventados:** los importadores se programan y se prueban contra el **formato real**, pero en el repositorio nunca puede haber **datos reales**. La solución es partir de un extracto real y cambiar todos los valores.
- **Texto y fecha en Excel:** la misma apariencia, `29/09/2026`, puede ser un **texto** o una **fecha** (que internamente es un número: los días desde 1899). `=ESTEXTO(B2)` lo distingue. Para el programa son cosas distintas: un texto hay que interpretarlo, una fecha ya viene interpretada.
- **El apóstrofo (`'`):** si escribes `-14,50EUR`, Excel cree que es una fórmula porque empieza por `-` o `=`. Con `'-14,50EUR`, Excel lo guarda como texto; el apóstrofo no se guarda en el archivo. Sin apóstrofo, `29/09/2026` se convierte en fecha.
- **Un CSV no se abre con Excel** si lo vas a guardar: Excel cambia las fechas, las comas decimales, el separador y a veces la codificación. Se edita con **VS Code**, que lo deja tal cual.
- **Un `.xlsx` es un ZIP** con archivos XML dentro. Los textos están en `xl/sharedStrings.xml` y los metadatos (autor, último en modificar) en `docProps/core.xml`. Por eso, al anonimizar, no basta con lo que se ve en las celdas: **tu nombre quedaba en los metadatos**, y en Wise los textos originales seguían escondidos en `sharedStrings.xml` aunque ya no se mostraran.
- **Los saldos tienen que cuadrar:** saldo anterior + importe = saldo nuevo. El programa lo usará para avisar si **falta algún movimiento**.
- **La huella anti-duplicados (*fingerprint*):** para no importar dos veces lo mismo, cada movimiento tiene un identificador.
  - **Wise** ya da uno (`Documento de identidad`).
  - **imagin** no, así que se calcula: `sha256(cuenta | fecha | importe | concepto | saldo)`. Incluir el saldo hace que dos compras idénticas el mismo día tengan huellas distintas, porque el saldo después de cada una es diferente.
- **Las transferencias internas:** pasar 50 € de imagin a Wise no es ni un gasto ni un ingreso. El programa empareja un −50 en una cuenta con un +50 en otra, con como mucho 3 días de diferencia, y los marca como *internos*.
- **Columnas por nombre, no por posición:** los extractos se suben **tal cual**. El importador busca cada columna por su cabecera e ignora el resto, así que no hay que borrar las columnas "raras" de Wise. Antes de leer, comprueba que el archivo es del banco de la cuenta elegida.

---

## 7. Trade Republic y Scalable

### Qué se decidió

Sus extractos **no incluyen las inversiones**, y hay pocas operaciones (compras puntuales, sin planes periódicos). Por eso se llevan **a mano**:
- **Efectivo remunerado de Trade Republic:** cada ingreso, retirada e interés mensual se apunta en **Movimientos**.
- **Cartera** (ETFs y cripto en Trade Republic; ETFs en Scalable): formulario **"+ Añadir compra / venta"**, con un botón para **duplicar una operación anterior**.
- **Historial antiguo:** con la plantilla de Excel, o con una **posición inicial** por producto (total de participaciones y total invertido).

### Apuntes para aprender

- Con **cuántas tienes** (participaciones) y el **precio actual** (que la app descarga sola), Caudal sabe **cuánto vale** tu cartera. Con **cuánto pagaste**, sabe además **cuánto ganas**: plusvalía = valor actual − coste.
- **FIFO** (*first in, first out*): al vender, se consideran vendidas primero las participaciones más antiguas. Es el criterio que exige Hacienda.
- **TIR (XIRR):** la rentabilidad anual teniendo en cuenta **cuándo** metiste cada euro. Con una posición inicial en lugar de cada compra, sale aproximada.
- Se hará en la **Fase 3**, manteniendo el orden del roadmap.

---

## 8. Decisiones de la fase

| Decisión | Motivo | Dónde está |
|---|---|---|
| El pendrive se llama `Gerard`, no `CAUDAL_BK` | Evitar renombrarlo; se asume no tener otro pendrive con el mismo nombre | DISENO §10 y §12, CLAUDE.md |
| Backups en `OneDrive - udl.cat\Proyectos` | Es la cuenta prevista; antes de graduarse se moverán | DISENO §10, pendiente 7 |
| Commits en inglés (Conventional Commits) | Estándar habitual; el resto sigue en castellano | CLAUDE.md |
| Proyecto en `C:\Users\<usuario>\Proyectos\caudal` | Misma ruta en todos los equipos y fuera de OneDrive | README |
| `pull.rebase true` | Historial lineal al trabajar en dos PCs | README |
| Los extractos se suben tal cual; columnas por nombre | No tener que editar nunca los archivos del banco | DISENO §6.0 |
| Filas ilegibles: se listan con su error y se añaden a mano | No perder movimientos en silencio | DISENO Fase 1b, CLAUDE.md |
| Reglas de Bizum en catalán (`BIZUM ENVIAT` / `BIZUM REBUT`) | Es lo que pone el extracto real | DISENO §9.4 |
| Trade Republic y Scalable a mano | Sus extractos no traen las inversiones y hay pocas operaciones | DISENO §6.3 y §7.4 |
| Se mantiene el orden de las fases | Fase 3 (inversiones) después de la 2 | DISENO §15 |

---

## 9. Problemas encontrados y cómo se resolvieron

| Problema | Causa | Solución |
|---|---|---|
| El bloque `@" ... "@` en PowerShell no hacía nada (prompt `>>`) | El cierre `"@` de un *here-string* tiene que ir **en la columna 0**; estaba sangrado | `Ctrl+C` y usar `Set-Content -Value "linea1","linea2"` |
| Docker: *"Unexpected WSL error… WSL2 no se puede iniciar"* | Faltaban funciones de Windows o el hipervisor estaba desactivado | Los dos `dism.exe /enable-feature`, `bcdedit /set hypervisorlaunchtype auto`, `wsl --update` y reiniciar |
| DISM "se quedaba cargando" sin porcentaje | Es normal: tarda varios minutos | Esperar. Se puede comprobar que `TiWorker.exe` o `DismHost.exe` trabajan en el Administrador de tareas |
| `MemTotal` daba ~8 GB en el PC de casa | No había `.wslconfig`: WSL usaba la mitad de la RAM | Crear `.wslconfig`, cerrar Docker, `wsl --shutdown` y volver a abrirlo |
| Aviso de fórmula de Excel al escribir `-23,00EUR` | Excel interpreta como fórmula lo que empieza por `-` | Escribir `'-23,00EUR`, o editar con F2 solo los números |
| Algunas fechas de imagin pasaron a ser fechas de Excel | Se escribieron sin apóstrofo | Todas las fechas reescritas como texto |
| IDs `CARD-xxxxxxxxxx` repetidos en Wise | Al anonimizar, todos quedaron iguales | IDs únicos inventados (`CARD-1000000001`…) |
| El nombre real en los metadatos del `.xlsx` | Excel guarda "último en modificar" | Borrado del archivo `docProps/core.xml` |

---

## 10. Chuleta de comandos

```powershell
# --- Docker / WSL ---
wsl --status                          # versión de WSL
wsl --shutdown                        # apagar WSL (para aplicar .wslconfig)
docker version                        # cliente + motor
docker run hello-world                # prueba rápida
docker info --format "{{.MemTotal}}"  # RAM disponible para Docker

# --- Git: día a día ---
git status                            # qué ha cambiado y si estás al día
git pull                              # bajar cambios
git add -A                            # preparar todos los cambios
git commit -m "docs: ..."             # guardar una foto
git push                              # subir
git log --oneline -5                  # últimos 5 commits
git diff --stat                       # resumen de cambios sin guardar
git mv "viejo nombre.md" nuevo.md     # renombrar
git rebase --abort                    # deshacer un pull con conflictos

# --- Git: configuración ---
git config --global --list            # ver la configuración

# --- VS Code ---
code .                                # abrir la carpeta actual
code --list-extensions                # extensiones instaladas

# --- Archivos y discos (PowerShell) ---
Test-Path "ruta"                      # ¿existe? True / False
New-Item -ItemType Directory -Path "ruta" -Force
Copy-Item "origen" "destino" -Force
Get-Content "archivo"                 # ver un archivo de texto
Get-Volume                            # discos y pendrives
Get-ChildItem $env:USERPROFILE -Filter "OneDrive*"
```

---

## 11. Glosario

| Término | Qué es |
|---|---|
| **Contenedor** | Programa aislado con todo lo que necesita, ejecutado por Docker |
| **Imagen** | La plantilla a partir de la que se crea un contenedor |
| **WSL2** | Subsistema de Windows que ejecuta un kernel Linux real en una máquina virtual ligera |
| **Hipervisor** | Software que permite ejecutar máquinas virtuales |
| **Repositorio** | Carpeta con historial de Git |
| **Commit** | Foto de los cambios con un mensaje |
| **Remote / origin** | La copia del repositorio en GitHub |
| **Clone / pull / push** | Copiar el repositorio la primera vez / bajar cambios / subir cambios |
| **Rebase** | Recolocar tus commits encima de los más recientes |
| **CRLF / LF** | Finales de línea de Windows / de Linux y Mac |
| **exFAT** | Formato de disco compatible con Windows y Mac, sin límite práctico de tamaño |
| **Nombre de volumen** | El nombre grabado en un disco o pendrive (no cambia, a diferencia de la letra) |
| **`.env`** | Archivo con la configuración y los secretos de cada equipo. Nunca va a Git |
| **Huella (*fingerprint*)** | Identificador de un movimiento para detectar duplicados |
| **Transferencia interna** | Dinero que se mueve entre tus propias cuentas: no es ni gasto ni ingreso |
| **FIFO** | Al vender, se venden primero las participaciones más antiguas |
| **TIR / XIRR** | Rentabilidad anual que tiene en cuenta las fechas de cada aportación |
| **Conventional Commits** | Convención de mensajes de commit: `tipo: descripción` |

---

**Siguiente fase:** 1a, base del proyecto e inicio de sesión. Para empezarla, en una conversación nueva del proyecto:
```text
Empezamos la Fase 1a de Caudal (base del proyecto + inicio de sesión). Sigue CLAUDE.md.
```
