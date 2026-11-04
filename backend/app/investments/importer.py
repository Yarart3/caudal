"""Importar la plantilla de inversiones (DISENO §7.4) en una cuenta de inversión del usuario.

Dos pasos con la misma llamada:
- Vista previa (`confirm=False`): se valida todo, también que ninguna venta se quede sin
  participaciones, y no se guarda nada.
- Confirmar (`confirm=True`): entra todo o nada. Si hay una sola fila con error, no se guarda.

El `identificador` de cada fila tiene que ser el ISIN, el símbolo de Yahoo o el ticker de un
producto que el usuario ya tenga. Las filas que ya se importaron antes (misma huella) se
saltan; dos filas idénticas en el mismo archivo entran las dos (la huella lleva cuál es de
ellas). Las operaciones escritas a mano no tienen huella: si se importa un historial que ya se
había apuntado a mano, saldrá repetido.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from hashlib import sha256

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.base import RowError
from app.importers.plantilla_inversiones import TemplateOperation, read_template
from app.investments.holdings import first_shortfall, format_shares
from app.investments.operations import OperationCreate, first_error
from app.models import Account, InvestmentOperation, Product, User

MAX_PREVIEW = 200


@dataclass(frozen=True)
class PreviewRow:
    row: int
    date: date
    product_id: int
    product_name: str
    kind: str
    shares: Decimal
    amount_eur: Decimal
    fee_eur: Decimal | None


@dataclass
class ImportResult:
    read: int
    new: int
    duplicates: int
    saved: bool
    errors: list[RowError] = field(default_factory=list)
    operations: list[PreviewRow] = field(default_factory=list)  # las nuevas (hasta 200)


def _products_by_identifier(db: Session, user: User) -> dict[str, Product]:
    """ISIN, símbolo o ticker → producto. Si chocan, gana el ISIN y luego el símbolo."""
    lookup: dict[str, Product] = {}
    products = db.scalars(select(Product).where(Product.user_id == user.id)).all()
    for attribute in ("ticker", "source_id", "isin"):
        for product in products:
            value = getattr(product, attribute)
            if value:
                lookup[value.strip().upper()] = product
    return lookup


def _fingerprint(account_id: int, product_id: int, op: TemplateOperation, nth: int) -> str:
    parts = [
        str(account_id),
        "plantilla",
        op.date.isoformat(),
        op.kind,
        str(product_id),
        format(op.shares, "f"),
        str(op.amount_eur),
        "" if op.fee_eur is None else str(op.fee_eur),
        str(nth),  # 1.ª, 2.ª… fila idéntica del archivo
    ]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()


def import_template(
    db: Session, user: User, account: Account, data: bytes, confirm: bool
) -> ImportResult:
    """Lanza ImportFormatError si el archivo entero no vale (no es la plantilla, está vacío…)."""
    parsed = read_template(data)
    errors = list(parsed.errors)
    lookup = _products_by_identifier(db, user)
    seen: Counter = Counter()
    candidates: list[tuple[TemplateOperation, Product, OperationCreate, str]] = []
    for op in parsed.operations:
        product = lookup.get(op.identifier)
        if product is None:
            errors.append(
                RowError(
                    op.row,
                    "identificador",
                    op.identifier,
                    f"Fila {op.row}: no tienes ningún producto «{op.identifier}»: "
                    "créalo antes en Productos",
                )
            )
            continue
        try:
            valid = OperationCreate(
                account_id=account.id,
                product_id=product.id,
                date=op.date,
                kind=op.kind,
                shares=op.shares,
                amount_eur=op.amount_eur,
                fee_eur=op.fee_eur,
            )
        except ValidationError as error:
            errors.append(RowError(op.row, "", "", f"Fila {op.row}: {first_error(error)}"))
            continue
        key = (op.date, op.kind, product.id, op.shares, op.amount_eur, op.fee_eur)
        seen[key] += 1
        candidates.append((op, product, valid, _fingerprint(account.id, product.id, op, seen[key])))

    existing = set(
        db.scalars(
            select(InvestmentOperation.fingerprint).where(
                InvestmentOperation.account_id == account.id,
                InvestmentOperation.fingerprint.in_([c[3] for c in candidates]),
            )
        )
    )
    new = [c for c in candidates if c[3] not in existing]
    result = ImportResult(
        read=len(parsed.operations) + len(parsed.errors),
        new=len(new),
        duplicates=len(candidates) - len(new),
        saved=False,
        errors=errors,
        operations=[
            PreviewRow(
                op.row,
                valid.date,
                product.id,
                product.name,
                valid.kind,
                valid.shares,
                valid.amount_eur,
                valid.fee_eur,
            )
            for op, product, valid, _ in new[:MAX_PREVIEW]
        ],
    )
    if errors or not new:
        return result

    for _, _, valid, fp in new:
        db.add(InvestmentOperation(**valid.model_dump(), fingerprint=fp))
    db.flush()
    for product in sorted({c[1] for c in new}, key=lambda p: p.id):
        shortfall = first_shortfall(db, account.id, product.id)
        if shortfall is not None:
            result.errors.append(
                RowError(
                    0,
                    "unidades",
                    "",
                    f"Con este archivo venderías más «{product.name}» del que tienes en "
                    f"{account.name}: el {shortfall.date:%d/%m/%Y} quedarían "
                    f"{format_shares(shortfall.shares)}",
                )
            )
    if result.errors or not confirm:
        db.rollback()
        return result
    db.commit()
    result.saved = True
    return result
