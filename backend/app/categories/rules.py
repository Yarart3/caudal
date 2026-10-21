"""Motor de reglas: «si el concepto contiene X → categoría Y» (DISENO 9.4).

- Se compara en mayúsculas, sin acentos y con un solo espacio (normalize_text).
- Por **palabras enteras**: `BAR` encaja con «BAR PEPE» o «CAFE-BAR», pero no con
  «BARCELONA» ni «EMBARQUE». Un borde es cualquier cosa que no sea letra o número (espacio,
  punto, asterisco, guion) o el principio o el final del concepto.
- Orden: prioridad (el número más bajo primero); a igual prioridad, el texto más largo (más
  concreto) primero; y después, la regla más antigua.
- Una regla sin categoría deja el movimiento **por revisar** (Bizum) y corta la búsqueda:
  «BIZUM ENVIAT BAR PEPE» no acaba en Comida fuera.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.base import normalize_text
from app.models import Account, Rule, Transaction

# Letra o número (cualquier alfabeto): lo que NO puede haber pegado a una palabra entera
_ALNUM = r"[^\W_]"


@dataclass(frozen=True)
class CompiledRule:
    id: int
    pattern: str  # ya normalizado
    category_id: int | None  # None = dejar por revisar
    priority: int
    regex: re.Pattern[str]


def pattern_regex(pattern: str) -> re.Pattern[str] | None:
    """Expresión regular de un texto de regla, o None si el texto queda vacío.

    El borde solo se exige en los extremos que son letra o número: `WWW.AMAZ` necesita un
    borde después de la Z, pero `*AMZ` no necesita nada antes del asterisco.
    """
    text = normalize_text(pattern)
    if not text:
        return None
    before = f"(?<!{_ALNUM})" if text[0].isalnum() else ""
    after = f"(?!{_ALNUM})" if text[-1].isalnum() else ""
    return re.compile(before + re.escape(text) + after)


def compile_rules(rules: Iterable[Rule]) -> list[CompiledRule]:
    compiled = []
    for rule in rules:
        regex = pattern_regex(rule.pattern)
        if regex is None:
            continue
        compiled.append(
            CompiledRule(
                id=rule.id,
                pattern=normalize_text(rule.pattern),
                category_id=rule.category_id,
                priority=rule.priority,
                regex=regex,
            )
        )
    compiled.sort(key=lambda r: (r.priority, -len(r.pattern), r.id))
    return compiled


def load_rules(db: Session, user_id: int) -> list[CompiledRule]:
    """Las reglas del usuario, ya ordenadas."""
    return compile_rules(db.scalars(select(Rule).where(Rule.user_id == user_id)))


def find_rule(description: str, rules: list[CompiledRule]) -> CompiledRule | None:
    """La primera regla (en orden) que encaja con el concepto, o None."""
    text = normalize_text(description)
    for rule in rules:
        if rule.regex.search(text):
            return rule
    return None


def apply_rules(
    db: Session,
    user_id: int,
    transaction_ids: Iterable[int] | None = None,
    *,
    include_auto: bool = False,
) -> int:
    """Aplica las reglas a los movimientos del usuario y devuelve cuántos han quedado
    categorizados.

    - Por defecto solo toca los **por revisar** (`review`). Nunca toca una categoría puesta a
      mano (`manual`) ni las transferencias internas.
    - `include_auto=True` vuelve a evaluar también los `auto` (botón «Reaplicar reglas» de
      Ajustes, para arreglar lo que categorizó mal una regla ya corregida). Un `auto` que ya
      no encaja con ninguna regla vuelve a `review`.
    - `transaction_ids`: limita a esos movimientos (los recién importados). None = todos los
      del usuario.
    - No hace commit: lo hace quien llama.
    """
    rules = load_rules(db, user_id)
    statuses = ("review", "auto") if include_auto else ("review",)
    if not rules and not include_auto:
        return 0
    query = (
        select(Transaction)
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.category_status.in_(statuses),
            Transaction.is_internal_transfer.is_(False),
        )
    )
    if transaction_ids is not None:
        ids = list(transaction_ids)
        if not ids:
            return 0
        query = query.where(Transaction.id.in_(ids))

    categorized = 0
    for tx in db.scalars(query):
        rule = find_rule(tx.description, rules)
        if rule is None or rule.category_id is None:
            if tx.category_status == "auto":  # solo pasa con include_auto
                tx.category_id = None
                tx.category_status = "review"
            continue
        tx.category_id = rule.category_id
        tx.category_status = "auto"
        categorized += 1
    db.flush()
    return categorized
