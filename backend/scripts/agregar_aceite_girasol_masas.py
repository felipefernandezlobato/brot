"""One-off: agregar 50 g de Aceite Girasol a las cuatro masas de pan.

Felipe cambio la formula de las masas de pan: ahora todas llevan 50 g de
aceite de girasol. Afecta a:

    receta 25  Masa Pan Blanco
    receta 26  Masa Pan Negro      (la masa del "pan integral")
    receta 47  Masa Barra Blanca
    receta 48  Masa Barra Integral

Las recetas 47/48 son masas nuevas (se separaron de los escandallos de
Barra Blanca/Integral 350g) y las terminadas (recetas 8 y 9) las consumen
como linea de subreceta "1 u", asi que el aceite sube solo por la cadena de
costes: NO hay que tocar las recetas 8/9.

OJO CON LA UNIDAD -- esta es la parte que se rompe tarde y mal:
`Aceite Girasol` (ingrediente 11) tiene `unidad_uso = "litro"`, o sea una
unidad de VOLUMEN. Una `LineaReceta` de un ingrediente tiene que usar una
unidad de la MISMA familia (peso vs volumen) que el `unidad_uso` de ese
ingrediente, porque `convertir()` explota si le pedis cruzar de familia --
y explota en el momento en que la receta se PRODUCE, no cuando se guarda,
asi que se manifiesta como un bug aparentemente inconexo dias despues.
Por eso los "50 g" NO se guardan como `50 g`.

La convencion del proyecto para este caso es 1 g -> 1 ml: los "150 g ACEITE
OLIVA" del Excel de Pizza estan guardados como `0.15 litro` (linea 31,
receta 7), y lo mismo la Focaccia (`0.41 litro`, receta 36) y el Pan Lomo
(`0.15 litro`, receta 45). Entonces aca: `0.05` con unidad `"litro"`.

Esto es data de catalogo (`LineaReceta`), no el ledger de stock: no toca
`MovimientoStock` / `StockCongelado` / `InventarioRegistro`, y no modifica
retroactivamente ninguna produccion ya registrada -- los registros viejos
se quedan con los movimientos que ya tienen. El ingrediente empieza a
descontarse recien en las producciones nuevas.

Idempotente: si una receta ya tiene una linea de Aceite Girasol, la saltea.
Sin flag hace dry run.

    DATABASE_URL=... python scripts/agregar_aceite_girasol_masas.py
    DATABASE_URL=... python scripts/agregar_aceite_girasol_masas.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, LineaReceta, Receta  # noqa: E402
from app.services.costes import costo_receta  # noqa: E402

INGREDIENTE_ID = 11  # Aceite Girasol, unidad_uso = "litro"
CANTIDAD = 0.05  # 50 g -> 0.05 litro (convencion 1 g = 1 ml)
UNIDAD = "litro"
RECETAS = [25, 26, 47, 48]


def imprimir_lineas(db, receta: Receta) -> None:
    lineas = (
        db.query(LineaReceta)
        .filter(LineaReceta.receta_id == receta.id)
        .order_by(LineaReceta.id)
        .all()
    )
    for l in lineas:
        nombre = l.ingrediente_rel.nombre if l.ingrediente_id else f"[subreceta] {l.subreceta_rel.nombre}"
        print(f"      linea#{l.id:<5} {l.cantidad:>10g} {l.unidad:<6} {nombre}")


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        ing = db.get(Ingrediente, INGREDIENTE_ID)
        if not ing:
            print(f"Ingrediente {INGREDIENTE_ID} no encontrado")
            return
        if ing.unidad_uso != UNIDAD:
            print(
                f"ABORTA: {ing.nombre} tiene unidad_uso={ing.unidad_uso!r}, "
                f"se esperaba {UNIDAD!r}. Revisar la conversion antes de seguir."
            )
            return

        print(f"Ingrediente: {ing.nombre} (id={ing.id})")
        print(
            f"  unidad_compra={ing.unidad_compra} cantidad_compra={ing.cantidad_compra} "
            f"precio_compra={ing.precio_compra} unidad_uso={ing.unidad_uso}"
        )
        print(f"  linea a insertar: {CANTIDAD} {UNIDAD} (= {CANTIDAD * 1000:g} g)\n")

        antes: dict[int, tuple[float, float]] = {}
        objetivo: list[Receta] = []

        for rid in RECETAS:
            receta = db.get(Receta, rid)
            if not receta:
                print(f"Receta {rid} no encontrada -- se saltea\n")
                continue

            ya = (
                db.query(LineaReceta)
                .filter(
                    LineaReceta.receta_id == rid,
                    LineaReceta.ingrediente_id == INGREDIENTE_ID,
                )
                .first()
            )
            total, por_unidad = costo_receta(receta, db)
            antes[rid] = (total, por_unidad)

            print(f"--- Receta {rid}: {receta.nombre} (porciones_por_lote={receta.porciones_por_lote:g})")
            print("    ANTES:")
            imprimir_lineas(db, receta)
            print(f"    costo lote = ${total:,.2f}   costo por unidad = ${por_unidad:,.2f}")

            if ya:
                print(f"    YA TIENE Aceite Girasol (linea#{ya.id}: {ya.cantidad:g} {ya.unidad}) -- se saltea\n")
                continue

            objetivo.append(receta)
            db.add(
                LineaReceta(
                    receta_id=rid,
                    ingrediente_id=INGREDIENTE_ID,
                    cantidad=CANTIDAD,
                    unidad=UNIDAD,
                )
            )
            print(f"    -> se agrega {CANTIDAD} {UNIDAD} de {ing.nombre}\n")

        if not objetivo:
            print("Nada que agregar.")
            db.rollback()
            return

        # Flush (no commit) para poder calcular el costo nuevo en el dry run
        # tambien; expire_all() para que las colecciones .lineas ya cargadas
        # se vuelvan a leer con la linea nueva incluida.
        db.flush()
        db.expire_all()

        print("=" * 72)
        print("RESULTADO\n")
        for receta in objetivo:
            receta = db.get(Receta, receta.id)
            total_antes, unidad_antes = antes[receta.id]
            total, por_unidad = costo_receta(receta, db)
            print(f"--- Receta {receta.id}: {receta.nombre}")
            print("    DESPUES:")
            imprimir_lineas(db, receta)
            print(
                f"    costo lote     ${total_antes:,.2f} -> ${total:,.2f} "
                f"(+${total - total_antes:,.2f})"
            )
            print(
                f"    costo x unidad ${unidad_antes:,.2f} -> ${por_unidad:,.2f} "
                f"(+${por_unidad - unidad_antes:,.2f})"
            )
            print()

        if apply:
            db.commit()
            print("APLICADO")
        else:
            db.rollback()
            print("DRY RUN -- nada escrito. Usa --apply para ejecutar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
