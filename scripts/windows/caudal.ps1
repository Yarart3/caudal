# Abre Caudal (DISENO §11 y §15): Docker Desktop, pendrive y Google Drive, prepara la app
# (reconstruye la imagen si el código ha cambiado), trae la última versión del otro equipo
# (python -m app.sync open), arranca y abre el navegador. Se lanza con «Caudal.bat».
. (Join-Path $PSScriptRoot '_comun.ps1')

Titulo 'Abriendo Caudal'
Comprobar-Env
Esperar-Docker
Preparar-Pendrive
Preparar-Nube

if (App-En-Marcha) {
    Ok 'Caudal ya estaba abierto'
    Start-Process (Url-App)
    Start-Sleep -Seconds 3
    exit 0
}

Write-Host '  Preparando la app (después de un «git pull» puede tardar unos minutos)...'
& docker compose build --quiet app
if ($LASTEXITCODE -ne 0) {
    Fallo 'No se ha podido preparar la app'
    Pausa-Y-Salir 1
}

Write-Host '  Buscando la última versión en Google Drive...'
& docker compose run --rm app python -m app.sync open
$codigo = $LASTEXITCODE
if ($codigo -ne 0) {
    & docker compose stop db *> $null
    switch ($codigo) {
        2 { Aviso 'No se ha abierto Caudal.' }
        3 { Fallo 'Caudal está abierto en el otro equipo: ciérralo allí con «Cerrar Caudal».' }
        4 { Fallo 'Actualiza el código («git pull» en la carpeta de Caudal) y vuelve a abrir.' }
        default { Fallo 'No se ha podido abrir Caudal (mira el mensaje de arriba).' }
    }
    Pausa-Y-Salir $codigo
}

Write-Host '  Arrancando Caudal...'
& docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Fallo 'No se ha podido arrancar Caudal'
    Pausa-Y-Salir 1
}
$null = Esperar-App

Start-Process (Url-App)
Ok "Caudal abierto en el navegador: $(Url-App)"
Write-Host ''
Write-Host '  Para cerrar Caudal, usa «Cerrar Caudal». Esta ventana se cierra sola.'
Start-Sleep -Seconds 5
