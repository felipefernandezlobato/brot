"""One-off: switch Papa Deshidratada (ingrediente 27) from grams to kilograms.

It's the only ingredient tracked in grams while every other flour-family
ingredient (Harina 000, Harina 00 Pizza, etc.) tracks in kg -- small-magnitude
gram values (0.125) were repeatedly mistyped as if they were kg (125 g typed
as "0.125"), most recently on the 20/8 and 27/8 manual counts (see the
Papa Deshidratada kg/g mix-up conversation, 2026-09-10).

`unidad_uso`/`unidad_compra` alone aren't enough to fix -- every existing
`InventarioRegistro` and `MovimientoStock` row for this ingredient is a raw
number in the OLD unit (grams), so switching the ingredient's unit without
rescaling history would make every past row read as if it were 1000x its
real quantity. This rescales (/1000) both tables for ingrediente_id=27 and
flips the unit fields, all in one transaction. `LineaReceta` needs no change:
receta 39 (Pure)'s "125 g Papa Deshidratada" line stays in grams -- convertir()
already converts a recipe line's own unit into the ingredient's unidad_uso at
production time regardless of what that unidad_uso is.

Without a flag it does a dry run.

    DATABASE_URL=... python scripts/convertir_papa_deshidratada_a_kg.py
    DATABASE_URL=... python scripts/convertir_papa_deshidratada_a_kg.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, InventarioRegistro, MovimientoStock  # noqa: E402

INGREDIENTE_ID = 27
FACTOR = 1000.0  # g -> kg


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        ing = db.query(Ingrediente).filter(Ingrediente.id == INGREDIENTE_ID).first()
        if not ing:
            print(f"Ingrediente {INGREDIENTE_ID} no encontrado")
            return
        if ing.unidad_uso == "kg":
            print(f"{ing.nombre}: ya esta en kg, nada que hacer")
            return

        print(f"Ingrediente: {ing.nombre} (id={ing.id})")
        print(f"  unidad_compra={ing.unidad_compra} cantidad_compra={ing.cantidad_compra} "
              f"precio_compra={ing.precio_compra} unidad_uso={ing.unidad_uso}")

        regs = (
            db.query(InventarioRegistro)
            .filter(InventarioRegistro.ingrediente_id == INGREDIENTE_ID)
            .order_by(InventarioRegistro.fecha_registro, InventarioRegistro.id)
            .all()
        )
        movs = (
            db.query(MovimientoStock)
            .filter(
                MovimientoStock.tipo_stock == "materia_prima",
                MovimientoStock.referencia_producto_id == INGREDIENTE_ID,
            )
            .order_by(MovimientoStock.fecha, MovimientoStock.id)
            .all()
        )

        print(f"\n{len(regs)} InventarioRegistro, {len(movs)} MovimientoStock a rescalar (/{FACTOR:g}):\n")
        for r in regs:
            nuevo = round(r.cantidad / FACTOR, 6)
            print(f"  InventarioRegistro#{r.id:5} {r.fecha_registro}  {r.cantidad:>10} {r.unidad} -> {nuevo:>10} kg")
            if apply:
                r.cantidad = nuevo
                r.unidad = "kg"

        for m in movs:
            nuevo = round(m.cantidad / FACTOR, 6)
            nuevo_saldo = round(m.saldo_despues / FACTOR, 6) if m.saldo_despues is not None else None
            print(f"  MovimientoStock#{m.id:5}    {m.fecha}  {m.cantidad:>10} {m.unidad} -> {nuevo:>10} kg "
                  f"({m.tipo_movimiento})")
            if apply:
                m.cantidad = nuevo
                m.unidad = "kg"
                m.saldo_despues = nuevo_saldo

        print(f"\nIngrediente: unidad_compra g->kg, unidad_uso g->kg, "
              f"cantidad_compra {ing.cantidad_compra}->{ing.cantidad_compra / FACTOR:g}")
        if apply:
            ing.unidad_compra = "kg"
            ing.unidad_uso = "kg"
            ing.cantidad_compra = ing.cantidad_compra / FACTOR

        if apply:
            db.commit()
            print("\nAPLICADO")
        else:
            db.rollback()
            print("\nDRY RUN -- nada escrito. Usa --apply para ejecutar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
