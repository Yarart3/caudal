#!/bin/bash
# Abre Caudal con doble clic (DISENO §11 y §15): Docker Desktop, pendrive y Google Drive,
# prepara la app (reconstruye la imagen si el código ha cambiado), trae la última versión del
# otro equipo (python -m app.sync open), arranca y abre el navegador.
source "$(dirname "$0")/_comun.sh"

titulo "Abriendo Caudal"
comprobar_env
esperar_docker
preparar_pendrive
preparar_nube

if app_en_marcha; then
  ok "Caudal ya estaba abierto"
  open "$(url_app)"
  exit 0
fi

echo "  Preparando la app (después de un «git pull» puede tardar unos minutos)…"
if ! docker compose build --quiet app; then
  fallo "No se ha podido preparar la app"
  pausa_y_salir 1
fi

echo "  Buscando la última versión en Google Drive…"
docker compose run --rm app python -m app.sync open
codigo=$?
if [ "$codigo" -ne 0 ]; then
  docker compose stop db >/dev/null 2>&1
  case "$codigo" in
    2) aviso "No se ha abierto Caudal." ;;
    3) fallo "Caudal está abierto en el otro equipo: ciérralo allí con «Cerrar Caudal»." ;;
    4) fallo "Actualiza el código («git pull» en la carpeta de Caudal) y vuelve a abrir." ;;
    *) fallo "No se ha podido abrir Caudal (mira el mensaje de arriba)." ;;
  esac
  pausa_y_salir "$codigo"
fi

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
