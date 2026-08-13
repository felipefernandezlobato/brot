"""unify clientes B2B with auth fields

Revision ID: b1e4f5a2c890
Revises: a73e99ac1304
Create Date: 2026-08-13 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1e4f5a2c890"
down_revision: Union[str, None] = "a73e99ac1304"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add auth fields to clientes_b2b
    op.add_column("clientes_b2b", sa.Column("email", sa.String(200), nullable=True))
    op.add_column("clientes_b2b", sa.Column("password_hash", sa.String(200), nullable=True))
    op.add_column("clientes_b2b", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.create_unique_constraint("uq_clientes_b2b_email", "clientes_b2b", ["email"])

    # Change FK on pedidos_clientes: clientes -> clientes_b2b
    op.drop_constraint("pedidos_clientes_cliente_id_fkey", "pedidos_clientes", type_="foreignkey")
    op.create_foreign_key(
        "pedidos_clientes_cliente_id_fkey",
        "pedidos_clientes",
        "clientes_b2b",
        ["cliente_id"],
        ["id"],
    )

    # Change FK on pedidos_recurrentes: clientes -> clientes_b2b
    op.drop_constraint("pedidos_recurrentes_cliente_id_fkey", "pedidos_recurrentes", type_="foreignkey")
    op.create_foreign_key(
        "pedidos_recurrentes_cliente_id_fkey",
        "pedidos_recurrentes",
        "clientes_b2b",
        ["cliente_id"],
        ["id"],
    )


def downgrade() -> None:
    # Revert FK on pedidos_recurrentes
    op.drop_constraint("pedidos_recurrentes_cliente_id_fkey", "pedidos_recurrentes", type_="foreignkey")
    op.create_foreign_key(
        "pedidos_recurrentes_cliente_id_fkey",
        "pedidos_recurrentes",
        "clientes",
        ["cliente_id"],
        ["id"],
    )

    # Revert FK on pedidos_clientes
    op.drop_constraint("pedidos_clientes_cliente_id_fkey", "pedidos_clientes", type_="foreignkey")
    op.create_foreign_key(
        "pedidos_clientes_cliente_id_fkey",
        "pedidos_clientes",
        "clientes",
        ["cliente_id"],
        ["id"],
    )

    # Remove auth fields from clientes_b2b
    op.drop_constraint("uq_clientes_b2b_email", "clientes_b2b", type_="unique")
    op.drop_column("clientes_b2b", "created_at")
    op.drop_column("clientes_b2b", "password_hash")
    op.drop_column("clientes_b2b", "email")
