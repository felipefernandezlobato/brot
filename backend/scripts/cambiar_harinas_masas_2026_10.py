"""One-off: cambio de harinas en tres masas (Felipe, 2026-10-15).

  * Masa de Croissant: -5 kg Harina 00 Pizza, +5 kg Harina 0000. El resto igual
    (la harina total del lote sigue siendo 19,5 kg).
  * Masa Pan Negro: el salvado sale y sus 500 g pasan a Harina Integral, que
    queda en 4.000 g (3.500 + 500, el total que indico Felipe).
  * Masa Barra Integral: lo mismo, 250 g de salvado -> Harina Integral 1.500 g.

La linea de salvado se BORRA en vez de dejarla en 0: el costo es identico y una
linea en cero solo ensucia el escandallo.

POR QUE SE CONGELA EL HISTORIAL PRIMERO
---------------------------------------
Felipe lo pidio "a partir de ahora", y sin este paso no lo seria. El costo de
una venta pasada se toma de `costo_unitario_snapshot` si existe y, si no, se
reconstruye con `costo_receta(fecha=...)`: precios historicos pero **lineas de
receta actuales**. Habia 331 de 349 lineas de venta sin snapshot, asi que
cambiar las recetas movia los margenes de agosto y septiembre como si los panes
integrales siempre hubieran costado mas.

Asi que primero se rellena el snapshot de las lineas ya entregadas con la
receta de HOY, y recien despues se cambian las recetas. Solo se tocan las
ventas en estado "entregado": una no entregada todavia no es historia, y
congelarle el costo ahora le pondria el de la receta vieja a algo que se va a
producir con la nueva (`_snapshot_costos` solo escribe lo que esta en null, asi
que el valor que pusieramos ahora ganaria para siempre).

IMPACTO EN COSTOS, medido antes de aplicar
------------------------------------------
Bolleria (via Masa Croissant): Croissant, Cruffin, Moño, Pan Suizo, Pan de
Choco y NY Roll bajan ~1,32 cada uno; el multiplicador se queda en 3,00x.
Panes integrales: Pan Integral 1kg 810,51 -> 851,76 (multi 2,50 -> 2,38),
Pan Integral 0.5kg 450,28 -> 473,20 (2,51 -> 2,39), Barra Integral 350g
272,61 -> 289,80 (3,01 -> 2,83).

**Los PVP se dejan como estan**: Felipe decidio absorber el mayor costo de la
harina integral (2.400/kg contra 750 del salvado) en vez de repreciar.

    DATABASE_URL=... python scripts/cambiar_harinas_masas_2026_10.py           # dry run
    DATABASE_URL=... python scripts/cambiar_harinas_masas_2026_10.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    EntregaB2B,
    Ingrediente,
    LineaReceta,
    PedidoCliente,
    Receta,
    User,
)
from app.routers.entregas_b2b import _snapshot_costos  # noqa: E402
from app.routers.recetas import update_receta  # noqa: E402
from app.schemas import RecetaUpdate  # noqa: E402
from app.services.costes import costo_receta  # noqa: E402

# receta -> {ingrediente: cantidad nueva en g}. Lo que no se nombra no cambia;
# un ingrediente con None se quita de la receta.
CAMBIOS = {
    "Masa de Croissant": {"Harina 00 Pizza": 14500.0, "Harina 0000": 5000.0},
    "Masa Pan Negro": {"Harina Integral": 4000.0, "Harina Salvado": None},
    "Masa Barra Integral": {"Harina Integral": 1500.0, "Harina Salvado": None},
}

AFECTADOS = [
    "Croissant", "Cruffin", "Moño", "Pan Suizo", "Pan de Choco Cocinado", "NY Roll",
    "Pan Integral 1kg", "Pan Integral 0.5kg", "Barra Integral 350g",
]


def lineas_nuevas(db, receta: Receta, cambios: dict) -> list[dict]:
    """La lista completa de lineas que tendra la receta. `update_receta`
    reemplaza todas, asi que hay que mandarlas todas."""
    por_nombre = {i.nombre: i for i in db.query(Ingrediente).all()}
    out, vistos = [], set()
    for l in db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).order_by(LineaReceta.id):
        if l.subreceta_id:
            out.append({"subreceta_id": l.subreceta_id, "cantidad": l.cantidad, "unidad": l.unidad})
            continue
        nombre = next((n for n, i in por_nombre.items() if i.id == l.ingrediente_id), None)
        if nombre in cambios:
            vistos.add(nombre)
            nueva = cambios[nombre]
            if nueva is None:
                continue  # se quita
            out.append({"ingrediente_id": l.ingrediente_id, "cantidad": nueva, "unidad": l.unidad})
        else:
            out.append({"ingrediente_id": l.ingrediente_id, "cantidad": l.cantidad, "unidad": l.unidad})
    # Ingredientes que el cambio agrega y la receta no tenia (Harina 0000).
    for nombre, cant in cambios.items():
        if nombre in vistos or cant is None:
            continue
        out.append({"ingrediente_id": por_nombre[nombre].id, "cantidad": cant, "unidad": "g"})
    return out


def congelar_historial(db) -> int:
    """Snapshot del costo en toda venta ENTREGADA que aun no lo tenga."""
    n = 0
    for e in db.query(EntregaB2B).filter(EntregaB2B.estado == "entregado").all():
        faltan = [l for l in e.lineas if l.costo_unitario_snapshot is None]
        if faltan:
            _snapshot_costos(db, faltan, e.fecha_entrega)
            n += sum(1 for l in faltan if l.costo_unitario_snapshot is not None)
    for p in db.query(PedidoCliente).filter(PedidoCliente.estado == "entregado").all():
        faltan = [l for l in p.lineas if l.costo_unitario_snapshot is None]
        if faltan:
            _snapshot_costos(db, faltan, p.fecha_entrega)
            n += sum(1 for l in faltan if l.costo_unitario_snapshot is not None)
    return n


def costos(db) -> dict:
    out = {}
    for n in AFECTADOS:
        r = db.query(Receta).filter(Receta.nombre == n).first()
        if r:
            out[n] = costo_receta(r, db)[1]
    return out


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print("  no hay usuario admin.")
            return

        print(f"{'APLICANDO' if aplicar else 'DRY RUN'}\n")
        antes = costos(db)
        for nombre, cambios in CAMBIOS.items():
            receta = db.query(Receta).filter(Receta.nombre == nombre).first()
            if not receta:
                print(f"  ABORTADO: no existe la receta '{nombre}'")
                return
            print(f"  {nombre}:")
            for ing_nombre, cant in cambios.items():
                print(f"      {ing_nombre:20} -> {'se quita' if cant is None else f'{cant:g} g'}")

        if not aplicar:
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        congeladas = congelar_historial(db)
        db.flush()
        print(f"\n  historial congelado: {congeladas} lineas de venta con costo propio")

        for nombre, cambios in CAMBIOS.items():
            receta = db.query(Receta).filter(Receta.nombre == nombre).first()
            update_receta(
                receta.id,
                RecetaUpdate(lineas=lineas_nuevas(db, receta, cambios)),
                user=admin,
                db=db,
            )

        despues = costos(db)
        print(f"\n  {'producto':24} {'antes':>9} {'despues':>9} {'cambio':>8}")
        for n in AFECTADOS:
            if n in antes:
                print(f"    {n:22} {antes[n]:>9.2f} {despues[n]:>9.2f} {despues[n] - antes[n]:>+8.2f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
