# Restaura un backup de Caudal (DISENO §12): elige el archivo de la lista (pendrive, Google Drive
# y conflictos/), pide la contraseña y lo restaura sobre una base vacía. Antes hace una copia de
# lo actual. Después, lo restaurado pasa a ser la versión con la que se sigue (Fase R).
# Se lanza con «Restaurar backup.bat».
. (Join-Path $PSScriptRoot '_comun.ps1')

Titulo 'Restaurar un backup de Caudal'
Comprobar-Env
Esperar-Docker
Preparar-Pendrive
Traer-Del-Pendrive
Preparar-Nube

# Mientras se restaura, la app tiene que estar parada (nadie puede estar usando la base)
$estabaAbierta = App-En-Marcha
if ($estabaAbierta) {
    Write-Host '  Parando la app mientras se restaura...'
    & docker compose stop app *> $null
}

Write-Host ''
& docker compose run --rm app python -m app.backup restore
$codigo = $LASTEXITCODE
Write-Host ''

if ($codigo -eq 0) {
    # Sin esto, al abrir se cambiaría sola por la última versión del otro equipo
    & docker compose run --rm app python -m app.sync adopt
    & docker compose run --rm app python -m app.sync open
    $abrir = ($LASTEXITCODE -eq 0)
} else {
    $abrir = $estabaAbierta  # si estaba abierta y no se ha restaurado, se vuelve a abrir
}

if ($abrir) {
    Write-Host '  Abriendo Caudal...'
    & docker compose up -d
    if ($LASTEXITCODE -eq 0 -and (Esperar-App)) { Start-Process (Url-App) }
}

switch ($codigo) {
    0 { Ok 'Restauración terminada. Comprueba en Caudal que los datos son los que esperabas.' }
    2 { Aviso 'No se ha restaurado nada.' }
    default { Fallo 'La restauración ha fallado (mira el mensaje de arriba).' }
}
Pausa-Y-Salir $codigo
