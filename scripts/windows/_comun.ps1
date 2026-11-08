# Funciones comunes de los scripts de Windows de Caudal. No se ejecuta solo: lo cargan los
# .ps1 con ". (Join-Path $PSScriptRoot '_comun.ps1')". Funciona con Windows PowerShell 5.1.
# Va en UTF-8 CON BOM: sin el BOM, PowerShell 5.1 lee mal los acentos.

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'  # sin la barra de progreso de Invoke-WebRequest
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Por si docker no está en el PATH de esta ventana
$env:Path += ";$env:ProgramFiles\Docker\Docker\resources\bin"
$DockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'

# Raíz del proyecto (scripts\windows\ -> ..\..)
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $Root

function Titulo([string]$texto) { Write-Host ''; Write-Host $texto -ForegroundColor White; Write-Host '' }
function Ok([string]$texto) { Write-Host "  [OK] $texto" -ForegroundColor Green }
function Aviso([string]$texto) { Write-Host "  [!]  $texto" -ForegroundColor Yellow }
function Fallo([string]$texto) { Write-Host "  [X]  $texto" -ForegroundColor Red }

# Deja la ventana abierta para que se pueda leer el mensaje y sale con el código indicado
function Pausa-Y-Salir([int]$codigo = 1) {
    Write-Host ''
    Read-Host 'Pulsa Enter para cerrar esta ventana' | Out-Null
    exit $codigo
}

function Comprobar-Env {
    if (-not (Test-Path -LiteralPath (Join-Path $Root '.env'))) {
        Fallo "No existe el archivo .env en $Root"
        Write-Host '       Cópialo de .env.example y rellénalo (README, «Instalación»).'
        Pausa-Y-Salir 1
    }
}

# Valor de una variable del .env, sin comillas. No se ejecuta el .env: solo se lee.
function Env-Valor([string]$nombre, [string]$defecto = '') {
    $valor = $null
    $patron = '^' + [regex]::Escape($nombre) + '=(.*)$'
    foreach ($linea in Get-Content -LiteralPath (Join-Path $Root '.env') -Encoding UTF8) {
        if ($linea -match $patron) { $valor = $Matches[1] }
    }
    if ($null -eq $valor) { return $defecto }
    $valor = $valor.Trim()
    if ($valor.Length -ge 2 -and (($valor.StartsWith('"') -and $valor.EndsWith('"')) -or
            ($valor.StartsWith("'") -and $valor.EndsWith("'")))) {
        $valor = $valor.Substring(1, $valor.Length - 2)
    }
    if ($valor -eq '') { return $defecto }
    return $valor
}

function Url-App { return 'http://localhost:' + (Env-Valor 'APP_PORT' '8080') }

