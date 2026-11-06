#!/bin/bash
# Restaura un backup de Caudal (DISENO §12): elige el archivo de la lista (pendrive, Google Drive
# y conflictos/), pide la contraseña y lo restaura sobre una base vacía. Antes hace una copia de
# lo actual. Después, lo restaurado pasa a ser la versión con la que se sigue (Fase R).
source "$(dirname "$0")/_comun.sh"

titulo "Restaurar un backup de Caudal"
comprobar_env
esperar_docker
preparar_pendrive
preparar_nube

# Mientras se restaura, la app tiene que estar parada (nadie puede estar usando la base)
estaba_abierta=0
if app_en_marcha; then
  estaba_abierta=1
  echo "  Parando la app mientras se restaura…"
  docker compose stop app >/dev/null
fi

echo
docker compose run --rm app python -m app.backup restore
codigo=$?
echo

if [ "$codigo" -eq 0 ]; then
  # Sin esto, al abrir se cambiaría sola por la última versión del otro equipo
  docker compose run --rm app python -m app.sync adopt
  docker compose run --rm app python -m app.sync open
  abrir=$?
else
  abrir=$((1 - estaba_abierta))  # si estaba abierta y no se ha restaurado, se vuelve a abrir
fi

if [ "$abrir" -eq 0 ]; then
  echo "  Abriendo Caudal…"
  if docker compose up -d && esperar_app; then
    open "$(url_app)"
  fi
fi

case "$codigo" in
  0) ok "Restauración terminada. Comprueba en Caudal que los datos son los que esperabas." ;;
  2) aviso "No se ha restaurado nada." ;;
  *) fallo "La restauración ha fallado (mira el mensaje de arriba)." ;;
esac
pausa_y_salir "$codigo"
