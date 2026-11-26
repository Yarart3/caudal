"""transaction notes and tags (phase 5)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-26 12:00:00+01:00

- transactions.note: nota libre del usuario (opcional, hasta 500 caracteres).
- transactions.tags: etiquetas del usuario («viaje japón», «regalos navidad»…), como lista de
  textos. Un índice GIN permite filtrar por etiqueta sin recorrer toda la tabla.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("note", sa.Text(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(length=30)),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_transactions_tags", "transactions", ["tags"], unique=False, postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_tags", table_name="transactions", postgresql_using="gin")
    op.drop_column("transactions", "tags")
    op.drop_column("transactions", "note")
