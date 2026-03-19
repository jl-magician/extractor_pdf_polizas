"""Add evaluation columns to polizas.

Revision ID: 002
Revises: 001
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: if columns already exist (e.g., fresh DB created via create_all in 001),
    # skip adding them to avoid "duplicate column name" error
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_cols = {c["name"] for c in inspector.get_columns("polizas")}

    with op.batch_alter_table("polizas") as batch_op:
        if "evaluation_score" not in existing_cols:
            batch_op.add_column(sa.Column("evaluation_score", sa.Float(), nullable=True))
        if "evaluation_json" not in existing_cols:
            batch_op.add_column(sa.Column("evaluation_json", sa.Text(), nullable=True))
        if "evaluated_at" not in existing_cols:
            batch_op.add_column(sa.Column("evaluated_at", sa.DateTime(), nullable=True))
        if "evaluated_model_id" not in existing_cols:
            batch_op.add_column(sa.Column("evaluated_model_id", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.drop_column("evaluated_model_id")
        batch_op.drop_column("evaluated_at")
        batch_op.drop_column("evaluation_json")
        batch_op.drop_column("evaluation_score")
