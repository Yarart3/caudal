#!/bin/bash
# Funciones comunes de los scripts de Mac de Caudal. No se ejecuta solo: lo cargan los .command.
# Compatible con el bash 3.2 que trae macOS.

# Al abrir un .command con doble clic, el PATH es el mínimo: se añaden los sitios de docker
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin:$HOME/.docker/bin:/Applications/Docker.app/Contents/Resources/bin"

# Raíz del proyecto (scripts/mac/ → ../..)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

titulo() { printf '\n\033[1m%s\033[0m\n\n' "$1"; }
ok() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
aviso() { printf '  \033[33m!\033[0m %s\n' "$1"; }
fallo() { printf '  \033[31m✗\033[0m %s\n' "$1"; }

# Deja la ventana abierta para que se pueda leer el mensaje y sale con el código indicado
pausa_y_salir() {
  echo
  read -r -p "Pulsa Enter para cerrar esta ventana… " _ || true
  exit "${1:-1}"
}

comprobar_env() {
  if [ ! -f .env ]; then
    fallo "No existe el archivo .env en $ROOT"
    echo "    Cópialo de .env.example y rellénalo (README, «Instalación»)."
    pausa_y_salir 1
  fi
}

# Valor de una variable del .env, sin comillas. No se usa "source": el .env no es un script.
env_valor() {
  local nombre="$1" defecto="${2:-}" linea valor
  linea="$(grep -E "^${nombre}=" .env 2>/dev/null | tail -n 1)"
  valor="${linea#*=}"
  valor="${valor%$'\r'}"
  case "$valor" in
    \"*\") valor="${valor#\"}"; valor="${valor%\"}" ;;
    \'*\') valor="${valor#\'}"; valor="${valor%\'}" ;;
  esac
  [ -z "$valor" ] && valor="$defecto"
  printf '%s' "$valor"
}

url_app() { printf 'http://localhost:%s' "$(env_valor APP_PORT 8080)"; }

# Abre Docker Desktop si hace falta y espera a que esté listo (hasta 3 minutos)
esperar_docker() {
  if docker info >/dev/null 2>&1; then
    ok "Docker está en marcha"
    return 0
  fi
  if [ ! -d /Applications/Docker.app ]; then
    fallo "No se encuentra Docker Desktop en Aplicaciones"
    pausa_y_salir 1
  fi
  echo "  Abriendo Docker Desktop (puede tardar un poco)…"
  open -a Docker
  for _ in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then
      ok "Docker está listo"
      return 0
    fi
    sleep 2
  done
  fallo "Docker Desktop no ha arrancado en 3 minutos. Ábrelo a mano y vuelve a intentarlo."
  pausa_y_salir 1
}

# Pendrive: se busca por su nombre de volumen (USB_LABEL), no por la ruta. Si está, se crea la
# carpeta CaudalBackups con su marcador y se pasa a Docker con USB_BACKUP_DIR. Si no está, no se
# pasa nada: Docker monta una carpeta vacía sin marcador y la app avisa «Pendrive no conectado».
preparar_pendrive() {
  local etiqueta volumen
  etiqueta="$(env_valor USB_LABEL Gerard)"
  volumen="/Volumes/$etiqueta"
  unset USB_BACKUP_DIR
  if mount | grep -qF " on $volumen ("; then
    if mkdir -p "$volumen/CaudalBackups" && touch "$volumen/CaudalBackups/.caudal-backups"; then
      export USB_BACKUP_DIR="$volumen/CaudalBackups"
      ok "Pendrive «$etiqueta» conectado"
      return 0
    fi
    aviso "El pendrive «$etiqueta» está conectado, pero no se puede escribir en él"
    return 1
  fi
  aviso "Pendrive «$etiqueta» no conectado: las copias irán solo a OneDrive"
  if mount | grep -qF " on $volumen 1 ("; then
    aviso "Hay un volumen «$etiqueta 1»: macOS cambia el nombre si dos discos se llaman igual."
  fi
  return 1
}

# OneDrive: la carpeta de ONEDRIVE_DIR tiene que existir (la crea la app de OneDrive). Si no
# existe, NO se deja que Docker la cree (sería una carpeta normal, sin sincronizar): se monta
# una carpeta vacía sin marcador y la app avisa.
preparar_onedrive() {
  local dir
  dir="$(env_valor ONEDRIVE_DIR)"
  if [ -n "$dir" ] && [ -d "$dir" ]; then
    if touch "$dir/.caudal-backups"; then
      ok "Carpeta de OneDrive disponible"
      return 0
    fi
    aviso "No se puede escribir en la carpeta de OneDrive: $dir"
  elif [ -z "$dir" ]; then
    aviso "ONEDRIVE_DIR está vacío en el .env: las copias no irán a OneDrive"
  else
    aviso "No existe la carpeta de OneDrive: $dir"
  fi
  export ONEDRIVE_DIR="$ROOT/backups/sin-onedrive"
  return 1
}

app_en_marcha() {
  [ -n "$(docker compose ps --status running -q app 2>/dev/null)" ]
}

# Espera a que la app responda en /api/health (hasta 3 minutos)
esperar_app() {
  local url
  url="$(url_app)/api/health"
  for _ in $(seq 1 90); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      ok "Caudal está listo"
      return 0
    fi
    sleep 2
  done
  fallo "Caudal no responde en $url"
  echo "    Para ver qué pasa: docker compose logs app --tail 50"
  pausa_y_salir 1
}
