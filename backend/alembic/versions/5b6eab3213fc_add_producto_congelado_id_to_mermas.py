"""add producto_congelado_id to mermas

Revision ID: 5b6eab3213fc
Revises: f7a2c31d9b04
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b6eab3213fc'
down_revision: Union[str, None] = 'f7a2c31d9b04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mermas', sa.Column('producto_congelado_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'mermas', 'productos_congelados', ['producto_congelado_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'mermas', type_='foreignkey')
    op.drop_column('mermas', 'producto_congelado_id')
