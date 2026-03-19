"""Baseline: stamp existing schema, create if fresh.

Revision ID: 001
Revises: None
Create Date: 2026-03-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "polizas" not in existing_tables:
        # Fresh database — create all tables via metadata using a separate engine
        # (Alembic's migration connection wraps DDL in a transaction that needs
        # an independent connection for create_all to be visible immediately)
        from policy_extractor.storage.models import Base
        from sqlalchemy import create_engine
        db_url = op.get_context().config.get_main_option("sqlalchemy.url")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            Base.metadata.create_all(conn)
            conn.commit()
        engine.dispose()
    # If polizas exists: schema already correct, no DDL needed.
    # Alembic stamps this revision after upgrade() returns.


def downgrade() -> None:
    # No downgrade for baseline — would drop all tables
    pass
