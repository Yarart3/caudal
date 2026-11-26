"""imports, to undo a statement import (phase 5)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-26 13:00:00+01:00

- imports: cada importación de extracto que trajo algún movimiento nuevo, con las fechas de lo
  importado y el saldo de referencia de la cuenta antes y después (para deshacerla).
- transactions.import_id: de qué importación viene cada movimiento. Los que ya existían antes
  de esta migración, los apuntados a mano y los repetidos no llevan ninguna.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("first_date", sa.Date(), nullable=True),
        sa.Column("last_date", sa.Date(), nullable=True),
        sa.Column("new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("previous_balance", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("previous_balance_date", sa.Date(), nullable=True),
        sa.Column("set_balance", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("set_balance_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_imports_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imports")),
    )
    op.create_index(op.f("ix_imports_account_id"), "imports", ["account_id"], unique=False)
    op.add_column("transactions", sa.Column("import_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_transactions_import_id_imports"),
        "transactions",
        "imports",
        ["import_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_transactions_import_id"), "transactions", ["import_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_import_id"), table_name="transactions")
    op.drop_constraint(
        op.f("fk_transactions_import_id_imports"), "transactions", type_="foreignkey"
    )
    op.drop_column("transactions", "import_id")
    op.drop_index(op.f("ix_imports_account_id"), table_name="imports")
    op.drop_table("imports")
