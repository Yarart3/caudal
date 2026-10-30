# Cambia la contraseña de un usuario de Caudal (por si se olvida), lo desbloquea si estaba
# bloqueado por intentos fallidos y cierra sus sesiones abiertas.
# Se lanza con «Restablecer contraseña.bat».
. (Join-Path $PSScriptRoot '_comun.ps1')

Titulo 'Restablecer la contraseña de un usuario de Caudal'
Comprobar-Env
Esperar-Docker
# Solo para que Docker no cree carpetas de backup que no existen (aquí no se hacen copias)
Preparar-Pendrive *> $null
Preparar-OneDrive *> $null

Write-Host ''
& docker compose run --rm app python -m app.auth.reset
Pausa-Y-Salir $LASTEXITCODE
