"""Foto de los pedidos del portal ANTES de la feature de pedido express.

Red de seguridad pedida por Felipe el 2026-11-07 antes de tocar
`pedidos_clientes`. La migracion de esa feature solo AGREGA dos columnas
(`recargo_pct`, `recargo_monto`), asi que no deberia perderse ningun dato --
pero "no deberia" no es una copia, y CLAUDE.md ya anota un incidente
(13/10/2026) cuyo error de fondo fue justamente no tener snapshot de la TABLA
antes de una escritura en lote.

Guarda tambien la revision de Alembic vigente, que es lo que hace falta para
saber a donde volver con `alembic downgrade`.

Para volver atras:
  - Codigo:    git checkout antes-pedido-express
  - Esquema:   alembic downgrade e5b73f2a91c4
  - Datos:     este JSON (restauracion a mano; no hay script de restore porque
               la migracion es aditiva y no deberia hacer falta nunca)

Solo lee. No escribe nada en la base.
"""

import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

DESTINO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot_pedidos_antes_express.json")

TABLAS = {
    "pedidos_clientes": "select * from pedidos_clientes order by id",
    "lineas_pedido_cliente": "select * from lineas_pedido_cliente order by id",
}


def serializable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def main() -> int:
    db = SessionLocal()
    try:
        datos = {
            "tomado_at": datetime.now().isoformat(),
            "alembic_version": db.execute(text("select version_num from alembic_version")).scalar(),
            "tablas": {},
        }
        for nombre, sql in TABLAS.items():
            filas = db.execute(text(sql)).mappings().all()
            datos["tablas"][nombre] = [
                {k: serializable(v) for k, v in fila.items()} for fila in filas
            ]
            print(f"  {nombre:<24} {len(filas):>4} filas")

        with open(DESTINO, "w") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)

        print(f"\nalembic_version: {datos['alembic_version']}")
        print(f"guardado en: {DESTINO}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
