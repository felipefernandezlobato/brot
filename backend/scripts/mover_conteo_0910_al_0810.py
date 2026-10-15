"""One-off: re-date the 2026-10-09 physical count to 2026-10-08.

WHY
---
The count was taken on the 8th and loaded on the 9th (Felipe, 2026-10-15).
Both stock screens date a count by when it was entered, so every one of those
69 rows carries the wrong day. That matters beyond cosmetics: the calculado
anchor sits on the count's date and re-anchors from the day AFTER it, so with
the count on the 9th all of the 9th's production and deliveries are treated as
having happened BEFORE the count instead of after it.

WHAT IT MOVES
-------------
47 manual `StockCongelado` counts + 22 manual `InventarioRegistro` counts.
Automatic rows of that day (production lots, "Consumo automatico:", pedido
receptions) are deliberately left where they are -- they really did happen on
the 9th, and both endpoints reject them anyway.

HOW
---
Through the routers' own `update_stock_congelado` / `update_inventario`, same
as the 2026-09-29 repricing went through `update_receta`. That keeps every
guard: the "this is not a manual count" and "this lot came from a production"
rejections, and `exclude_unset` so ONLY the date is written.

Sending just the date matters: `update_stock_congelado` sets
`cantidad_original = cantidad` whenever `cantidad` is present in the payload,
and several of these lots have already been drawn down by FIFO (Barra Blanca
Cocinado is at 24 against a counted 32). Passing the quantity back in would
silently rewrite what the count said -- the exact thing `cantidad_original`
exists to protect.

CHECKED BEFORE WRITING
----------------------
* Nothing manual already sits on 2026-10-08 (only 3 production lots and 2
  automatic materia-prima rows), so no count collides.
* `get_saldo_materia_prima` picks the latest row by `(fecha_registro, id)`;
  moving these 22 back a day changes which row that is for **0 of 22**
  ingredients, so the write path everything else chains off is untouched.
* Congelado saldos don't move at all: `is_active` is what drives them and this
  only writes a date.

    DATABASE_URL=... python scripts/mover_conteo_0910_al_0810.py           # dry run
    DATABASE_URL=... python scripts/mover_conteo_0910_al_0810.py --apply
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Ingrediente,
    InventarioRegistro,
    ProductoCongelado,
    StockCongelado,
    User,
)
from app.routers.congelados import update_stock_congelado  # noqa: E402
from app.routers.inventario import update_inventario  # noqa: E402
from app.schemas import InventarioRegistroUpdate, StockCongeladoUpdate  # noqa: E402
from app.services.stock import es_conteo_manual  # noqa: E402

DESDE = date(2026, 10, 9)
HASTA = date(2026, 10, 8)


def a_mover(db):
    congelados = [
        l
        for l in db.query(StockCongelado)
        .filter(StockCongelado.fecha_entrada == DESDE)
        .order_by(StockCongelado.id)
        .all()
        if l.registro_produccion_id is None and es_conteo_manual("congelado", l.notas)
    ]
    materia = [
        r
        for r in db.query(InventarioRegistro)
        .filter(InventarioRegistro.fecha_registro == DESDE)
        .order_by(InventarioRegistro.id)
        .all()
        if es_conteo_manual("materia_prima", r.notas)
    ]
    return congelados, materia


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print("  no hay usuario admin para atribuir la edicion.")
            return

        congelados, materia = a_mover(db)
        pc = {p.id: p.nombre for p in db.query(ProductoCongelado).all()}
        ing = {i.id: i.nombre for i in db.query(Ingrediente).all()}

        print(f"{'APLICANDO' if aplicar else 'DRY RUN'} -- {DESDE} -> {HASTA}")
        print(f"\n  CONGELADO: {len(congelados)} conteos")
        for l in congelados:
            print(f"    id {l.id:>5} {pc.get(l.producto_congelado_id, '?')[:30]:32} "
                  f"contado {l.cantidad_original if l.cantidad_original is not None else l.cantidad:>8.2f}")
        print(f"\n  MATERIA PRIMA: {len(materia)} conteos")
        for r in materia:
            print(f"    id {r.id:>5} {ing.get(r.ingrediente_id, '?')[:30]:32} "
                  f"contado {r.cantidad:>9.3f} {r.unidad}")

        if not aplicar:
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        # Snapshot de lo que se toca, por si hay que volver atras.
        destino = Path("/tmp/snapshot_fechas_conteo_0910.txt")
        destino.write_text(
            "\n".join(
                [f"congelado {l.id} {l.fecha_entrada}" for l in congelados]
                + [f"materia_prima {r.id} {r.fecha_registro}" for r in materia]
            )
        )
        print(f"\n  snapshot de fechas previas en {destino}")

        for l in congelados:
            update_stock_congelado(
                l.id, StockCongeladoUpdate(fecha_entrada=HASTA), user=admin, db=db
            )
        for r in materia:
            update_inventario(
                r.id, InventarioRegistroUpdate(fecha_registro=HASTA), user=admin, db=db
            )

        quedan_c, quedan_m = a_mover(db)
        movidos_c = db.query(StockCongelado).filter(StockCongelado.fecha_entrada == HASTA).count()
        print(f"\n  listo. conteos que siguen en {DESDE}: "
              f"congelado {len(quedan_c)}, materia prima {len(quedan_m)}")
        print(f"  lotes de congelado ahora en {HASTA}: {movidos_c}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
