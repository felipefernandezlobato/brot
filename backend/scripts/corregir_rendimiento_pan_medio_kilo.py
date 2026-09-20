"""One-off: 1 lote de masa rinde 40 panes de 0,5 kg, no 36. Y el sabado tiene
una tarea duplicada de Pan Negro 0,5 kg donde deberia ir la de Pan Blanco.

RENDIMIENTO (recetas 5 y 22, ProductoCongelado 15 y 17)
-------------------------------------------------------
Un lote de Masa Pan Blanco pesa 21.865 g. A 20 panes por lote, el de 1 kg lleva
1.093 g de masa; el de medio kilo tiene que llevar la mitad, 547 g, o sea 40 por
lote. Con 36 lleva 607 g -- un pan de 0,55 kg.

Tres pruebas de que 40 es el numero bueno:

  * los dos tamanos salen de la MISMA masa, asi que el de medio kilo es medio
    bollo del de 1 kg por definicion. 20 y 40, no 20 y 36;
  * el PVP del medio kilo ya es exactamente la mitad (631 = 1262/2, 940 =
    1880/2). A 36 el multiplicador sale 2,24x contra 2,49x del de 1 kg; a 40 los
    dos dan 2,49x clavado (y 3,18x los integrales). El precio se fijo asumiendo
    medio bollo;
  * el Excel original costeaba "precio por kg $383 / por unit 1kg $421 / por
    unit 0.5kg $210", o sea 1,099 kg y 0,548 kg de masa por pieza.
    21,865 / 0,548 = 39,9. El 36 se cargo mal en la app.

El 36 hacia que el plan no cerrara nunca: 24/20 + 30/36 = 2,0333 lotes pedidos
contra 2,0 amasados, y cada ciclo dejaba un lote de ajuste de -0,033 ("Stock
insuficiente: se pidieron 0,833, habia 0,800"). Hay seis en Masa Pan Negro y dos
en Masa Pan Blanco. Con 40: 24/20 + 30/40 = 1,95, entra en los 2 lotes.

SABADO (tarea 101)
------------------
El dia 6 tiene "Pan Negro cocinar 0.5kg" dos veces (tareas 101 y 103, misma
receta 22, mismo producto 17, 15u cada una) y ningun "Pan Blanco cocinar 0.5kg",
cuando los demas dias de horneado llevan siempre la pareja blanco+negro. Por
orden de aparicion (100 blanco 1kg, 101, 102 negro 1kg, 103) la 101 es la que
deberia ser blanco.

NO toca el historial. Los registros ya cargados guardan su propio
`producto_congelado_id` (aplicar_efectos lo fija al aplicar), asi que repuntar la
tarea solo afecta a las proximas veces que se complete. Los movimientos y lotes
existentes se quedan como estan, a proposito.

Sin flag hace dry run.

    DATABASE_URL=... python scripts/corregir_rendimiento_pan_medio_kilo.py
    DATABASE_URL=... python scripts/corregir_rendimiento_pan_medio_kilo.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import ProductoCongelado, Receta, TareaProduccion  # noqa: E402
from app.database import SessionLocal  # noqa: E402

RENDIMIENTO_VIEJO = 36.0
RENDIMIENTO_NUEVO = 40.0

RECETAS_MEDIO_KILO = [5, 22]           # Pan Blanco 0.5kg, Pan Integral 0.5kg
CONGELADOS_MEDIO_KILO = [15, 17]       # Pan 500g Blanco/Integral Cocinado

TAREA_SABADO = 101
RECETA_BLANCO_MEDIO = 5
CONGELADO_BLANCO_MEDIO = 15
TITULO_BLANCO_MEDIO = "Pan Blanco cocinar 0.5kg"


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        print("=== Rendimiento del medio kilo")
        for receta_id in RECETAS_MEDIO_KILO:
            r = db.query(Receta).filter(Receta.id == receta_id).first()
            if not r:
                print(f"  receta {receta_id} no encontrada")
                continue
            if r.porciones_por_lote == RENDIMIENTO_NUEVO:
                print(f"  {r.nombre}: ya esta en {RENDIMIENTO_NUEVO:.0f}")
                continue
            print(f"  receta {receta_id} {r.nombre}: "
                  f"porciones_por_lote {r.porciones_por_lote} -> {RENDIMIENTO_NUEVO}")
            if apply:
                r.porciones_por_lote = RENDIMIENTO_NUEVO

        for pc_id in CONGELADOS_MEDIO_KILO:
            p = db.query(ProductoCongelado).filter(ProductoCongelado.id == pc_id).first()
            if not p:
                print(f"  producto {pc_id} no encontrado")
                continue
            if p.cantidad_por_padre == RENDIMIENTO_NUEVO:
                print(f"  {p.nombre}: ya esta en {RENDIMIENTO_NUEVO:.0f}")
                continue
            print(f"  producto {pc_id} {p.nombre}: "
                  f"cantidad_por_padre {p.cantidad_por_padre} -> {RENDIMIENTO_NUEVO}")
            if apply:
                p.cantidad_por_padre = RENDIMIENTO_NUEVO

        print()
        print("=== Tarea duplicada del sabado")
        t = db.query(TareaProduccion).filter(TareaProduccion.id == TAREA_SABADO).first()
        if not t:
            print(f"  tarea {TAREA_SABADO} no encontrada")
        elif t.receta_id == RECETA_BLANCO_MEDIO:
            print(f"  tarea {TAREA_SABADO}: ya apunta a Pan Blanco 0.5kg")
        else:
            print(f"  tarea {TAREA_SABADO} '{t.titulo}' (receta {t.receta_id}, "
                  f"producto {t.producto_congelado_id})")
            print(f"    -> '{TITULO_BLANCO_MEDIO}' (receta {RECETA_BLANCO_MEDIO}, "
                  f"producto {CONGELADO_BLANCO_MEDIO})")
            if apply:
                t.titulo = TITULO_BLANCO_MEDIO
                t.receta_id = RECETA_BLANCO_MEDIO
                t.producto_congelado_id = CONGELADO_BLANCO_MEDIO

        if apply:
            db.commit()
            print("\nAplicado.")
        else:
            print("\nDry run -- usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
