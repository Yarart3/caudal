# Cierra Caudal (DISENO §11 y §15): guarda la versión final (copia + candado «cerrado en este
# equipo» en Google Drive), docker compose down y, si quieres, cierra Docker Desktop. Los datos
# se conservan en el volumen de Docker. Se lanza con «Cerrar Caudal.bat».
. (Join-Path $PSScriptRoot '_comun.ps1')

Titulo 'Cerrando Caudal'
Comprobar-Env

if (-not (Docker-Listo)) {
    Ok 'Docker no está en marcha: Caudal ya está cerrado'
    Start-Sleep -Seconds 3
    exit 0
}

if (App-En-Marcha) {
    Write-Host '  Guardando la versión final (copia de seguridad y Google Drive)...'
    # Si hay otra copia en marcha (la periódica), la propia app espera hasta 1 minuto
    & docker compose exec -T app python -m app.sync close
    if ($LASTEXITCODE -eq 0) {
        Ok 'Versión final guardada'
    } else {
        Fallo 'La versión final no ha llegado a Google Drive (mira el mensaje de arriba)'
        Write-Host '       Si cierras igualmente, el otro equipo no verá lo que has hecho hasta que'
        Write-Host '       vuelvas a abrir y cerrar Caudal aquí.'
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
