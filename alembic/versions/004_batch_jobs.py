"""Create batch_jobs table.

Revision ID: a3f8c91d0e2b
Revises: 003
Create Date: 2026-03-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3f8c91d0e2b"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: if table already exists (e.g., fresh DB created via create_all),
    # skip creation to avoid "table already exists" error
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    if "batch_jobs" not in inspector.get_table_names():
        op.create_table(
            "batch_jobs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("batch_name", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("results_json", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("batch_jobs")