function Docker-Listo {
    try {
        & docker info *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

# Abre Docker Desktop si hace falta y espera a que esté listo (hasta 3 minutos)
function Esperar-Docker {
    if (Docker-Listo) { Ok 'Docker está en marcha'; return }
    if (-not (Test-Path -LiteralPath $DockerDesktop)) {
        Fallo "No se encuentra Docker Desktop ($DockerDesktop)"
        Pausa-Y-Salir 1
    }
    Write-Host '  Abriendo Docker Desktop (puede tardar un poco)...'
    Start-Process -FilePath $DockerDesktop
    for ($i = 0; $i -lt 90; $i++) {
        if (Docker-Listo) { Ok 'Docker está listo'; return }
        Start-Sleep -Seconds 2
    }
    Fallo 'Docker Desktop no ha arrancado en 3 minutos. Ábrelo a mano y vuelve a intentarlo.'
    Pausa-Y-Salir 1
}

# Pendrive (pendiente 12, Fase R): Docker Desktop (WSL2) NO ve las unidades extraíbles de Windows
# (monta una carpeta vacía en su lugar), así que el pendrive no se monta. La app guarda sus copias
# del «pendrive» en backups\pendrive (en el disco C:, que Docker sí ve) y este script las lleva al
# pendrive al abrir y al cerrar (Llevar-Al-Pendrive) y las trae antes de restaurar
# (Traer-Del-Pendrive). El pendrive se busca por su nombre de volumen (USB_LABEL), no por la letra,
# y dentro se usa la carpeta USB_FOLDER (CaudalBackups en la instancia real, CaudalBackupsDev en
# desarrollo). Sin pendrive, se quita el marcador de backups\pendrive y la app avisa.
$Intermedia = Join-Path $Root 'backups\pendrive'
$PatronCopia = '^caudal_\d{4}-\d{2}-\d{2}_\d{4}\.dump\.enc$'
$script:DirPendrive = $null

function Preparar-Pendrive {
    $etiqueta = Env-Valor 'USB_LABEL' 'Gerard'
    $carpeta = Env-Valor 'USB_FOLDER' 'CaudalBackups'
    $marcador = Join-Path $Intermedia '.caudal-backups'
    New-Item -ItemType Directory -Force -Path $Intermedia | Out-Null
    $env:USB_BACKUP_DIR = $Intermedia
    $script:DirPendrive = $null
    $discos = @(Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction SilentlyContinue |
            Where-Object { $_.VolumeName -eq $etiqueta })
    if ($discos.Count -ne 1) {
        Remove-Item -LiteralPath $marcador -Force -ErrorAction SilentlyContinue
        if ($discos.Count -eq 0) {
            Aviso "Pendrive «$etiqueta» no conectado: las copias irán solo a Google Drive"
        } else {
            $letras = ($discos | ForEach-Object { $_.DeviceID }) -join ', '
            Fallo "Hay varias unidades llamadas «$etiqueta» ($letras): no se usa ninguna."
        }
        return
    }
    $dir = $discos[0].DeviceID + '\' + $carpeta
    try {
        New-Item -ItemType Directory -Force -Path $dir -ErrorAction Stop | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $dir '.caudal-backups') -ErrorAction Stop | Out-Null
    } catch {
        Remove-Item -LiteralPath $marcador -Force -ErrorAction SilentlyContinue
        Aviso "El pendrive «$etiqueta» está conectado, pero no se puede escribir en él"
        return
    }
    New-Item -ItemType File -Force -Path $marcador | Out-Null
    $script:DirPendrive = $dir
    Ok "Pendrive «$etiqueta» conectado ($dir)"
}

# Copia de $origen a $destino las copias de Caudal que falten (o que tengan otro tamaño); con
# $maximo, solo las $maximo más recientes. Cada una se copia primero como .partial y después se
# renombra: nunca queda una a medias con el nombre bueno.
function Copiar-Copias([string]$origen, [string]$destino, [int]$maximo = 0) {
    $copiadas = 0
    $archivos = @(Get-ChildItem -LiteralPath $origen -File -ErrorAction Stop |
            Where-Object { $_.Name -match $PatronCopia } |
            Sort-Object Name -Descending)
    if ($maximo -gt 0) { $archivos = @($archivos | Select-Object -First $maximo) }
    foreach ($archivo in $archivos) {
        $final = Join-Path $destino $archivo.Name
        $ya = Get-Item -LiteralPath $final -ErrorAction SilentlyContinue
        if ($ya -and $ya.Length -eq $archivo.Length) { continue }
        $temporal = $final + '.partial'
        Copy-Item -LiteralPath $archivo.FullName -Destination $temporal -Force -ErrorAction Stop
        Move-Item -LiteralPath $temporal -Destination $final -Force -ErrorAction Stop
        $copiadas++
    }
    return $copiadas
}

# Lleva al pendrive las copias nuevas y deja solo las BACKUP_KEEP más recientes (como la app)
function Llevar-Al-Pendrive {
    if (-not $script:DirPendrive) { return }
    try {
        $guardar = [int](Env-Valor 'BACKUP_KEEP' '30')
        $copiadas = Copiar-Copias $Intermedia $script:DirPendrive $guardar
        Get-ChildItem -LiteralPath $script:DirPendrive -File |
            Where-Object { $_.Name -match $PatronCopia } |
            Sort-Object Name -Descending |
            Select-Object -Skip $guardar |
            Remove-Item -Force -ErrorAction Stop
        if ($copiadas -gt 0) { Ok "Pendrive: $copiadas copia(s) nueva(s) guardada(s)" } else { Ok 'Pendrive al día' }
    } catch {
        Aviso "No se han podido guardar las copias en el pendrive: $($_.Exception.Message)"
    }
}

# Trae del pendrive las copias que no estén en backups\pendrive (para poder restaurarlas)
function Traer-Del-Pendrive {
    if (-not $script:DirPendrive) { return }
    try {
        $copiadas = Copiar-Copias $script:DirPendrive $Intermedia
        if ($copiadas -gt 0) { Ok "Pendrive: $copiadas copia(s) traída(s) para poder restaurarlas" }
    } catch {
        Aviso "No se han podido leer las copias del pendrive: $($_.Exception.Message)"
    }
}

# Google Drive: la carpeta de CLOUD_DIR tiene que existir (la crea la app de Google Drive). Si no
# existe, NO se deja que Docker la cree (sería una carpeta normal, sin sincronizar): se monta
# una carpeta vacía sin marcador y la app avisa.
function Preparar-Nube {
    $dir = Env-Valor 'CLOUD_DIR'
    if ($dir -ne '' -and (Test-Path -LiteralPath $dir -PathType Container)) {
        try {
            New-Item -ItemType File -Force -Path (Join-Path $dir '.caudal-backups') -ErrorAction Stop | Out-Null
            Ok 'Carpeta de Google Drive disponible'
            return
        } catch {
            Aviso "No se puede escribir en la carpeta de Google Drive: $dir"
        }
    } elseif ($dir -eq '') {
        Aviso 'CLOUD_DIR está vacío en el .env: las copias no irán a Google Drive'
    } else {
        Aviso "No existe la carpeta de Google Drive: $dir"
    }
    $env:CLOUD_DIR = Join-Path $Root 'backups\sin-nube'
}

function App-En-Marcha {
    $id = & docker compose ps --status running -q app 2> $null
    return [bool]$id
}

# Espera a que la app responda en /api/health (hasta 3 minutos)
function Esperar-App {
    $url = (Url-App) + '/api/health'
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $respuesta = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
            if ($respuesta.StatusCode -eq 200) { Ok 'Caudal está listo'; return $true }
        } catch {
            # todavía no responde
        }
        Start-Sleep -Seconds 2
    }
    Fallo "Caudal no responde en $url"
    Write-Host '       Para ver qué pasa: docker compose logs app --tail 50'
    Pausa-Y-Salir 1
}
