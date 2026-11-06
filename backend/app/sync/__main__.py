"""Sincronización desde la terminal (la usan los scripts de abrir y cerrar Caudal).

    python -m app.sync open [--force]   antes de arrancar la app: trae la última versión
    python -m app.sync close            con la app en marcha: copia final y candado «cerrado»
    python -m app.sync status           qué versión hay aquí y qué dice Google Drive
    python -m app.sync adopt            tras «Restaurar backup»: seguir con lo restaurado

Códigos de salida: 0 bien (se puede abrir), 1 error, 2 cancelado, 3 abierto en el otro
equipo, 4 hay que actualizar el código (git pull).
"""

import argparse
import sys

from app.config import get_settings
from app.db import engine
from app.sync.service import (
    OK,
    SyncContext,
    adopt_restored,
    close_sync,
    open_sync,
    status_lines,
)


def _ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.sync", description="Sincronización")
    sub = parser.add_subparsers(dest="command", required=True)
    open_cmd = sub.add_parser("open", help="trae la última versión antes de abrir")
    open_cmd.add_argument(
        "--force", action="store_true", help="abrir aunque el candado diga que está abierto"
    )
    sub.add_parser("close", help="copia final y candado «cerrado»")
    sub.add_parser("status", help="versión de este equipo y de Google Drive")
    sub.add_parser("adopt", help="tras restaurar un backup a mano: seguir con lo restaurado")
    args = parser.parse_args(argv)

    ctx = SyncContext(settings=get_settings(), engine=engine, ask=_ask)
    if args.command == "open":
        return open_sync(ctx, force=args.force)
    if args.command == "close":
        return close_sync(ctx)
    if args.command == "adopt":
        return adopt_restored(ctx)
    for line in status_lines(ctx):
        print(line)
    return OK


if __name__ == "__main__":
    sys.exit(main())
