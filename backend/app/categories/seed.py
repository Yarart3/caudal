"""Categorías y reglas iniciales de cada usuario (DISENO 9.4). El usuario las puede editar.

Si se cambian aquí, solo afecta a los usuarios que se creen después: los que ya existen
conservan las suyas. La migración 0002 lleva una copia congelada de esta lista para los
usuarios que ya existían antes de la Fase 1c.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Rule

# (nombre, tipo, color). Los colores siguen la paleta de la maqueta.
DEFAULT_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("Supermercado", "expense", "#0E6B58"),
    ("Comida fuera", "expense", "#C2581B"),
    ("Ocio y salidas", "expense", "#3555A0"),
    ("Transporte", "expense", "#B08A12"),
    ("Vivienda", "expense", "#7E3F7C"),
    ("Suministros", "expense", "#8A9099"),
    ("Suscripciones", "expense", "#2F8F9D"),
    ("Compras online", "expense", "#B4466B"),
    ("Ropa", "expense", "#6B8E23"),
    ("Salud", "expense", "#D08C60"),
    ("Educación / Material uni", "expense", "#4F5D95"),
    ("Regalos", "expense", "#9C6644"),
    ("Otros", "expense", "#5B616B"),
    ("Nómina", "income", "#0E6B58"),
    ("Bizum recibido", "income", "#2F8F9D"),
    ("Transferencias recibidas", "income", "#3555A0"),
    ("Intereses", "income", "#B08A12"),
    ("Otros ingresos", "income", "#8A9099"),
)

# Prioridad: el número más bajo se mira primero.
PRIORITY_REVIEW = 10  # reglas que dejan por revisar (Bizum): ganan a todas
PRIORITY_USER = 50  # reglas creadas con «¿Aplicar siempre?»: ganan a las del sistema
PRIORITY_SYSTEM = 100

# (texto, categoría o None = dejar por revisar, prioridad)
DEFAULT_RULES: tuple[tuple[str, str | None, int], ...] = (
    # Bizum: puede ser cualquier cosa (una cena, un regalo…). Siempre lo revisa el usuario.
    ("BIZUM ENVIAT", None, PRIORITY_REVIEW),
    ("BIZUM REBUT", None, PRIORITY_REVIEW),
    ("BON AREA", "Supermercado", PRIORITY_SYSTEM),
    ("MERCADONA", "Supermercado", PRIORITY_SYSTEM),
    ("CONSUM", "Supermercado", PRIORITY_SYSTEM),
    ("MC DONALDS", "Comida fuera", PRIORITY_SYSTEM),
    ("BAR", "Comida fuera", PRIORITY_SYSTEM),
    ("AMAZON", "Compras online", PRIORITY_SYSTEM),
    ("WWW.AMAZ", "Compras online", PRIORITY_SYSTEM),
    ("REPSOL", "Transporte", PRIORITY_SYSTEM),
    ("RENFE", "Transporte", PRIORITY_SYSTEM),
    ("SPOTIFY", "Suscripciones", PRIORITY_SYSTEM),
    ("NETFLIX", "Suscripciones", PRIORITY_SYSTEM),
)


def seed_user_defaults(db: Session, user_id: int) -> None:
    """Crea las categorías y reglas iniciales del usuario. Si ya tiene categorías, no hace
    nada (así se puede llamar dos veces sin duplicar). No hace commit."""
    has_categories = db.scalar(
        select(func.count()).select_from(Category).where(Category.user_id == user_id)
    )
    if has_categories:
        return
    categories = {
        name: Category(user_id=user_id, name=name, kind=kind, color=color)
        for name, kind, color in DEFAULT_CATEGORIES
    }
    db.add_all(categories.values())
    db.flush()  # para tener los id de las categorías
    db.add_all(
        Rule(
            user_id=user_id,
            pattern=pattern,
            category_id=categories[name].id if name else None,
            priority=priority,
            created_by="system",
        )
        for pattern, name, priority in DEFAULT_RULES
    )
    db.flush()
