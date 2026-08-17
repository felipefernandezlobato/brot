"""One-off: recompute the two masa productions inflated by the porciones_por_lote bug.

For a masa recipe (Masa de Croissant, porciones_por_lote=9; Masa de Medialuna,
porciones_por_lote=6), `u` of stock IS a lote -- 1 lote of dough is 1 unit on
the shelf, and only turns into 9 (or 6) bastones once combined with butter and
laminated downstream. `cantidad_en_porciones()` used to multiply what the
operator entered by porciones_por_lote before handing it to producir_producto,
which fixed ingredient deduction by accident but also inflated the masa's own
StockCongelado quantity by the same factor (1.5 recorded as 13.5, 1 recorded
as 6). Fixed in produccion_registro.py / stock.py -- this script re-runs the
two real production records written under the old logic so their stock
reflects lotes, not (lotes * porciones_por_lote).

Ingredient consumption is untouched by the fix and nets to the same values
before and after -- only the masa's own StockCongelado quantity changes.

Uses the existing revert+reapply machinery (same one corregir_produccion_agosto.py
used), which already knows how to handle "the batch was partly consumed
downstream by a later bastón run": it books the shortfall as a negative
adjustment lot instead of pretending it can un-consume flour that's already
gone.

    DATABASE_URL=... python scripts/corregir_lotes_masa.py           # dry run
    DATABASE_URL=... python scripts/corregir_lotes_masa.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, ProductoCongelado, Receta, RegistroProduccion  # noqa: E402
from app.services.produccion_registro import aplicar_efectos, revertir_efectos  # noqa: E402
from app.services.stock import get_saldo_congelado, get_saldo_materia_prima  # noqa: E402

REGISTROS = [43, 44]  # Masa de Croissant, Masa de Medialuna
PRODUCTOS_MASA = [22, 24]  # Masa de Croissant, Masa de Medialuna
USER_ID = 1


def saldos(db, etiqueta: str) -> None:
    print(f"\n  {etiqueta}")
    for pid in PRODUCTOS_MASA:
        prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == pid).first()
        if prod:
            print(f"    {prod.nombre:<20} {get_saldo_congelado(db, pid):>10.4f} {prod.unidad}")
    for ing in db.query(Ingrediente).filter(Ingrediente.nombre.ilike("harina 00 pizza")):
        print(f"    {ing.nombre:<20} {get_saldo_materia_prima(db, ing.id):>10.4f} {ing.unidad_uso}")


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        saldos(db, "ANTES")

        for reg_id in REGISTROS:
            reg = db.query(RegistroProduccion).filter(RegistroProduccion.id == reg_id).first()
            if not reg:
                print(f"\n  reg#{reg_id}: NO EXISTE, salteado")
                continue
            receta = db.query(Receta).filter(Receta.id == reg.tarea.receta_id).first() if reg.tarea else None
            porciones = receta.porciones_por_lote if receta else 1
            print(
                f"\n  reg#{reg_id} ({receta.nombre if receta else '?'}): cantidad_real={reg.cantidad_real} "
                f"-> stock pasa de {reg.cantidad_real * porciones} a {reg.cantidad_real} u "
                f"(el consumo de ingredientes no cambia)"
            )
            if apply:
                revertidos = revertir_efectos(db, reg, USER_ID)
                aplicados = aplicar_efectos(db, reg, USER_ID)
                print(f"    revertidos {revertidos}, aplicados {aplicados}")

        if apply:
            db.commit()
            saldos(db, "DESPUES")
            print("\n  APLICADO")
        else:
            db.rollback()
            print("\n  DRY RUN -- nada escrito. Usa --apply para ejecutar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
