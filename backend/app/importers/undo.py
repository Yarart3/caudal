"""Deshacer una importación de extracto (Fase 5).

Borra los movimientos que entraron en esa importación (también los que se hayan editado
después) y deja la cuenta como estaba:

- **Saldo de referencia:** vuelve al de antes de importar, salvo que otra importación o el
  usuario lo hayan cambiado después (entonces se respeta el actual).
- **Transferencias internas:** si un movimiento borrado estaba emparejado con otro de otra
  cuenta, esa otra pata deja de estar marcada como interna y vuelve a pasar por las reglas.
  Las parejas no se guardan (DISENO 9.3), así que se busca como al emparejar: importe opuesto,
  ≤ 3 días y en otra cuenta del usuario. Si la otra pata podría ser pareja de otro movimiento
  que sigue ahí, no se toca: es mejor una interna de más que esconder una de verdad.

Si se vuelve a importar el mismo extracto, los movimientos vuelven a entrar.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categories import apply_rules
from app.models import Account, Import, Transaction
from app.transfers.matcher import MAX_DAYS


@dataclass
class UndoResult:
    deleted: int  # movimientos borrados
    unpaired: int  # transferencias de otras cuentas que dejan de ser internas
    balance_restored: bool  # el saldo de referencia ha vuelto al de antes de importar


def _counterparts(
    db: Session, user_id: int, tx: Transaction, exclude: set[int]
) -> list[Transaction]:
    """Movimientos internos de otras cuentas del usuario que podrían ser la pareja de `tx`."""
    return list(
        db.scalars(
            select(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.user_id == user_id,
                Transaction.account_id != tx.account_id,
                Transaction.amount == -tx.amount,
                Transaction.is_internal_transfer.is_(True),
                Transaction.date >= tx.date - timedelta(days=MAX_DAYS),
                Transaction.date <= tx.date + timedelta(days=MAX_DAYS),
                Transaction.id.not_in(exclude),
            )
            .order_by(Transaction.date, Transaction.id)
        )
    )


def undo_import(db: Session, batch: Import, user_id: int) -> UndoResult:
    """Deshace `batch` (que ya se ha comprobado que es del usuario). No hace commit."""
    txs = list(db.scalars(select(Transaction).where(Transaction.import_id == batch.id)))
    deleted_ids = {tx.id for tx in txs}

    # Otras patas de las transferencias internas que se van a borrar
    unpair: list[Transaction] = []
    taken: set[int] = set()
    for tx in txs:
        if not tx.is_internal_transfer or tx.amount == 0:
            continue
        candidates = [
            c for c in _counterparts(db, user_id, tx, deleted_ids | taken) if c.id not in taken
        ]
        if not candidates:
            continue  # conversión de divisa de Wise o pareja borrada a mano
        partner = min(candidates, key=lambda c: (abs((c.date - tx.date).days), c.id))
        taken.add(partner.id)
        # ¿Podría ser pareja de otro movimiento que se queda? Entonces se deja como está
        if _counterparts(db, user_id, partner, deleted_ids | {partner.id}):
            continue
        unpair.append(partner)

    for partner in unpair:
        partner.is_internal_transfer = False
        if partner.category_id is None:
            partner.category_status = "review"

    for tx in txs:
        db.delete(tx)

    account = db.get(Account, batch.account_id)
    restored = False
    if (
        account is not None
        and batch.set_balance is not None
        and account.reference_balance == batch.set_balance
        and account.reference_balance_date == batch.set_balance_date
        and (batch.previous_balance, batch.previous_balance_date)
        != (batch.set_balance, batch.set_balance_date)
    ):
        account.reference_balance = batch.previous_balance
        account.reference_balance_date = batch.previous_balance_date
        restored = True

    db.delete(batch)
    db.flush()
    if unpair:
        apply_rules(db, user_id, [p.id for p in unpair])
    return UndoResult(deleted=len(txs), unpaired=len(unpair), balance_restored=restored)
