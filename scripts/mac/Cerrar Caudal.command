#!/bin/bash
# Cierra Caudal con doble clic (DISENO §11 y §15): guarda la versión final (copia + candado
# «cerrado en este equipo» en Google Drive), docker compose down y, si quieres, cierra Docker
# Desktop. Los datos se conservan en el volumen de Docker.
source "$(dirname "$0")/_comun.sh"

titulo "Cerrando Caudal"
comprobar_env

if ! docker info >/dev/null 2>&1; then
  ok "Docker no está en marcha: Caudal ya está cerrado"
  exit 0
fi

if app_en_marcha; then
  echo "  Guardando la versión final (copia de seguridad y Google Drive)…"
  # Si hay otra copia en marcha (la periódica), la propia app espera hasta 1 minuto
  docker compose exec -T app python -m app.sync close
  codigo=$?
  if [ "$codigo" -eq 0 ]; then
    ok "Versión final guardada"
  else
    fallo "La versión final no ha llegado a Google Drive (mira el mensaje de arriba)"
    echo "    Si cierras igualmente, el otro equipo no verá lo que has hecho hasta que"
    echo "    vuelvas a abrir y cerrar Caudal aquí."
    read -r -p "  ¿Cerrar Caudal igualmente? (s/N): " respuesta || respuesta=""
    case "$respuesta" in
      s | S) ;;
      *)
        echo "  No se ha cerrado nada."
        pausa_y_salir 1
        ;;
    esac
  fi
else
  aviso "Caudal no estaba abierto: no hace falta copia final"
fi

echo "  Parando Caudal…"
if ! docker compose down; then
  fallo "No se ha podido parar Caudal"
  pausa_y_salir 1
fi
ok "Caudal cerrado. Los datos se conservan."

echo
read -r -p "¿Cerrar también Docker Desktop para liberar memoria? (S/n): " respuesta || respuesta=""
case "$respuesta" in
  n | N) ;;
  *) osascript -e 'quit app "Docker"' >/dev/null 2>&1 && ok "Docker Desktop cerrado" ;;
esac
