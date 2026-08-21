"""add cantidad_original to stock_congelado

Revision ID: 4dac5d6d7328
Revises: 5b6eab3213fc
Create Date: 2026-08-21 20:27:38.448842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dac5d6d7328'
down_revision: Union[str, None] = '5b6eab3213fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stock_congelado', sa.Column('cantidad_original', sa.Float(), nullable=True))

    # Backfill existing lots: `cantidad` has been mutated in place by every
    # FIFO draw taken from it since, so the true original count is what's
    # left plus whatever's still validly (non-reversed) drawn from it. This
    # runs ONCE here, producing a static value new code never re-derives --
    # unlike the reverted 2026-08-21 attempt to compute this live on every
    # read, which re-summed draws that historial_movimientos_acumulado's own
    # ledger loop was *also* about to re-apply, double-subtracting them.
    # `\:rev` (not `:rev`): op.execute() runs raw strings through sqlalchemy.text(),
    # which treats a bare `:name` as a bind parameter -- the backslash escapes it
    # back to a literal colon.
    op.execute(r"""
        UPDATE stock_congelado
        SET cantidad_original = cantidad + (
            SELECT COALESCE(SUM(cfd.cantidad), 0)
            FROM consumo_fifo_detalle cfd
            JOIN movimientos_stock ms ON ms.id = cfd.movimiento_stock_id
            WHERE cfd.stock_congelado_id = stock_congelado.id
              AND (ms.referencia_origen IS NULL OR ms.referencia_origen NOT LIKE '%\:rev')
        )
        WHERE cantidad_original IS NULL
    """)


def downgrade() -> None:
    op.drop_column('stock_congelado', 'cantidad_original')
