"""One-off: fix the Manteca Laminado double-count in Croissant/Medialuna.

Masa de Croissant and Masa de Medialuna each carried a second "Manteca" line
that was really the lamination butter block (Manteca Laminado), duplicated as
raw butter instead of referencing the block that Baston Croissant/Medialuna
should have consumed when the dough gets laminated into bastones. Confirmed
with Felipe: 1 masa de croissant -> 9 bastones, 9000 g manteca / 9 = 1 kg de
Manteca Laminado por baston (same for medialuna: 6000 g / 6 = 1 kg/baston).

  * Masa de Croissant (receta 1): drop the 9000 g Manteca line (id 7).
  * Masa de Medialuna (receta 2): drop the 6000 g Manteca line (id 18).
  * Baston Croissant (receta 29): add 1 kg Manteca Laminado (subreceta 23).
  * Baston Medialuna (receta 30): add 1 kg Manteca Laminado (subreceta 23).

Then re-run the four 14-15/08 records built from these recipes so the stock
ledger reflects the corrected quantities: 43 (Masa Croissant), 44 (Masa
Medialuna), 47 (Baston Croissant), 48 (Baston Medialuna). 42 (Manteca
Laminado itself) is untouched -- its recipe didn't change.

Without a flag it does a dry run.

    DATABASE_URL=... python scripts/corregir_manteca_laminado.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, LineaReceta, MovimientoStock, Receta, RegistroProduccion  # noqa: E402
from app.services.produccion_registro import aplicar_efectos, revertir_efectos  # noqa: E402

MASA_CROISSANT_ID = 1
MASA_MEDIALUNA_ID = 2
MANTECA_LAMINADO_ID = 23
BASTON_CROISSANT_ID = 29
BASTON_MEDIALUNA_ID = 30

LINEAS_A_BORRAR = {
    MASA_CROISSANT_ID: ("Manteca", 9000.0, "g"),
    MASA_MEDIALUNA_ID: ("Manteca", 6000.0, "g"),
}
BASTONES_A_AGREGAR = [BASTON_CROISSANT_ID, BASTON_MEDIALUNA_ID]

A_RECALCULAR = [43, 44]
# 47/48 (Baston Croissant/Medialuna) are NOT recalculated: their only
# stock-relevant line is the producto_padre_id link to the masa, unaffected
# by this fix. The new Manteca Laminado line added below only affects their
# cost (costo_linea walks every subreceta line); producir_producto's stock
# step skips subreceta lines whose target already has its own ProductoCongelado
# (see _tiene_stock_propio in stock.py) -- Manteca Laminado's 23kg block will
# keep showing as unconsumed stock until that's extended to also deduct FIFO
# from a subreceta's own stock, not just via producto_padre_id.

USER_ID = 1


def saldo_manteca(db):
    ing = db.query(Ingrediente).filter(Ingrediente.nombre == "Manteca").first()
    from sqlalchemy import text
    s = db.execute(
        text(
            "SELECT cantidad FROM inventario_registros WHERE ingrediente_id=:i "
            "ORDER BY fecha_registro DESC, id DESC LIMIT 1"
        ),
        {"i": ing.id},
    ).scalar()
    print(f"  ultimo conteo fisico Manteca: {s} kg")
    total = (
        db.query(MovimientoStock)
        .filter(MovimientoStock.tipo_stock == "materia_prima", MovimientoStock.referencia_producto_id == ing.id)
        .all()
    )
    print(f"  suma total de movimientos Manteca (historico): {sum(m.cantidad for m in total):.3f} kg")


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        print("SALDOS ANTES")
        saldo_manteca(db)

        print("\nBORRAR lineas de manteca duplicada de las masas:")
        for receta_id, (nombre_ing, cantidad, unidad) in LINEAS_A_BORRAR.items():
            linea = (
                db.query(LineaReceta)
                .join(Ingrediente, LineaReceta.ingrediente_id == Ingrediente.id)
                .filter(
                    LineaReceta.receta_id == receta_id,
                    Ingrediente.nombre == nombre_ing,
                    LineaReceta.cantidad == cantidad,
                    LineaReceta.unidad == unidad,
                )
                .first()
            )
            receta = db.query(Receta).filter(Receta.id == receta_id).first()
            if not linea:
                print(f"    receta#{receta_id} ({receta.nombre}): NO SE ENCONTRO la linea de {cantidad}{unidad} {nombre_ing}, salteado")
                continue
            print(f"    receta#{receta_id} ({receta.nombre}): borrar linea#{linea.id} ({cantidad}{unidad} {nombre_ing})")
            if apply:
                db.delete(linea)

        print("\nAGREGAR 1kg Manteca Laminado (subreceta) a cada Baston:")
        for receta_id in BASTONES_A_AGREGAR:
            receta = db.query(Receta).filter(Receta.id == receta_id).first()
            ya_existe = (
                db.query(LineaReceta)
                .filter(LineaReceta.receta_id == receta_id, LineaReceta.subreceta_id == MANTECA_LAMINADO_ID)
                .first()
            )
            if ya_existe:
                print(f"    receta#{receta_id} ({receta.nombre}): ya tiene una linea a Manteca Laminado, salteado")
                continue
            print(f"    receta#{receta_id} ({receta.nombre}): agregar 1kg Manteca Laminado")
            if apply:
                db.add(LineaReceta(receta_id=receta_id, subreceta_id=MANTECA_LAMINADO_ID, cantidad=1.0, unidad="kg"))

        if apply:
            db.flush()

        print("\nRECALCULO de registros 43,44,47,48 con las recetas corregidas:")
        for reg_id in A_RECALCULAR:
            reg = db.query(RegistroProduccion).filter(RegistroProduccion.id == reg_id).first()
            if not reg:
                print(f"    reg#{reg_id}: NO EXISTE, salteado")
                continue
            print(f"    reg#{reg_id}: {reg.cantidad_real} {reg.tarea.unidad_cantidad} de \"{reg.tarea.titulo}\"")
            if apply:
                revertidos = revertir_efectos(db, reg, USER_ID)
                aplicados = aplicar_efectos(db, reg, USER_ID)
                print(f"      revertidos {revertidos}, aplicados {aplicados}")

        if apply:
            db.commit()
            print("\nSALDOS DESPUES")
            saldo_manteca(db)
            print("\nAPLICADO")
        else:
            db.rollback()
            print("\nDRY RUN -- nada escrito. Usa --apply para ejecutar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
