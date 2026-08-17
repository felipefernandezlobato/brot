"""One-off: convert "Masa Madre" from a purchased Ingrediente into a subreceta.

Masa Madre isn't bought -- it's fed daily from Harina 00 Pizza + Agua (50/50 by
weight) -- and it has no ProductoCongelado of its own: it's used inline inside
other recipes, never produced/stocked as its own batch. Modeling it as an
Ingrediente meant its cost was a fixed guess ($400/kg) instead of tracking
flour price, and production of Masa Pan Blanco/Negro, Amasar Focaccia, Barra
Blanca/Integral never actually consumed flour or water for the masa madre
portion (producir_producto only deducted direct ingrediente_id lines).

This creates Receta "Masa Madre" (subreceta, 1kg lote = 0.5kg Harina 00 Pizza
+ 0.5L Agua), repoints the existing LineaReceta rows that reference Masa
Madre as an ingredient to the new subreceta, and deactivates the old
Ingrediente record (kept, not deleted, so price history stays intact).

Because the subreceta has no ProductoCongelado, producir_producto()'s
_consumir_ingredientes_subreceta() will resolve it down to Harina/Agua at
production time -- see backend/app/services/stock.py.

    DATABASE_URL=... python scripts/convertir_masa_madre_subreceta.py           # dry run
    DATABASE_URL=... python scripts/convertir_masa_madre_subreceta.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Categoria, Ingrediente, LineaReceta, Receta  # noqa: E402

MASA_MADRE_NOMBRE = "Masa Madre"
HARINA_NOMBRE = "Harina 00 Pizza"
AGUA_NOMBRE = "Agua"
CATEGORIA_SUBRECETA = "Masas Madre"


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        ing_masa_madre = (
            db.query(Ingrediente).filter(Ingrediente.nombre == MASA_MADRE_NOMBRE).first()
        )
        if not ing_masa_madre:
            print("No se encontro el Ingrediente 'Masa Madre'. Nada que hacer.")
            return

        ing_harina = db.query(Ingrediente).filter(Ingrediente.nombre == HARINA_NOMBRE).first()
        ing_agua = db.query(Ingrediente).filter(Ingrediente.nombre == AGUA_NOMBRE).first()
        if not ing_harina or not ing_agua:
            print(f"Falta '{HARINA_NOMBRE}' o '{AGUA_NOMBRE}' como ingrediente. Abortando.")
            return

        categoria = (
            db.query(Categoria)
            .filter(Categoria.nombre == CATEGORIA_SUBRECETA, Categoria.tipo == "receta")
            .first()
        )
        if not categoria:
            print(f"No se encontro la categoria de receta '{CATEGORIA_SUBRECETA}'. Abortando.")
            return

        receta_masa_madre = (
            db.query(Receta)
            .filter(Receta.nombre == MASA_MADRE_NOMBRE, Receta.es_subreceta.is_(True))
            .first()
        )
        if receta_masa_madre:
            print(f"Ya existe la receta subreceta 'Masa Madre' (id={receta_masa_madre.id}).")
        else:
            print("CREAR receta 'Masa Madre' (subreceta, 1kg por lote = 0.5kg Harina 00 Pizza + 0.5L Agua)")
            if apply:
                receta_masa_madre = Receta(
                    nombre=MASA_MADRE_NOMBRE,
                    categoria_id=categoria.id,
                    porciones_por_lote=1,
                    es_subreceta=True,
                    unidad_rendimiento="kg",
                )
                db.add(receta_masa_madre)
                db.flush()

        lineas_existentes = []
        if receta_masa_madre:
            lineas_existentes = (
                db.query(LineaReceta)
                .filter(LineaReceta.receta_id == receta_masa_madre.id)
                .all()
            )

        if not any(l.ingrediente_id == ing_harina.id for l in lineas_existentes):
            print("  + linea Harina 00 Pizza 0.5 kg")
            if apply:
                db.add(LineaReceta(
                    receta_id=receta_masa_madre.id, ingrediente_id=ing_harina.id,
                    cantidad=0.5, unidad="kg",
                ))
        if not any(l.ingrediente_id == ing_agua.id for l in lineas_existentes):
            print("  + linea Agua 0.5 litro")
            if apply:
                db.add(LineaReceta(
                    receta_id=receta_masa_madre.id, ingrediente_id=ing_agua.id,
                    cantidad=0.5, unidad="litro",
                ))

        if apply:
            db.flush()

        lineas_a_repuntar = (
            db.query(LineaReceta).filter(LineaReceta.ingrediente_id == ing_masa_madre.id).all()
        )
        print(f"\nREPUNTAR {len(lineas_a_repuntar)} lineas que usan Masa Madre como ingrediente:")
        for linea in lineas_a_repuntar:
            receta_padre = db.query(Receta).filter(Receta.id == linea.receta_id).first()
            nombre_padre = receta_padre.nombre if receta_padre else linea.receta_id
            print(f"  - {nombre_padre}: {linea.cantidad} {linea.unidad}")
            if apply:
                linea.ingrediente_id = None
                linea.subreceta_id = receta_masa_madre.id

        print(f"\nDESACTIVAR ingrediente 'Masa Madre' (id={ing_masa_madre.id})")
        if apply:
            ing_masa_madre.activo = False

        if apply:
            db.commit()
            print("\nAPLICADO")
        else:
            db.rollback()
            print("\nDRY RUN - nada escrito. Usa --apply para ejecutar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
