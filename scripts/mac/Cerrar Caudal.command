#!/bin/bash
# Cierra Caudal con doble clic (DISENO §11): copia final, docker compose down y, si quieres,
# cierra Docker Desktop. Los datos se conservan en el volumen de Docker.
source "$(dirname "$0")/_comun.sh"

titulo "Cerrando Caudal"
comprobar_env

if ! docker info >/dev/null 2>&1; then
  ok "Docker no está en marcha: Caudal ya está cerrado"
  exit 0
fi

if app_en_marcha; then
  echo "  Haciendo la copia de seguridad final…"
  intentos=0
  while :; do
    docker compose exec -T app python -m app.backup run --trigger close
    codigo=$?
    # 2 = hay otra copia en marcha (por ejemplo, la periódica): se espera hasta 1 minuto
    if [ "$codigo" -eq 2 ] && [ "$intentos" -lt 12 ]; then
      intentos=$((intentos + 1))
      echo "  Esperando a que termine la otra copia…"
      sleep 5
      continue
    fi
    break
  done
  if [ "$codigo" -eq 0 ]; then
    ok "Copia final hecha"
  else
    fallo "No se ha podido hacer la copia final"
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
