"""rename bastones_consumidos -> consumo_padre_declarado

The column held "how much of the parent product was consumed, declared by
hand", but only bastones were ever allowed to use it. It now applies to any
semi or masa parent (see services/stock.admite_consumo_declarado), so the
bastón-specific name was misleading.

A rename, not a new column: the existing values are the same thing and stay.

Revision ID: b8e2d41a9c37
Revises: a7c91f3e24b8
"""
from alembic import op

revision = "b8e2d41a9c37"
down_revision = "a7c91f3e24b8"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "registros_produccion",
        "bastones_consumidos",
        new_column_name="consumo_padre_declarado",
    )


def downgrade():
    op.alter_column(
        "registros_produccion",
        "consumo_padre_declarado",
        new_column_name="bastones_consumidos",
    )
