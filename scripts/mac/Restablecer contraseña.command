#!/bin/bash
# Cambia la contraseña de un usuario de Caudal (por si se olvida), lo desbloquea si estaba
# bloqueado por intentos fallidos y cierra sus sesiones abiertas.
source "$(dirname "$0")/_comun.sh"

titulo "Restablecer la contraseña de un usuario de Caudal"
comprobar_env
esperar_docker
# Solo para que Docker no cree carpetas de backup que no existen (aquí no se hacen copias)
preparar_pendrive >/dev/null
preparar_onedrive >/dev/null

echo
docker compose run --rm app python -m app.auth.reset
pausa_y_salir $?
