"""Add validation_warnings column to polizas.

Revision ID: 003
Revises: 002
Create Date: 2026-03-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: if column already exists (e.g., fresh DB created via create_all),
    # skip adding it to avoid "duplicate column name" error
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("polizas")}

    with op.batch_alter_table("polizas") as batch_op:
        if "validation_warnings" not in existing_cols:
            batch_op.add_column(sa.Column("validation_warnings", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.drop_column("validation_warnings")
