"""Backups desde la terminal (los usan los scripts de arranque, cierre y restauración).

    python -m app.backup run [--trigger close]   hace un backup ahora
    python -m app.backup list                     lista los backups disponibles
    python -m app.backup restore                  restaura uno (pregunta cuál)

Códigos de salida: 0 bien, 1 error, 2 no se ha hecho nada (cancelado u otro backup en marcha).
"""

import argparse
import getpass
import sys
from pathlib import Path

from app.backup.crypto import BackupDecryptError
from app.backup.restore import (
    BackupFile,
    available_backups,
    check_dump,
    decrypted_dump,
    recreate_database,
    restore_dump,
)
from app.backup.service import LABELS, TRIGGERS, BackupBusyError, BackupError, run_backup
from app.config import Settings, get_settings
from app.db import engine


def _size(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{n / 1024:.0f} KB"


def cmd_run(trigger: str) -> int:
    try:
        result = run_backup(trigger)
    except BackupBusyError as error:
        print(error)
        return 2
    except BackupError as error:
        print(f"ERROR: {error}")
        return 1
    for r in result.results:
        print(f"  {LABELS[r.destination]:9} {'✓' if r.ok else '✗'}  {r.message}")
    if not result.ok:
        print("ERROR: la copia no se ha guardado en ningún sitio")
        return 1
    print(f"Copia hecha: {result.filename}")
    return 0


def _print_list(backups: list[BackupFile]) -> None:
    for i, b in enumerate(backups, start=1):
        print(f"  {i:3}. {b.path.name}  {b.label:9} {_size(b.size):>9}")


def cmd_list() -> int:
    backups = available_backups(get_settings())
    if not backups:
        print("No hay backups (o el pendrive y OneDrive no están disponibles).")
        return 1
    _print_list(backups)
    return 0


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def cmd_restore() -> int:
    settings = get_settings()
    backups = available_backups(settings)
    if not backups:
        print("No hay backups (o el pendrive y OneDrive no están disponibles).")
        return 1
    print("Backups disponibles (el 1 es el más reciente):")
    _print_list(backups)
    choice = _ask("\nNúmero del backup que quieres restaurar (Enter = cancelar): ")
    if not choice.isdigit() or not 1 <= int(choice) <= len(backups):
        print("Cancelado.")
        return 2
    chosen = backups[int(choice) - 1]

    try:
        password = getpass.getpass("Contraseña del backup (Enter = la del .env): ")
    except EOFError:
        password = ""
    if not password and settings.backup_password:
        password = settings.backup_password.get_secret_value()

    # Se descifra y se comprueba ANTES de tocar nada: con una contraseña incorrecta o un archivo
    # dañado, la base queda como estaba.
    try:
        with decrypted_dump(chosen.path, password) as dump:
            check_dump(dump, settings)
            return _confirm_and_restore(chosen, dump, settings)
    except BackupDecryptError as error:
        print(f"ERROR: {error}. No se ha tocado nada.")
        return 1
    except BackupError as error:
        print(f"ERROR: {error}")
        return 1


def _confirm_and_restore(chosen: BackupFile, dump: Path, settings: Settings) -> int:
    print(
        f"\nSe BORRARÁN todos los datos actuales de Caudal y se cambiarán por {chosen.path.name}."
    )
    if _ask("Escribe RESTAURAR para seguir: ") != "RESTAURAR":
        print("Cancelado. No se ha tocado nada.")
        return 2

    # Copia de lo que hay ahora, por si el backup elegido no era el bueno
    print("Haciendo antes una copia de los datos actuales…")
    try:
        before = run_backup("pre_restore")
        saved = before.ok
        if saved:
            print(f"  Copia previa: {before.filename}")
    except BackupError as error:
        print(f"  {error}")
        saved = False
    if not saved:
        answer = _ask("No se ha podido hacer la copia previa. ¿Seguir igualmente? (s/N): ")
        if answer.lower() != "s":
            print("Cancelado. No se ha tocado nada.")
            return 2

    engine.dispose()  # cierra las conexiones de este proceso antes de borrar la base
    print("Restaurando…")
    try:
        recreate_database(settings, settings.postgres_db)
        restore_dump(dump, settings, settings.postgres_db)
    except BackupError as error:
        print(f"ERROR: {error}")
        print("La base puede haber quedado vacía: restaura otro backup (o la copia previa).")
        return 1
    print("Restaurado. Al abrir Caudal se aplicarán las migraciones pendientes, si las hay.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.backup", description="Backups de Caudal")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="hace un backup ahora")
    run.add_argument("--trigger", choices=sorted(TRIGGERS), default="manual")
    sub.add_parser("list", help="lista los backups disponibles")
    sub.add_parser("restore", help="restaura un backup (pregunta cuál)")
    args = parser.parse_args(argv)
    if args.command == "run":
        return cmd_run(args.trigger)
    if args.command == "list":
        return cmd_list()
    return cmd_restore()


if __name__ == "__main__":
    sys.exit(main())
