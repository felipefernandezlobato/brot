"""ampliar tokens_acceso_cliente.tipo de 10 a 20 caracteres

Revision ID: e5b73f2a91c4
Revises: d4a92c7e1b38
Create Date: 2026-10-16 22:10:00.000000

La columna nacio como String(10) cuando los unicos valores eran "alta" (4) y
"reset" (5). Al anadir "verificacion" (12) el alta de clientes empezo a dar
500 en produccion:

    psycopg2.errors.StringDataRightTruncation
    value too long for type character varying(10)

Los 381 tests pasaban: corren sobre SQLite, que ignora el limite de longitud
de los VARCHAR. Postgres no. Es el unico tipo de fallo que esta suite no
puede ver, y conviene recordarlo al anadir columnas de texto con valores
enumerados.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b73f2a91c4"
down_revision: Union[str, None] = "d4a92c7e1b38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tokens_acceso_cliente",
        "tipo",
        existing_type=sa.String(10),
        type_=sa.String(20),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Solo seguro si no quedan filas con "verificacion"; las hay en cuanto
    # alguien se registre, asi que volver atras pide limpiarlas antes.
    op.alter_column(
        "tokens_acceso_cliente",
        "tipo",
        existing_type=sa.String(20),
        type_=sa.String(10),
        existing_nullable=False,
    )
