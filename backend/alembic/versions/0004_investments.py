"""investments (phase 3)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03 22:10:00+01:00

- products, investment_operations, prices y manual_valuations (DISENO 7 y 8.4).
- Tipo de producto nuevo `commodity` (oro y otras materias primas: ETC), que DISENO no tenía.
- prices.fetched_at: cuándo se descargó el precio, para avisar de precios desactualizados.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column("ticker", sa.String(length=20), nullable=True),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("price_source", sa.String(length=12), nullable=False),
        sa.Column("source_id", sa.String(length=60), nullable=True),
        sa.Column("ter", sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column("long_term", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('etf', 'stock', 'fund', 'crypto', 'pension', 'commodity', 'other')",
            name=op.f("ck_products_kind"),
        ),
        sa.CheckConstraint(
            "price_source IN ('yahoo', 'morningstar', 'coingecko', 'manual')",
            name=op.f("ck_products_price_source"),
        ),
        sa.CheckConstraint("ter IS NULL OR (ter >= 0 AND ter < 1)", name=op.f("ck_products_ter")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_products_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("user_id", "isin", name=op.f("uq_products_user_id_isin")),
    )
    op.create_index(op.f("ix_products_user_id"), "products", ["user_id"], unique=False)
    op.create_table(
        "investment_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("shares", sa.Numeric(precision=18, scale=8), server_default="0", nullable=False),
        sa.Column("amount_eur", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fee_eur", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('buy', 'sell', 'dividend', 'fee')", name=op.f("ck_investment_operations_kind")
        ),
        sa.CheckConstraint(
            "kind NOT IN ('buy', 'sell') OR shares > 0",
            name=op.f("ck_investment_operations_shares_buy_sell"),
        ),
        sa.CheckConstraint("amount_eur > 0", name=op.f("ck_investment_operations_amount_eur")),
        sa.CheckConstraint(
            "fee_eur IS NULL OR fee_eur >= 0", name=op.f("ck_investment_operations_fee_eur")
        ),
        sa.CheckConstraint("shares >= 0", name=op.f("ck_investment_operations_shares")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_investment_operations_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_investment_operations_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investment_operations")),
        sa.UniqueConstraint(
            "account_id",
            "fingerprint",
            name=op.f("uq_investment_operations_account_id_fingerprint"),
        ),
    )
    op.create_index(
        "ix_investment_operations_account_id_date",
        "investment_operations",
        ["account_id", "date"],
        unique=False,
    )
    op.create_table(
        "manual_valuations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value_eur", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("contributed_eur", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "contributed_eur IS NULL OR contributed_eur >= 0",
            name=op.f("ck_manual_valuations_contributed_eur"),
        ),
        sa.CheckConstraint("value_eur >= 0", name=op.f("ck_manual_valuations_value_eur")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_manual_valuations_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_manual_valuations")),
        sa.UniqueConstraint(
            "product_id", "date", name=op.f("uq_manual_valuations_product_id_date")
        ),
    )
    op.create_index(
        op.f("ix_manual_valuations_product_id"), "manual_valuations", ["product_id"], unique=False
    )
    op.create_table(
        "prices",
        sa.Column("product_id", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("price > 0", name=op.f("ck_prices_price")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_prices_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_id", "date", name=op.f("pk_prices")),
    )


def downgrade() -> None:
    op.drop_table("prices")
    op.drop_index(op.f("ix_manual_valuations_product_id"), table_name="manual_valuations")
    op.drop_table("manual_valuations")
    op.drop_index("ix_investment_operations_account_id_date", table_name="investment_operations")
    op.drop_table("investment_operations")
    op.drop_index(op.f("ix_products_user_id"), table_name="products")
    op.drop_table("products")
