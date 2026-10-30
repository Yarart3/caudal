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

# Pendrive: se busca por su nombre de volumen (USB_LABEL), no por la letra de unidad. Si está,
# se crea la carpeta CaudalBackups con su marcador y se pasa a Docker con USB_BACKUP_DIR. Si no
# está, no se pasa nada: Docker monta una carpeta vacía sin marcador y la app avisa.
function Preparar-Pendrive {
    $etiqueta = Env-Valor 'USB_LABEL' 'Gerard'
    Remove-Item Env:USB_BACKUP_DIR -ErrorAction SilentlyContinue
    $discos = @(Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction SilentlyContinue |
            Where-Object { $_.VolumeName -eq $etiqueta })
    if ($discos.Count -eq 0) {
        Aviso "Pendrive «$etiqueta» no conectado: las copias irán solo a OneDrive"
        return
    }
    if ($discos.Count -gt 1) {
        $letras = ($discos | ForEach-Object { $_.DeviceID }) -join ', '
        Fallo "Hay varias unidades llamadas «$etiqueta» ($letras): no se usa ninguna."
        return
    }
    $dir = $discos[0].DeviceID + '\CaudalBackups'
    try {
        New-Item -ItemType Directory -Force -Path $dir -ErrorAction Stop | Out-Null
        New-Item -ItemType File -Force -Path (Join-Path $dir '.caudal-backups') -ErrorAction Stop | Out-Null
    } catch {
        Aviso "El pendrive «$etiqueta» está conectado, pero no se puede escribir en él"
        return
    }
    $env:USB_BACKUP_DIR = $dir
    Ok "Pendrive «$etiqueta» conectado ($($discos[0].DeviceID))"
}

# OneDrive: la carpeta de ONEDRIVE_DIR tiene que existir (la crea la app de OneDrive). Si no
# existe, NO se deja que Docker la cree (sería una carpeta normal, sin sincronizar): se monta
# una carpeta vacía sin marcador y la app avisa.
function Preparar-OneDrive {
    $dir = Env-Valor 'ONEDRIVE_DIR'
    if ($dir -ne '' -and (Test-Path -LiteralPath $dir -PathType Container)) {
        try {
            New-Item -ItemType File -Force -Path (Join-Path $dir '.caudal-backups') -ErrorAction Stop | Out-Null
            Ok 'Carpeta de OneDrive disponible'
            return
        } catch {
            Aviso "No se puede escribir en la carpeta de OneDrive: $dir"
        }
    } elseif ($dir -eq '') {
        Aviso 'ONEDRIVE_DIR está vacío en el .env: las copias no irán a OneDrive'
    } else {
        Aviso "No existe la carpeta de OneDrive: $dir"
    }
    $env:ONEDRIVE_DIR = Join-Path $Root 'backups\sin-onedrive'
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
