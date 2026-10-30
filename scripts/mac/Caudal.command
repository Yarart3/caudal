#!/bin/bash
# Abre Caudal con doble clic (DISENO §11): Docker Desktop, pendrive, docker compose up,
# espera a que responda y abre el navegador.
source "$(dirname "$0")/_comun.sh"

titulo "Abriendo Caudal"
comprobar_env
esperar_docker
preparar_pendrive
preparar_onedrive

echo "  Arrancando Caudal…"
if ! docker compose up -d; then
  fallo "No se ha podido arrancar Caudal"
  pausa_y_salir 1
fi
esperar_app

open "$(url_app)"
ok "Caudal abierto en el navegador: $(url_app)"
echo
echo "  Puedes cerrar esta ventana. Para cerrar Caudal, usa «Cerrar Caudal»."
