"""Create corrections table.

Revision ID: c7f2e43b1d5a
Revises: a3f8c91d0e2b
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c7f2e43b1d5a"
down_revision: Union[str, None] = "a3f8c91d0e2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: if table already exists (e.g., fresh DB created via create_all),
    # skip creation to avoid "table already exists" error
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    if "corrections" not in inspector.get_table_names():
        op.create_table(
            "corrections",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "poliza_id", sa.Integer(),
                sa.ForeignKey("polizas.id", ondelete="CASCADE"),
                nullable=False, index=True
            ),
            sa.Column("field_path", sa.String(), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("corrected_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("corrections")
