"""sync state (phase R)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05 23:00:00+01:00

- sync_state: versión de los datos de esta base, para sincronizar el Mac y el PC por los
  backups de Google Drive (DISENO §15, Fase R). Una sola fila.
- Si la base ya tiene usuarios, se marca como «sesión abierta»: no se sabe si sus datos están
  en alguna copia, así que al abrir se preguntará antes de cambiarlos por los del otro equipo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("version_id", sa.String(length=36), nullable=True),
        sa.Column("lineage", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("session_open", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("device", sa.String(length=20), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_sync_state_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_state")),
    )
    op.execute("INSERT INTO sync_state (id, session_open) SELECT 1, EXISTS (SELECT 1 FROM users)")


def downgrade() -> None:
    op.drop_table("sync_state")
