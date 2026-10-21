"""rules without category (review) and default categories for existing users

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 12:00:00+02:00

- rules.category_id pasa a ser opcional: una regla sin categoría deja el movimiento por
  revisar (BIZUM ENVIAT / BIZUM REBUT, DISENO 9.4).
- Crea las categorías y reglas iniciales de los usuarios que ya existían (los del asistente
  de la Fase 1a), que se crearon sin ellas. Los usuarios nuevos las reciben al crearse
  (app/categories/seed.py).

La lista va copiada aquí a propósito: una migración tiene que hacer siempre lo mismo, aunque
app/categories/seed.py cambie más adelante.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = (
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
RULES = (
    ("BIZUM ENVIAT", None, 10),
    ("BIZUM REBUT", None, 10),
    ("BON AREA", "Supermercado", 100),
    ("MERCADONA", "Supermercado", 100),
    ("CONSUM", "Supermercado", 100),
    ("MC DONALDS", "Comida fuera", 100),
    ("BAR", "Comida fuera", 100),
    ("AMAZON", "Compras online", 100),
    ("WWW.AMAZ", "Compras online", 100),
    ("REPSOL", "Transporte", 100),
    ("RENFE", "Transporte", 100),
    ("SPOTIFY", "Suscripciones", 100),
    ("NETFLIX", "Suscripciones", 100),
)

users = sa.table("users", sa.column("id", sa.Integer))
categories = sa.table(
    "categories",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("kind", sa.String),
    sa.column("color", sa.String),
)
rules = sa.table(
    "rules",
    sa.column("user_id", sa.Integer),
    sa.column("pattern", sa.String),
    sa.column("category_id", sa.Integer),
    sa.column("priority", sa.Integer),
    sa.column("created_by", sa.String),
)


def upgrade() -> None:
    op.alter_column("rules", "category_id", existing_type=sa.Integer(), nullable=True)

    conn = op.get_bind()
    with_categories = sa.select(categories.c.user_id)
    user_ids = conn.scalars(sa.select(users.c.id).where(users.c.id.not_in(with_categories)))
    for user_id in user_ids:
        inserted = conn.execute(
            categories.insert().returning(categories.c.id, categories.c.name),
            [{"user_id": user_id, "name": n, "kind": k, "color": c} for n, k, c in CATEGORIES],
        )
        ids = {row.name: row.id for row in inserted}
        conn.execute(
            rules.insert(),
            [
                {
                    "user_id": user_id,
                    "pattern": pattern,
                    "category_id": ids[name] if name else None,
                    "priority": priority,
                    "created_by": "system",
                }
                for pattern, name, priority in RULES
            ],
        )


def downgrade() -> None:
    # Las reglas sin categoría no caben en el esquema anterior. Las categorías y el resto de
    # reglas se quedan: son datos del usuario y el esquema 0001 los admite.
    op.execute("DELETE FROM rules WHERE category_id IS NULL")
    op.alter_column("rules", "category_id", existing_type=sa.Integer(), nullable=False)
