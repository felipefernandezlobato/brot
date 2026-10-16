"""alta propia de clientes con verificacion de email y aprobacion

Revision ID: d4a92c7e1b38
Revises: c3f81b4d6a27
Create Date: 2026-10-16 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a92c7e1b38"
down_revision: Union[str, None] = "c3f81b4d6a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clientes_b2b", sa.Column("email_verificado_at", sa.DateTime(), nullable=True))
    op.add_column("clientes_b2b", sa.Column("aprobado_at", sa.DateTime(), nullable=True))

    # Todas las filas que ya existian son clientes que Felipe dio de alta o
    # acepto en su dia -- Olula entre ellas, que lleva meses pidiendo. Sin
    # este relleno, el dia del deploy se quedarian todas "pendientes" y
    # dejarian de poder pedir, que es exactamente lo contrario de lo que este
    # cambio busca.
    op.execute(
        "UPDATE clientes_b2b SET aprobado_at = CURRENT_TIMESTAMP, "
        "email_verificado_at = CURRENT_TIMESTAMP"
    )


def downgrade() -> None:
    op.drop_column("clientes_b2b", "aprobado_at")
    op.drop_column("clientes_b2b", "email_verificado_at")
