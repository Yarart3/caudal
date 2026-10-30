# Abre Caudal (DISENO §11): Docker Desktop, pendrive, docker compose up, espera a que
# responda y abre el navegador. Se lanza con doble clic en «Caudal.bat».
. (Join-Path $PSScriptRoot '_comun.ps1')

Titulo 'Abriendo Caudal'
Comprobar-Env
Esperar-Docker
Preparar-Pendrive
Preparar-OneDrive

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
