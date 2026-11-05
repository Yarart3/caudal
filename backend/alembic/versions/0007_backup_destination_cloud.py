"""backup destination cloud (phase R)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-05 22:00:00+01:00

- backup_log.destination: 'onedrive' pasa a 'cloud'. El destino en la nube es ahora Google Drive
  y en el código tiene un nombre neutro, para no depender del proveedor (DISENO §10).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_backup_log_destination"), "backup_log", type_="check")
    op.execute("UPDATE backup_log SET destination = 'cloud' WHERE destination = 'onedrive'")
    op.create_check_constraint(
        op.f("ck_backup_log_destination"), "backup_log", "destination IN ('usb', 'cloud')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_backup_log_destination"), "backup_log", type_="check")
    op.execute("UPDATE backup_log SET destination = 'onedrive' WHERE destination = 'cloud'")
    op.create_check_constraint(
        op.f("ck_backup_log_destination"), "backup_log", "destination IN ('usb', 'onedrive')"
    )
