"""Add financial breakdown columns to polizas table.

Revision ID: 006
Revises: 005
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = "006_financial_breakdown"
down_revision = "c7f2e43b1d5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("polizas")}
    new_cols = [
        ("prima_neta", sa.Numeric(precision=15, scale=2)),
        ("derecho_poliza", sa.Numeric(precision=15, scale=2)),
        ("recargo", sa.Numeric(precision=15, scale=2)),
        ("descuento", sa.Numeric(precision=15, scale=2)),
        ("iva", sa.Numeric(precision=15, scale=2)),
        ("otros_cargos", sa.Numeric(precision=15, scale=2)),
        ("primer_pago", sa.Numeric(precision=15, scale=2)),
        ("pago_subsecuente", sa.Numeric(precision=15, scale=2)),
    ]
    cols_to_add = [(name, typ) for name, typ in new_cols if name not in existing]
    if cols_to_add:
        with op.batch_alter_table("polizas") as batch_op:
            for name, typ in cols_to_add:
                batch_op.add_column(sa.Column(name, typ, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.drop_column("pago_subsecuente")
        batch_op.drop_column("primer_pago")
        batch_op.drop_column("otros_cargos")
        batch_op.drop_column("iva")
        batch_op.drop_column("descuento")
        batch_op.drop_column("recargo")
        batch_op.drop_column("derecho_poliza")
        batch_op.drop_column("prima_neta")
