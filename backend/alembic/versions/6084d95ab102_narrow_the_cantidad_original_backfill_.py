"""narrow the cantidad_original backfill to fully depleted lots

Revision ID: 6084d95ab102
Revises: 4dac5d6d7328
Create Date: 2026-08-21 20:38:39.071660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6084d95ab102'
down_revision: Union[str, None] = '4dac5d6d7328'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """The previous migration (4dac5d6d7328) backfilled EVERY existing manual
    lot as cantidad + still-live draws, on the assumption that `cantidad`
    always equals "original minus exactly what ConsumoFifoDetalle says was
    drawn from it". That held for a cleanly-depleted lot (drawn to exactly
    0, e.g. Barra Negra Cocinado's 2026-08-13 lot -- 0 + 12 = 12, correct),
    but a lot that was never fully depleted, or whose consumption/reversal
    history has any pre-existing inconsistency (found on Croissant
    Cocinado's 2026-08-13 lot: still sitting at its full 141 despite two
    live draws recorded against it -- some unrelated, already-existing edit/
    reversal edge case, not something this fix should try to untangle),
    got a fabricated `cantidad + draws` value that's provably wrong given
    `cantidad` was never actually reduced.

    Restricts the reconstruction to the one case it's unambiguously correct
    for: a lot currently sitting at exactly 0 (deducir_congelado_fifo's own
    depletion signature). Everything else reverts to cantidad_original =
    cantidad, i.e. no adjustment -- matching the small, contained,
    pre-existing "old lot's own anchor can read low" issue rather than
    inventing a wrong number.
    """
    op.execute("""
        UPDATE stock_congelado
        SET cantidad_original = cantidad
        WHERE cantidad_original IS NOT NULL
          AND ABS(cantidad) > 0.01
    """)


def downgrade() -> None:
    pass
