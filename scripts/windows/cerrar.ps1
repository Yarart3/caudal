# Cierra Caudal (DISENO §11): copia final, docker compose down y, si quieres, cierra Docker
# Desktop. Los datos se conservan en el volumen de Docker. Se lanza con «Cerrar Caudal.bat».
. (Join-Path $PSScriptRoot '_comun.ps1')

Titulo 'Cerrando Caudal'
Comprobar-Env

if (-not (Docker-Listo)) {
    Ok 'Docker no está en marcha: Caudal ya está cerrado'
    Start-Sleep -Seconds 3
    exit 0
}

if (App-En-Marcha) {
    Write-Host '  Haciendo la copia de seguridad final...'
    $intentos = 0
    while ($true) {
        & docker compose exec -T app python -m app.backup run --trigger close
        $codigo = $LASTEXITCODE
        # 2 = hay otra copia en marcha (por ejemplo, la periódica): se espera hasta 1 minuto
        if ($codigo -eq 2 -and $intentos -lt 12) {
            $intentos++
            Write-Host '  Esperando a que termine la otra copia...'
            Start-Sleep -Seconds 5
            continue
        }
        break
    }
    if ($codigo -eq 0) {
        Ok 'Copia final hecha'
    } else {
        Fallo 'No se ha podido hacer la copia final'
        $respuesta = Read-Host '  ¿Cerrar Caudal igualmente? (s/N)'
        if ($respuesta -notmatch '^[sS]') {
            Write-Host '  No se ha cerrado nada.'
            Pausa-Y-Salir 1
        }
    }
} else {
    Aviso 'Caudal no estaba abierto: no hace falta copia final'
}

Write-Host '  Parando Caudal...'
& docker compose down
if ($LASTEXITCODE -ne 0) {
    Fallo 'No se ha podido parar Caudal'
    Pausa-Y-Salir 1
}
Ok 'Caudal cerrado. Los datos se conservan.'

Write-Host ''
$respuesta = Read-Host '¿Cerrar también Docker Desktop para liberar memoria? (S/n)'
if ($respuesta -notmatch '^[nN]') {
    # "docker desktop stop" existe en las versiones recientes de Docker Desktop; si no, se cierra
    # el proceso (Caudal ya está parado, así que no hay contenedores a medias)
    & docker desktop stop *> $null
    if ($LASTEXITCODE -ne 0) {
        Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    Ok 'Docker Desktop cerrado'
}
Start-Sleep -Seconds 3
