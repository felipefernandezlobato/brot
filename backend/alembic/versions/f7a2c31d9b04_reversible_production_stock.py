"""reversible production stock effects

Links every stock movement to an editable RegistroProduccion and records the
per-lot breakdown of FIFO consumptions so edits can be reversed exactly.

Revision ID: f7a2c31d9b04
Revises: b1e4f5a2c890
Create Date: 2026-08-17 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a2c31d9b04'
down_revision: Union[str, None] = 'b1e4f5a2c890'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Plain integer references, no DB-level FK — SQLite cannot ALTER in a constraint,
    # and this matches how MovimientoStock.referencia_producto_id already works here.
    # Referential cleanup is done in code (see services/produccion_registro.py).
    op.add_column(
        "registros_produccion",
        sa.Column("producto_congelado_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "registros_produccion",
        sa.Column("bastones_consumidos", sa.Float(), nullable=True),
    )
    op.add_column(
        "stock_congelado",
        sa.Column("registro_produccion_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_stock_congelado_registro_produccion_id",
        "stock_congelado",
        ["registro_produccion_id"],
    )

    op.create_table(
        "consumo_fifo_detalle",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movimiento_stock_id", sa.Integer(), nullable=False),
        sa.Column("stock_congelado_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["movimiento_stock_id"], ["movimientos_stock.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stock_congelado_id"], ["stock_congelado.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_consumo_fifo_detalle_movimiento_stock_id",
        "consumo_fifo_detalle",
        ["movimiento_stock_id"],
    )

    # One record per task per day, enforced by the DB. upsert_registro reads then
    # writes; without this, two devices saving the same task at once could each
    # insert a row and each apply the deduction. CREATE UNIQUE INDEX works on both
    # SQLite and Postgres without an ALTER. Verified no duplicates exist first.
    op.create_index(
        "uq_registro_tarea_fecha",
        "registros_produccion",
        ["tarea_id", "fecha"],
        unique=True,
        sqlite_where=sa.text("tarea_id IS NOT NULL"),
        postgresql_where=sa.text("tarea_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_registro_tarea_fecha", table_name="registros_produccion")
    op.drop_index("ix_consumo_fifo_detalle_movimiento_stock_id", table_name="consumo_fifo_detalle")
    op.drop_table("consumo_fifo_detalle")

    op.drop_index("ix_stock_congelado_registro_produccion_id", table_name="stock_congelado")
    with op.batch_alter_table("stock_congelado") as batch:
        batch.drop_column("registro_produccion_id")

    with op.batch_alter_table("registros_produccion") as batch:
        batch.drop_column("bastones_consumidos")
        batch.drop_column("producto_congelado_id")
