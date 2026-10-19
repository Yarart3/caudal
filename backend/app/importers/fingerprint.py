"""Huella anti-duplicados de cada movimiento importado (DISENO, sección 9.2).

Siempre es un SHA-256 en hexadecimal (64 caracteres, lo que cabe en transactions.fingerprint):
- Wise:   sha256(cuenta | ID de la transacción)
- imagin: sha256(cuenta | fecha | importe | concepto normalizado | saldo del extracto)
  El saldo es lo que distingue dos compras iguales el mismo día.

Como la huella incluye la cuenta, el mismo movimiento en dos cuentas nunca choca (además de que
la restricción única ya es por (account_id, fingerprint)).
"""

from hashlib import sha256

from app.importers.base import ParsedTransaction, normalize_text


def fingerprint(account_id: int, tx: ParsedTransaction) -> str:
    if tx.external_id is not None:
        parts = [str(account_id), "id", tx.external_id]
    elif tx.balance is not None:
        parts = [
            str(account_id),
            tx.date.isoformat(),
            str(tx.amount),  # Decimal con 2 decimales: "-2.45"
            normalize_text(tx.description),
            str(tx.balance),
        ]
    else:
        # Ningún importador actual llega aquí: imagin siempre trae saldo y Wise siempre trae ID
        raise ValueError("No se puede calcular la huella: falta el ID y el saldo")
    return sha256("|".join(parts).encode("utf-8")).hexdigest()
