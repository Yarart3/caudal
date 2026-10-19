"""Emparejar transferencias internas (DISENO, sección 9.3).

Dos movimientos forman una transferencia interna si:
- son del MISMO usuario y de cuentas DISTINTAS,
- tienen importes opuestos (-50,00 y +50,00),
- hay como mucho 3 días entre ellos,
- y algo confirma que es una transferencia: la pista del extracto (Wise dice que el ingreso
  viene de imaginBank y la otra pata es de una cuenta imagin) o un concepto de transferencia
  en alguna de las dos patas (`enviament de dine`, `TRANSFER IMMEDIATA`...).

Sin esa confirmación, un -12,40 con tarjeta y un +12,40 de una devolución en otra cuenta se
tomarían por transferencia. Es mejor dejar alguna sin marcar (el usuario la marca a mano en la
1c) que esconder gastos de verdad.

Solo se buscan parejas para los movimientos que se acaban de importar. Así, si el usuario
desmarca una pareja, no se vuelve a marcar sola en la siguiente importación.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.base import normalize_text
from app.models import Account, Transaction

MAX_DAYS = 3
# Palabras de los conceptos de transferencia que se han visto en los extractos (normalizados).
# Si un banco usa otra, se añade aquí con su test.
TRANSFER_WORDS = ("TRANSFER", "ENVIAMENT", "TRASPAS")


def looks_like_transfer(description: str) -> bool:
    text = normalize_text(description)
    return any(word in text for word in TRANSFER_WORDS)


def mark_internal(tx: Transaction) -> None:
    """Una transferencia interna no es gasto ni ingreso: no necesita categoría."""
    tx.is_internal_transfer = True
    if tx.category_status == "review":
        tx.category_status = "auto"


def match_internal_transfers(
    db: Session, user_id: int, new_ids: list[int], hints: dict[int, str]
) -> set[int]:
    """Busca pareja a cada movimiento recién importado (`new_ids`) entre TODOS los movimientos
    del usuario. Marca las dos patas y devuelve los ids de `new_ids` que han quedado marcados.

    `hints`: id → pista del extracto: el banco (`import_format`) de la cuenta de la que viene
    el dinero. Por ejemplo, "imagin" en un ingreso de Wise que lleva "imaginBank".
    No hace commit: lo hace quien llama.
    """
    if not new_ids:
        return set()
    new_txs = db.scalars(
        select(Transaction)
        .where(Transaction.id.in_(new_ids), Transaction.is_internal_transfer.is_(False))
        .order_by(Transaction.date, Transaction.id)
    ).all()

    marked: set[int] = set()
    for tx in new_txs:
        if tx.amount == 0:
            continue
        counterpart = _find_counterpart(db, user_id, tx, hints.get(tx.id))
        if counterpart is None:
            continue
        mark_internal(tx)
        mark_internal(counterpart)
        db.flush()  # para que la siguiente búsqueda ya no vea la pareja como libre
        marked.add(tx.id)
    return marked


def _find_counterpart(
    db: Session, user_id: int, tx: Transaction, hint: str | None
) -> Transaction | None:
    rows = db.execute(
        select(Transaction, Account.import_format)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,  # nunca entre usuarios distintos
            Transaction.account_id != tx.account_id,
            Transaction.amount == -tx.amount,
            Transaction.is_internal_transfer.is_(False),
            Transaction.date >= tx.date - timedelta(days=MAX_DAYS),
            Transaction.date <= tx.date + timedelta(days=MAX_DAYS),
        )
    ).all()

    own_word = looks_like_transfer(tx.description)
    best: tuple[tuple[bool, bool, int, int], Transaction] | None = None
    for candidate, import_format in rows:
        hint_ok = hint is not None and hint == import_format
        word_ok = own_word or looks_like_transfer(candidate.description)
        if not (hint_ok or word_ok):
            continue
        # Mejor: confirmado por la pista, luego por el concepto, luego el más cercano en fecha
        key = (not hint_ok, not word_ok, abs((candidate.date - tx.date).days), candidate.id)
        if best is None or key < best[0]:
            best = (key, candidate)
    return best[1] if best else None
