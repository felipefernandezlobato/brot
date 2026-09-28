"""One-off: apply Felipe's "LISTA DE PRECIOS AL 01/09" to the ingredient catalog.

Every row of the spreadsheet is transcribed below, including the ones that
already match -- the script is meant to be a faithful copy of the list, and a
row that matches is simply skipped, which is also what makes it idempotent.

Each change records a HistorialPrecio row (precio_anterior -> precio_nuevo,
dated today), exactly like `PUT /api/ingredientes/{id}` does. Cost flows from
`Ingrediente.precio_compra / cantidad_compra` alone -- there are no
PrecioProveedor rows -- so this is the only write a price update needs.

Two rows of the list are deliberately NOT applied as printed:

  * HUEVOS -- the list quotes $267 per UNIDAD, but the ingredient is tracked in
    kg and both recipes that use it ask for grams (Masa de Medialuna 700 g,
    Ensaimadas 400 g). Loading 267 as a per-kilo price would undercost those
    two by ~15x. At 50 g per egg (Felipe, 28/09) the kilo is 267 / 0,050 =
    $5.340, which is what goes in.
  * CHOCOLATE -- the list says $30.000/kg, but on 23/09 the price was changed
    from 30.000 down to 10.600, three weeks after the list was drawn up.
    Felipe confirmed 10.600 is current, so Chocolate is left off the table
    entirely rather than reverted.

LEVADURA, SAL and SEMOLIN are blank in the list and keep their current prices.

Without a flag it does a dry run.

    DATABASE_URL=... python scripts/actualizar_precios_insumos_0109.py
    DATABASE_URL=... python scripts/actualizar_precios_insumos_0109.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import HistorialPrecio, Ingrediente  # noqa: E402

EPSILON = 0.005  # half a centavo

# (id, nombre esperado, precio nuevo por unidad_compra)
# The name is asserted, not just displayed: an id that has drifted to another
# ingredient must be skipped loudly rather than silently repriced.
PRECIOS = [
    (1, "Harina 000", 800.0),
    (2, "Harina 0000", 960.0),
    (3, "Harina 00 Pizza", 1050.0),
    (4, "Harina Integral", 2400.0),
    (5, "Harina Salvado", 750.0),
    (6, "Crema Pastelera", 2411.0),
    (8, "Leche", 1792.01),
    (9, "Huevos", 5340.0),  # $267 / 0,050 kg -- ver docstring
    (10, "Manteca", 13814.0),
    (11, "Aceite Girasol", 4005.0),
    (12, "Aceite Oliva", 16000.0),
    (13, "Grasa de Cerdo", 5300.0),
    (14, "Azúcar", 1273.0),
    (15, "Miel", 7500.0),
    (19, "Canela", 18000.0),
    (21, "Vinagre Blanco", 1700.0),
]


def actualizar(db, apply: bool, log=print) -> list[int]:
    """Returns the ids whose price differs from the list (and, with `apply`,
    were updated). Does not commit -- the caller owns that."""
    cambiados = []

    for ing_id, nombre, nuevo in PRECIOS:
        ing = db.query(Ingrediente).filter(Ingrediente.id == ing_id).first()
        if not ing:
            log(f"  !! {nombre:<20} id {ing_id} no existe, se omite")
            continue
        if ing.nombre != nombre:
            log(f"  !! id {ing_id} es '{ing.nombre}', no '{nombre}' -- se omite")
            continue

        anterior = ing.precio_compra or 0.0
        if abs(anterior - nuevo) <= EPSILON:
            log(f"     {nombre:<20} {anterior:>10,.2f}  (sin cambio)")
            continue

        pct = (nuevo - anterior) / anterior * 100 if anterior else float("inf")
        log(f"  -> {nombre:<20} {anterior:>10,.2f} -> {nuevo:>10,.2f}  ({pct:+.1f}%)")
        cambiados.append(ing_id)

        if apply:
            db.add(HistorialPrecio(
                ingrediente_id=ing.id,
                precio_anterior=anterior,
                precio_nuevo=nuevo,
            ))
            ing.precio_compra = nuevo

    return cambiados


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        cambiados = actualizar(db, apply)
        if not cambiados:
            print("\nTodos los precios ya coinciden con la lista.")
            return
        if not apply:
            print(f"\n[dry run] {len(cambiados)} precio(s) a actualizar. "
                  f"Volve a correr con --apply para escribir.")
            return
        db.commit()
        print(f"\nListo: {len(cambiados)} precio(s) actualizado(s), "
              f"cada uno con su fila en el historial.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
