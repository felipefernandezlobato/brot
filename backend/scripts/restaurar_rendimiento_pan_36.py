"""One-off: devolver el rendimiento del pan de "medio kilo" a 36 por lote.

Revierte la parte de rendimiento de corregir_rendimiento_pan_medio_kilo.py (la
parte de la tarea duplicada del sabado se queda: esa era correcta y sigue).

Aquel script lo subio a 40 razonando que, siendo la misma masa, el de medio kilo
tenia que ser medio bollo del de 1 kg: 1.093 g / 2 = 547 g -> 40 por lote. El
obrador desmiente la premisa: los bollos de "medio kilo" se dividen de verdad a
**600 g**, que es justo lo que da 36 por lote (21.865 / 36 = 607 g). El nombre
del producto es una etiqueta comercial, no el peso del bollo.

O sea que el modelo estaba bien y el razonamiento de "medio bollo" era falso. Lo
que el 36 SI deja al descubierto son dos cosas reales, ninguna de las cuales se
arregla tocando este numero:

  * el plan no cierra: 24/20 + 30/36 = 2,0333 lotes pedidos contra 2,0 amasados.
    Son 44.454 g de masa pedidos contra 43.730 g amasados, 724 g de menos, poco
    mas de un bollo. Por eso cada ciclo deja un ajuste de -0,033 por stock
    insuficiente. Se arregla en el PLAN (amasar un pelo mas, o planificar un pan
    menos), no en el rendimiento;

  * el de medio kilo esta mal preciado. Lleva el 55,6% de la masa del de 1 kg
    (607 de 1.093 g) pero se vende a exactamente la mitad (631 de 1.262), asi
    que rinde 2,24x contra 2,49x. Para igualar margen tendria que estar a ~$700
    (y el integral a ~$1.043 en vez de $940). El Excel original ya arrastraba el
    error: costeaba "por unit 0.5kg $210", la mitad clavada de los $421 del de
    1 kg, como si el bollo fuera de 547 g.

Sin flag hace dry run.

    DATABASE_URL=... python scripts/restaurar_rendimiento_pan_36.py
    DATABASE_URL=... python scripts/restaurar_rendimiento_pan_36.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import ProductoCongelado, Receta  # noqa: E402
from app.database import SessionLocal  # noqa: E402

RENDIMIENTO_REAL = 36.0  # bollos de 600 g, confirmado por el obrador

RECETAS_MEDIO_KILO = [5, 22]       # Pan Blanco 0.5kg, Pan Integral 0.5kg
CONGELADOS_MEDIO_KILO = [15, 17]   # Pan 500g Blanco/Integral Cocinado


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        for receta_id in RECETAS_MEDIO_KILO:
            r = db.query(Receta).filter(Receta.id == receta_id).first()
            if not r:
                print(f"receta {receta_id} no encontrada")
                continue
            if r.porciones_por_lote == RENDIMIENTO_REAL:
                print(f"  {r.nombre}: ya esta en {RENDIMIENTO_REAL:.0f}")
                continue
            print(f"  receta {receta_id} {r.nombre}: "
                  f"porciones_por_lote {r.porciones_por_lote} -> {RENDIMIENTO_REAL}")
            if apply:
                r.porciones_por_lote = RENDIMIENTO_REAL

        for pc_id in CONGELADOS_MEDIO_KILO:
            p = db.query(ProductoCongelado).filter(ProductoCongelado.id == pc_id).first()
            if not p:
                print(f"producto {pc_id} no encontrado")
                continue
            if p.cantidad_por_padre == RENDIMIENTO_REAL:
                print(f"  {p.nombre}: ya esta en {RENDIMIENTO_REAL:.0f}")
                continue
            print(f"  producto {pc_id} {p.nombre}: "
                  f"cantidad_por_padre {p.cantidad_por_padre} -> {RENDIMIENTO_REAL}")
            if apply:
                p.cantidad_por_padre = RENDIMIENTO_REAL

        if apply:
            db.commit()
            print("\nAplicado.")
        else:
            print("\nDry run -- usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
