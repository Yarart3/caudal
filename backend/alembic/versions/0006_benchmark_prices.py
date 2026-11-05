"""benchmark prices (phase 3)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05 10:30:00+01:00

- benchmark_prices: cierres diarios de los índices de la comparativa (MSCI World, S&P 500 y
  monetario del euro). Datos públicos de mercado: no van por usuario.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "benchmark_prices",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=12), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("price > 0", name=op.f("ck_benchmark_prices_price")),
        sa.PrimaryKeyConstraint("symbol", "date", name=op.f("pk_benchmark_prices")),
    )


def downgrade() -> None:
    op.drop_table("benchmark_prices")
