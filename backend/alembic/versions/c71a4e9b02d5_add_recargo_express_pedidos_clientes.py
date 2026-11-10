"""add recargo express a pedidos_clientes

El portal pasa a aceptar pedidos con 1 dia de antelacion (antes el minimo era
2), cobrando un recargo del 5% sobre el subtotal de las lineas. Es plata real:
entra en `total`, en el mail al panadero y en la facturacion mensual.

Dos columnas y no una porque el porcentaje hay que congelarlo igual que
`precio_unitario_snapshot`: `RECARGO_EXPRESS_PCT` va a cambiar, y un pedido
viejo tiene que seguir diciendo el porcentaje que se le cobro, no el vigente.
Con solo el monto no se puede reconstruir (habria que dividir por un subtotal
que tampoco esta guardado aparte).

NOT NULL con server_default 0 y no nullable: todo pedido anterior a esta
feature tuvo recargo cero: es un hecho, no un dato desconocido. Eso lo
diferencia de `costo_unitario_snapshot`, que si es nullable justamente porque
"no sabemos el costo" es un estado real alli.

Revision ID: c71a4e9b02d5
Revises: e5b73f2a91c4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c71a4e9b02d5"
down_revision: Union[str, None] = "e5b73f2a91c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pedidos_clientes",
        sa.Column("recargo_pct", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pedidos_clientes",
        sa.Column("recargo_monto", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("pedidos_clientes", "recargo_monto")
    op.drop_column("pedidos_clientes", "recargo_pct")
