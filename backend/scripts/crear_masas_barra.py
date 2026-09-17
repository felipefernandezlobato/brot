"""One-off: give Barra Blanca / Barra Integral their own masa, like Pizza and Pan Lomo.

Both barras were wired wrong in two incompatible ways at once:

  * the escandallo (receta 8 / 9) carried the full dough formula as DIRECT
    ingredient lines -- 5000g harina + 110g sal + 300g masa madre + 20g
    levadura + 3L agua, 8430g total, /24 = 351g per barra, which matches the
    original Excel exactly; and
  * the stock chain said `Barra Blanca Cocinado` (18) came from `Masa Pan
    Blanco` (26) and `Barra Negra Cocinado` (19) from `Masa Pan Negro` (27),
    24 per lote.

So `producir_producto()` deducted BOTH: the whole ingredient batch *and* a
lote of pan dough. Live example, registro 237 (26u Barra Blanca, 17/09):
-5.42kg Harina 000 ... AND -1.083u Masa Pan Blanco.

The parent link was wrong on its own terms too: Masa Pan Blanco weighs 21865g,
so 21865/24 = 911g per barra, not 350g. And the two doughs are genuinely
different formulas (barra 60% hydration, 0.40% yeast, 6% masa madre; pan 70%,
0.125%, 10%) -- the barras really are amasadas aparte.

This moves the ingredient lines out to two new masa recipes and rewires the
chain to mirror Pan Lomo (receta 45 -> ProductoCongelado 47 -> receta 46 ->
ProductoCongelado 48):

    Masa Barra Blanca   (receta, porciones=1)  -> PC nivel="masa"
      -> Barra Blanca 350g (receta 8, porciones=24, one 1u subreceta line)
      -> Barra Blanca Cocinado (PC 18, padre=masa, cantidad_por_padre=24)

    ... and the same for Integral (receta 9 / PC 19).

`es_subreceta=False` on the masas is deliberate, copied from Masa de Pan Lomo:
barras have no `TareaProduccion` (they're produced as extras), and
`GET /api/produccion/productos-dropdown` filters `es_subreceta == False`, so
`True` would make the amasado impossible to log.

Cost is unchanged: the masa lote costs what receta 8/9 used to cost, receta
8/9 now consume exactly 1 lote, so cost/barra stays $172.81 / $197.70.

Catalog-only -- no `MovimientoStock`/`StockCongelado` row is touched here. The
three already-logged barra productions (registros 88, 237, 238) still carry
their old, wrong movements; correct those afterwards through the app's own
edit path (`PUT /api/produccion/registro/{id}` re-saves via
revertir_efectos/aplicar_efectos), never by hand.

Without a flag it does a dry run.

    DATABASE_URL=... python scripts/crear_masas_barra.py
    DATABASE_URL=... python scripts/crear_masas_barra.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import LineaReceta, ProductoCongelado, Receta  # noqa: E402
from app.database import SessionLocal  # noqa: E402

# (receta del terminado, nombre de la masa nueva, ProductoCongelado del terminado)
CHAINS = [
    (8, "Masa Barra Blanca", 18),
    (9, "Masa Barra Integral", 19),
]

CATEGORIA_ID = 1  # Panes, same as Masa de Pan Lomo
CATEGORIA_PC = "Masas"


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        for receta_id, masa_nombre, pc_terminado_id in CHAINS:
            terminado = db.query(Receta).filter(Receta.id == receta_id).first()
            pc_terminado = (
                db.query(ProductoCongelado)
                .filter(ProductoCongelado.id == pc_terminado_id)
                .first()
            )
            if not terminado or not pc_terminado:
                print(f"receta {receta_id} / producto {pc_terminado_id} no encontrado")
                return

            ya_existe = db.query(Receta).filter(Receta.nombre == masa_nombre).first()
            if ya_existe:
                print(f"{masa_nombre}: ya existe (receta {ya_existe.id}), nada que hacer")
                continue

            lineas = (
                db.query(LineaReceta)
                .filter(LineaReceta.receta_id == receta_id)
                .order_by(LineaReceta.id)
                .all()
            )
            if len(lineas) == 1 and lineas[0].subreceta_id:
                print(f"{terminado.nombre}: ya consume una subreceta, nada que mover")
                continue

            print(f"=== {terminado.nombre} (receta {receta_id})")
            print(f"    padre actual: {pc_terminado.producto_padre_id} "
                  f"x{pc_terminado.cantidad_por_padre}")
            print(f"    -> nueva masa '{masa_nombre}' con {len(lineas)} lineas:")
            for l in lineas:
                print(f"       {l.cantidad} {l.unidad} "
                      f"(ingrediente={l.ingrediente_id} subreceta={l.subreceta_id})")

            if not apply:
                continue

            masa = Receta(
                nombre=masa_nombre,
                categoria_id=CATEGORIA_ID,
                porciones_por_lote=1.0,
                precio_venta=None,
                es_subreceta=False,
                unidad_rendimiento="u",
            )
            db.add(masa)
            db.flush()

            # Move the dough formula verbatim -- same rows, new owner.
            for l in lineas:
                l.receta_id = masa.id
            db.flush()

            posicion = db.query(ProductoCongelado).count() + 1
            pc_masa = ProductoCongelado(
                nombre=masa_nombre,
                categoria=CATEGORIA_PC,
                unidad="u",
                is_active=True,
                position=posicion,
                receta_id=masa.id,
                nivel="masa",
                producto_padre_id=None,
                cantidad_por_padre=None,
            )
            db.add(pc_masa)
            db.flush()

            # The terminado now consumes exactly one lote of its own masa.
            db.add(LineaReceta(
                receta_id=receta_id,
                ingrediente_id=None,
                subreceta_id=masa.id,
                cantidad=1.0,
                unidad="u",
            ))
            pc_terminado.producto_padre_id = pc_masa.id
            pc_terminado.cantidad_por_padre = terminado.porciones_por_lote

            print(f"    receta masa={masa.id}  producto masa={pc_masa.id}  "
                  f"padre de {pc_terminado.nombre} -> {pc_masa.id} "
                  f"x{pc_terminado.cantidad_por_padre}")

        if apply:
            db.commit()
            print("\nAplicado.")
        else:
            print("\nDry run -- usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
