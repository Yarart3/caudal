"""budgets and net worth goal (phase 2)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30 20:30:00+01:00

- categories.monthly_budget: presupuesto mensual fijo de la categoría (DISENO 3.2 y 8.4).
  Vacío = sin presupuesto. Solo en categorías de gasto y siempre mayor que cero.
- goals: objetivo de patrimonio, uno por usuario (DISENO 3.1 y 8.4). Se adelanta de la Fase 3.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("monthly_budget", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_categories_monthly_budget"),
        "categories",
        "monthly_budget IS NULL OR (monthly_budget > 0 AND kind = 'expense')",
    )
    op.create_table(
        "goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("target_amount > 0", name=op.f("ck_goals_target_amount")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_goals_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goals")),
        sa.UniqueConstraint("user_id", name=op.f("uq_goals_user_id")),
    )


def downgrade() -> None:
    op.drop_table("goals")
    op.drop_constraint(op.f("ck_categories_monthly_budget"), "categories", type_="check")
    op.drop_column("categories", "monthly_budget")
