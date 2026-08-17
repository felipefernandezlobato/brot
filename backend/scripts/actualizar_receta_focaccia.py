"""One-off: rework the Focaccia recipe/production chain per Felipe's new process.

Changes:
  - Ingrediente "Papa Deshidratada": sets precio_compra=3500 for its existing
    125g purchase unit (was never priced, precio_compra=0).
  - New subreceta "Pure" (125g Papa Deshidratada + 700g Agua -> 825g yield),
    consumed by Amasar Focaccia instead of a direct Papa Deshidratada line.
  - Receta "Amasar Focaccia": ingredient lines replaced with the new batch
    (4kg harina, 2.2L agua, 1.6kg masa madre, 110g sal, 3g levadura, 0.41L
    aceite oliva, 825g pure). Aceitunas Verdes and Romero removed (not part
    of the new dough recipe -- toppings, if any, aren't tracked here anymore).
  - Receta "Cocinar Focaccia": porciones_por_lote 1 -> 3 (cost per bandeja,
    not per whole batch -- matches the same pattern as Croissant/Pan costing).
  - ProductoCongelado "Focaccia Cruda" -> "Masa de Focaccia" (crudo/masa
    level, 1 unit = 1 batch of dough); "Focaccia 1kg" -> "Focaccia"
    (terminado, cantidad_por_padre 1 -> 3: cooking 3 bandejas now correctly
    consumes exactly 1 unit of masa).
  - Two new TareaProduccion rows: "Amasar Focaccia" on Viernes, "Cocinar
    Focaccia" on Sabado -- Focaccia currently has no calendar tasks at all.

    DATABASE_URL=... python scripts/actualizar_receta_focaccia.py           # dry run
    DATABASE_URL=... python scripts/actualizar_receta_focaccia.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Ingrediente,
    LineaReceta,
    ProductoCongelado,
    Receta,
    TareaProduccion,
)

VIERNES = 5
SABADO = 6


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        papa = db.query(Ingrediente).filter(Ingrediente.nombre == "Papa Deshidratada").first()
        agua = db.query(Ingrediente).filter(Ingrediente.nombre == "Agua").first()
        harina = db.query(Ingrediente).filter(Ingrediente.nombre == "Harina 000").first()
        sal = db.query(Ingrediente).filter(Ingrediente.nombre == "Sal").first()
        levadura = db.query(Ingrediente).filter(Ingrediente.nombre == "Levadura").first()
        aceite = db.query(Ingrediente).filter(Ingrediente.nombre == "Aceite Oliva").first()
        masa_madre = db.query(Receta).filter(Receta.nombre == "Masa Madre", Receta.es_subreceta.is_(True)).first()
        amasar = db.query(Receta).filter(Receta.nombre == "Amasar Focaccia").first()
        cocinar = db.query(Receta).filter(Receta.nombre == "Cocinar Focaccia").first()
        masa_prod = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == "Focaccia Cruda").first()
        term_prod = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == "Focaccia 1kg").first()

        faltantes = [
            n for n, v in [
                ("Papa Deshidratada", papa), ("Agua", agua), ("Harina 000", harina),
                ("Sal", sal), ("Levadura", levadura), ("Aceite Oliva", aceite),
                ("Masa Madre (subreceta)", masa_madre), ("Amasar Focaccia", amasar),
                ("Cocinar Focaccia", cocinar), ("Focaccia Cruda (producto)", masa_prod),
                ("Focaccia 1kg (producto)", term_prod),
            ] if v is None
        ]
        if faltantes:
            print("Faltan en la base:", ", ".join(faltantes))
            return

        print(f"1) Papa Deshidratada: precio_compra {papa.precio_compra} -> 3500")
        if apply:
            papa.precio_compra = 3500

        pure = db.query(Receta).filter(Receta.nombre == "Pure", Receta.es_subreceta.is_(True)).first()
        if pure:
            print(f"2) Receta 'Pure' ya existe (id={pure.id})")
        else:
            print("2) CREAR receta 'Pure' (subreceta, 825g = 125g Papa Deshidratada + 700g Agua)")
            if apply:
                pure = Receta(
                    nombre="Pure", categoria_id=amasar.categoria_id,
                    porciones_por_lote=825, es_subreceta=True, unidad_rendimiento="g",
                )
                db.add(pure)
                db.flush()
                db.add(LineaReceta(receta_id=pure.id, ingrediente_id=papa.id, cantidad=125.0, unidad="g"))
                db.add(LineaReceta(receta_id=pure.id, ingrediente_id=agua.id, cantidad=700.0, unidad="g"))

        print(f"3) Receta 'Amasar Focaccia' (id={amasar.id}): reemplazar lineas")
        lineas_actuales = db.query(LineaReceta).filter(LineaReceta.receta_id == amasar.id).all()
        for l in lineas_actuales:
            print(f"   eliminar linea#{l.id} (cantidad={l.cantidad} {l.unidad})")
            if apply:
                db.delete(l)
        if apply:
            db.flush()
            db.add(LineaReceta(receta_id=amasar.id, ingrediente_id=harina.id, cantidad=4000.0, unidad="g"))
            db.add(LineaReceta(receta_id=amasar.id, ingrediente_id=agua.id, cantidad=2.2, unidad="litro"))
            db.add(LineaReceta(receta_id=amasar.id, subreceta_id=masa_madre.id, cantidad=1600.0, unidad="g"))
            db.add(LineaReceta(receta_id=amasar.id, ingrediente_id=sal.id, cantidad=110.0, unidad="g"))
            db.add(LineaReceta(receta_id=amasar.id, ingrediente_id=levadura.id, cantidad=3.0, unidad="g"))
            db.add(LineaReceta(receta_id=amasar.id, ingrediente_id=aceite.id, cantidad=0.41, unidad="litro"))
            db.add(LineaReceta(receta_id=amasar.id, subreceta_id=pure.id, cantidad=825.0, unidad="g"))
        print("   + Harina 000 4000g, Agua 2.2L, Masa Madre 1600g, Sal 110g, Levadura 3g, Aceite Oliva 0.41L, Pure 825g")

        print(f"4) Receta 'Cocinar Focaccia' (id={cocinar.id}): porciones_por_lote {cocinar.porciones_por_lote} -> 3 (costo por bandeja)")
        if apply:
            cocinar.porciones_por_lote = 3

        print(f"5) Producto '{masa_prod.nombre}' -> 'Masa de Focaccia'")
        print(f"   Producto '{term_prod.nombre}' -> 'Focaccia', cantidad_por_padre {term_prod.cantidad_por_padre} -> 3")
        if apply:
            masa_prod.nombre = "Masa de Focaccia"
            term_prod.nombre = "Focaccia"
            term_prod.cantidad_por_padre = 3.0

        tareas_existentes = db.query(TareaProduccion).filter(TareaProduccion.titulo.ilike("%focaccia%")).count()
        if tareas_existentes:
            print(f"6) Ya existen {tareas_existentes} tareas de Focaccia, no se agregan mas")
        else:
            print("6) CREAR tareas: Viernes 'Amasar Focaccia' (u receta), Sabado 'Cocinar Focaccia' (bandejas)")
            if apply:
                # cantidad_planificada is required, not just a hint: the day
                # view only renders the quantity input when it's set
                # (frontend/src/app/produccion/page.tsx checks
                # `tarea.cantidad_planificada !== null`) -- a task with no
                # planned quantity has nowhere to type an actual one.
                db.add(TareaProduccion(
                    dia_semana=VIERNES, hora="08:00", titulo="Amasar Focaccia",
                    cantidad_planificada=1.0, unidad_cantidad="u receta", receta_id=amasar.id,
                    producto_congelado_id=masa_prod.id, tipo="produccion",
                ))
                db.add(TareaProduccion(
                    dia_semana=SABADO, hora="08:00", titulo="Cocinar Focaccia",
                    cantidad_planificada=3.0, unidad_cantidad="bandejas", receta_id=cocinar.id,
                    producto_congelado_id=term_prod.id, tipo="produccion",
                ))

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
