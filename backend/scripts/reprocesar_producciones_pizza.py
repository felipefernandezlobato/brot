"""One-off: re-run the logged Masa de Pizza productions against the current recipe.

Receta 7 (Pizza 350g) carried 0,05 L of Tomate per batch, which was a typo for
1 L -- 50 ml of sauce across 20 pizzas. Felipe corrected the recipe on
2026-09-28, but the two batches already produced had deducted ingredients under
the old formula, so Stock MP still shows the tomato that never came back:

    Tomate ledger 6,00 - 0,05 - 0,05 = 5,90 L  vs  conteo fisico 4,00 L (24/09)
    la diferencia, 1,90 L, es exactamente 2 x 0,95 L.

Only the two `masa` records deduct ingredients (registros 176 del 28/08 y 278
del 22/09). The `terminado` records (177, 290) consume Masa de Pizza from the
freezer, and receta 44 didn't change, so they're deliberately left alone.

The correction goes through `revertir_efectos` / `aplicar_efectos` -- the exact
pair `PUT /api/produccion/registro/{id}` runs when you hit "Editar" and
"Guardar" on the record in /produccion. Nothing here writes a MovimientoStock
row by hand: the service functions already know every side effect (giving the
ingredients back, retagging the originals to `:rev`, rebuilding the frozen lot).

Idempotent: a record whose live consumption already matches the current recipe
is skipped, so re-running this leaves no extra reversal churn in the ledger.

What this does NOT move is any ingredient's current stock figure. Stock MP is a
running total -- every consumption INSERTs an InventarioRegistro carrying the
resulting balance, and get_saldo_materia_prima() reads the latest by
(fecha_registro, id) -- and revertir_consumos deliberately dates its give-back
to the record's own date rather than today (see its docstring). Both batches
predate every one of the seven ingredients' latest count (24/09 and 28/09), so
the rows written at 28/08 and 22/09 can't outrank them. That's the right
outcome: the physical count owns "what's on the shelf", the ledger is what was
wrong, and `calculado` is what compares the two. Tomate ends at 6,00 - 1,00 -
1,00 = 4,00 L calculado against 4,00 L contado.

Heads-up on one side effect, expected and not a bug: reverting registro 278
books the 0,8 u of its lot already consumed downstream as a negative adjustment
lot and creates a fresh 1 u lot, both active. That puts Masa de Pizza's
lot-based "stock actual" at 0,2 u, which is what the ledger already said -- the
0 counted on 24/09 had simply deactivated the leftover lot. Register a new
count if the real number is 0.

Without a flag it does a dry run.

    DATABASE_URL=... python scripts/reprocesar_producciones_pizza.py
    DATABASE_URL=... python scripts/reprocesar_producciones_pizza.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Ingrediente,
    LineaReceta,
    MovimientoStock,
    RegistroProduccion,
)
from app.services.conversiones import convertir  # noqa: E402
from app.services.produccion_registro import (  # noqa: E402
    aplicar_efectos,
    lotes_de_receta,
    referencia_de,
    revertir_efectos,
)

RECETA_MASA_ID = 7  # Pizza 350g
PRODUCTO_MASA_ID = 46  # Masa de Pizza
EPSILON = 1e-6


def consumo_esperado(db, reg) -> dict[int, float]:
    """What each ingredient line should deduct for this record, in the
    ingredient's own unidad_uso -- same math deducir_materia_prima() does."""
    lotes = lotes_de_receta(db, reg)
    esperado: dict[int, float] = {}
    lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == RECETA_MASA_ID).all()
    for linea in lineas:
        if not linea.ingrediente_id:
            continue  # receta 7 has no subreceta lines; nothing to recurse into
        ing = db.query(Ingrediente).filter(Ingrediente.id == linea.ingrediente_id).first()
        if not ing:
            continue
        cantidad = convertir(linea.cantidad * lotes, linea.unidad, ing.unidad_uso)
        esperado[ing.id] = esperado.get(ing.id, 0.0) + cantidad
    return esperado


def consumo_vigente(db, reg) -> dict[int, float]:
    """What this record currently has booked, positive, by ingredient."""
    movs = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.referencia_origen == referencia_de(reg),
            MovimientoStock.tipo_stock == "materia_prima",
        )
        .all()
    )
    vigente: dict[int, float] = {}
    for m in movs:
        vigente[m.referencia_producto_id] = vigente.get(m.referencia_producto_id, 0.0) - m.cantidad
    return vigente


def reprocesar(db, apply: bool, log=print) -> list[int]:
    """Returns the ids of the records that needed reprocessing (and, with
    `apply`, were reprocessed). Does not commit -- the caller owns that."""
    registros = (
        db.query(RegistroProduccion)
        .filter(
            (RegistroProduccion.receta_id == RECETA_MASA_ID)
            | (RegistroProduccion.producto_congelado_id == PRODUCTO_MASA_ID),
            RegistroProduccion.completada.is_(True),
        )
        .order_by(RegistroProduccion.fecha, RegistroProduccion.id)
        .all()
    )
    if not registros:
        log("No hay producciones de Masa de Pizza registradas.")
        return []

    nombres = {i.id: i.nombre for i in db.query(Ingrediente).all()}
    unidades = {i.id: i.unidad_uso for i in db.query(Ingrediente).all()}
    a_reprocesar = []

    for reg in registros:
        esperado = consumo_esperado(db, reg)
        vigente = consumo_vigente(db, reg)
        difieren = {
            ing_id
            for ing_id in set(esperado) | set(vigente)
            if abs(esperado.get(ing_id, 0.0) - vigente.get(ing_id, 0.0)) > EPSILON
        }

        log(f"\nRegistro {reg.id} -- {reg.fecha} -- {reg.cantidad_real:g} lote(s)")
        if not difieren:
            log("  ya coincide con la receta actual, se omite")
            continue

        for ing_id in sorted(difieren):
            u = unidades.get(ing_id, "")
            log(
                f"  {nombres.get(ing_id, ing_id):<20} "
                f"{vigente.get(ing_id, 0.0):>8.3f} -> {esperado.get(ing_id, 0.0):>8.3f} {u}"
            )
        a_reprocesar.append(reg)

    if not a_reprocesar:
        log("\nNada que reprocesar.")
        return []

    if not apply:
        log(f"\n[dry run] {len(a_reprocesar)} registro(s) a reprocesar. "
            f"Volve a correr con --apply para escribir.")
        return [r.id for r in a_reprocesar]

    for reg in a_reprocesar:
        user_id = reg.registrado_por or 1
        revertidos = revertir_efectos(db, reg, user_id)
        nuevos = aplicar_efectos(db, reg, user_id)
        log(f"\nRegistro {reg.id}: {revertidos} movimiento(s) revertido(s), "
            f"{nuevos} nuevo(s)")

    return [r.id for r in a_reprocesar]


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        if reprocesar(db, apply) and apply:
            db.commit()
            print("\nListo.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
