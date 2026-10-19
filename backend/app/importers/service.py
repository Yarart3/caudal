"""Importar un extracto en una cuenta: leer, comprobar, guardar sin duplicados.

Se usa desde POST /api/imports (parte 1.4). Después de guardar, busca las transferencias
internas entre los movimientos nuevos y los que ya había (app/transfers).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.importers import check_format
from app.importers.base import ImportFormatError, RowError, open_workbook
from app.importers.fingerprint import fingerprint
from app.models import Account, Transaction
from app.transfers import match_internal_transfers
from app.transfers.matcher import mark_internal


@dataclass
class ImportSummary:
    """Resumen para la pantalla: «8 leídos · 6 nuevos · 2 ya existían»."""

    read: int = 0  # filas con datos del extracto (las leídas bien + las que han fallado)
    new: int = 0  # guardadas ahora
    duplicates: int = 0  # ya estaban guardadas de una importación anterior
    review: int = 0  # nuevas que quedan por revisar (sin categoría)
    internal: int = 0  # nuevas marcadas como transferencia interna
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    closing_balance: Decimal | None = None
    closing_date: date | None = None


def import_statement(db: Session, account: Account, data: bytes) -> ImportSummary:
    """Importa el extracto `data` (bytes del .xlsx) en `account` y hace commit.

    Lanza ImportFormatError si no se puede importar nada (archivo no válido, banco que no es
    el de la cuenta, falta una columna). En ese caso no se guarda nada.
    """
    if not account.import_format:
        raise ImportFormatError(
            f"La cuenta «{account.name}» no tiene banco asociado: sus movimientos se apuntan a mano"
        )
    workbook = open_workbook(data)
    importer = check_format(workbook, account.import_format)
    parsed = importer.parse(workbook)

    summary = ImportSummary(
        read=len(parsed.transactions) + len(parsed.errors),
        errors=parsed.errors,
        warnings=parsed.warnings,
        closing_balance=parsed.closing_balance,
        closing_date=parsed.closing_date,
    )
    by_fingerprint = {fingerprint(account.id, tx): tx for tx in parsed.transactions}
    rows = [
        {
            "account_id": account.id,
            "date": tx.date,
            "description": tx.description,
            "amount": tx.amount,
            "category_status": "review",
            "fingerprint": fp,
        }
        for fp, tx in by_fingerprint.items()
    ]
    inserted: list[tuple[int, str]] = []
    if rows:
        # Las que ya existen (misma cuenta y huella) se saltan sin error; RETURNING devuelve
        # solo las insertadas de verdad
        stmt = (
            insert(Transaction)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_transactions_account_id_fingerprint")
            .returning(Transaction.id, Transaction.fingerprint)
        )
        inserted = [(row.id, row.fingerprint) for row in db.execute(stmt)]
    summary.new = len(inserted)
    summary.duplicates = len(parsed.transactions) - summary.new

    # Transferencias internas: las conversiones de divisa lo son siempre; el resto, si tienen
    # pareja en otra cuenta del usuario
    hints = {
        tx_id: hint
        for tx_id, fp in inserted
        if (hint := by_fingerprint[fp].transfer_hint) is not None
    }
    conversions = {tx_id for tx_id, hint in hints.items() if hint == "conversion"}
    for tx in db.scalars(select(Transaction).where(Transaction.id.in_(conversions))):
        mark_internal(tx)
    db.flush()
    matched = match_internal_transfers(db, account.user_id, [i for i, _ in inserted], hints)
    summary.internal = len(conversions | matched)
    summary.review = summary.new - summary.internal

    _update_reference_balance(account, parsed.closing_balance, parsed.closing_date)
    db.commit()
    return summary


def _update_reference_balance(account: Account, balance: Decimal | None, when: date | None) -> None:
    """El saldo de referencia pasa a ser el último del extracto, salvo que el extracto sea más
    antiguo que el saldo que ya hay (importar un mes viejo no debe "rebobinar" la cuenta)."""
    if balance is None or when is None:
        return
    if account.reference_balance_date is None or when >= account.reference_balance_date:
        account.reference_balance = balance
        account.reference_balance_date = when
