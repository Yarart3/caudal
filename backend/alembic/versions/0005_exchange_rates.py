"""exchange rates (phase 3)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04 14:40:00+01:00

- exchange_rates: tipo de cambio a euros por divisa y día (1 unidad = rate EUR), de Yahoo
  (`{DIVISA}EUR=X`). Son datos públicos de mercado: no van por usuario.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("source", sa.String(length=12), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency <> 'EUR'", name=op.f("ck_exchange_rates_currency")),
        sa.CheckConstraint("rate > 0", name=op.f("ck_exchange_rates_rate")),
        sa.PrimaryKeyConstraint("currency", "date", name=op.f("pk_exchange_rates")),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
