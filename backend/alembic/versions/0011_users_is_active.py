"""users.is_active, to deactivate a user from settings (phase 4)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-26 20:00:00+01:00

- users.is_active: un usuario desactivado no sale en «¿Quién entra?» ni puede entrar, pero sus
  datos se quedan. Los que ya existen quedan activos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
