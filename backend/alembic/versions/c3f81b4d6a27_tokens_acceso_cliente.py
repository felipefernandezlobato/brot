"""tokens de acceso de cliente (alta por invitacion y reset de contrasena)

Revision ID: c3f81b4d6a27
Revises: b8e2d41a9c37
Create Date: 2026-10-16 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f81b4d6a27"
down_revision: Union[str, None] = "b8e2d41a9c37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tokens_acceso_cliente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cliente_b2b_id", sa.Integer(), nullable=False),
        # Se guarda el sha256 del token, nunca el token. 64 chars hex.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("expira_at", sa.DateTime(), nullable=False),
        sa.Column("usado_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["cliente_b2b_id"], ["clientes_b2b.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unico: el lookup del token al canjearlo es por este campo y tiene que ser
    # exacto y rapido. Unique ademas impide colisiones de tokens.
    op.create_index(
        "ix_tokens_acceso_cliente_token_hash",
        "tokens_acceso_cliente",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_tokens_acceso_cliente_cliente_b2b_id",
        "tokens_acceso_cliente",
        ["cliente_b2b_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tokens_acceso_cliente_cliente_b2b_id", table_name="tokens_acceso_cliente")
    op.drop_index("ix_tokens_acceso_cliente_token_hash", table_name="tokens_acceso_cliente")
    op.drop_table("tokens_acceso_cliente")
