"""add costo_unitario_snapshot to sale lines

Freezes the cost of goods at delivery time, so a closed month's margin stops
moving when ingredient prices change afterwards. Nullable: a line whose recipe
can't produce a real cost stores NULL rather than 0, so the gap is visible
instead of reading as a 100% margin.

Historical lines stay NULL on purpose -- for those the monthly endpoint
reconstructs the cost from HistorialPrecio at the delivery date
(services/costes.precio_compra_en).

Revision ID: a7c91f3e24b8
Revises: 6084d95ab102
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c91f3e24b8"
down_revision = "6084d95ab102"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "lineas_entrega_b2b",
        sa.Column("costo_unitario_snapshot", sa.Float(), nullable=True),
    )
    op.add_column(
        "lineas_pedido_cliente",
        sa.Column("costo_unitario_snapshot", sa.Float(), nullable=True),
    )


def downgrade():
    op.drop_column("lineas_pedido_cliente", "costo_unitario_snapshot")
    op.drop_column("lineas_entrega_b2b", "costo_unitario_snapshot")
