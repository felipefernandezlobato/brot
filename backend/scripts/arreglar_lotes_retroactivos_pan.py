"""One-off: undo the lot inflation caused by redondear_consumo_masa_pan.py.

WHAT WENT WRONG
---------------
`redondear_consumo_masa_pan.py` re-declared the masa consumption on 58 historical
bakes using the sanctioned revert+reapply path. The MOVEMENT ledger came out
correct, but reapplying a production dated in August/September created fresh
`StockCongelado` lots dated before the 2026-10-09 physical count -- and a count
can only supersede lots that already existed when it was taken
(`reconciliar_lotes_tras_conteo` sweeps by `id <`, so lots inserted afterwards
are never swept even when their `fecha_entrada` precedes it).

Result: the bread products' shelf totals ballooned, e.g. Barra Blanca Cocinado
24 -> 118, Pan 1kg Integral 23 -> 187. ~+162 units across six products.

This is the failure mode CLAUDE.md already records as open, on this very
product: "logging production dated BEFORE an existing count inflates the saldo
... Found 2026-10-01 on Barra Blanca Cocinado."

WHAT THIS DOES
--------------
For each affected product, finds the most recent physical-count lot and
deactivates every ACTIVE lot that was inserted after it (higher `id`) but dated
on or before it (`fecha_entrada <=`). That is exactly the rule
`reconciliar_lotes_tras_conteo` applies at count time, just applied after the
fact to the lots that slipped in behind it.

Production dated AFTER the count is left alone -- it is genuine stock the count
could not have included.

The MovimientoStock ledger is NOT touched: it is already correct (each original
`produccion_salida` is `:rev`-tagged against its give-back, with a fresh one
alongside, netting right). Only the lot `is_active` flags change, which is the
same thing the count itself would have done.

    DATABASE_URL=... python scripts/arreglar_lotes_retroactivos_pan.py           # dry run
    DATABASE_URL=... python scripts/arreglar_lotes_retroactivos_pan.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, StockCongelado  # noqa: E402
from app.services.stock import get_saldo_congelado  # noqa: E402

MASAS = ["Masa Pan Blanco", "Masa Pan Negro", "Masa Barra Blanca", "Masa Barra Integral"]


def productos_afectados(db):
    out = []
    for nombre in MASAS:
        masa = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == nombre).first()
        if not masa:
            continue
        out.append(masa)
        out += (
            db.query(ProductoCongelado)
            .filter(ProductoCongelado.producto_padre_id == masa.id)
            .all()
        )
    return out


def conteo_mas_reciente(db, producto_id: int):
    """The latest physical-count lot still standing.

    `registro_produccion_id IS NULL` alone is NOT enough to identify a count:
    `crear_lote_ajuste()` also leaves it null, and those lots are negative. A
    real headcount is positive and active. Filtering on
    `cantidad_original > 0` is what separates them -- without it this picks an
    adjustment lot and the whole fix lands in the wrong place (it did, first
    try: it reported "conteo del 2026-10-06: -1 u").
    """
    return (
        db.query(StockCongelado)
        .filter(
            StockCongelado.producto_congelado_id == producto_id,
            StockCongelado.registro_produccion_id.is_(None),
            StockCongelado.fecha_vencimiento.is_(None),
            StockCongelado.cantidad_original > 0,
            StockCongelado.is_active.is_(True),
        )
        .order_by(StockCongelado.id.desc())
        .first()
    )


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        print(f"{'APLICANDO' if aplicar else 'DRY RUN'}\n")
        total = 0
        for p in productos_afectados(db):
            conteo = conteo_mas_reciente(db, p.id)
            if not conteo:
                continue
            colados = (
                db.query(StockCongelado)
                .filter(
                    StockCongelado.producto_congelado_id == p.id,
                    StockCongelado.is_active.is_(True),
                    StockCongelado.id > conteo.id,
                    StockCongelado.fecha_entrada <= conteo.fecha_entrada,
                )
                .order_by(StockCongelado.id)
                .all()
            )
            if not colados:
                continue
            antes = get_saldo_congelado(db, p.id)
            suma = sum(l.cantidad for l in colados)
            print(f"  {p.nombre}")
            print(f"    conteo del {conteo.fecha_entrada}: {conteo.cantidad:g} {p.unidad} (lote {conteo.id})")
            for l in colados:
                print(f"      desactivar lote {l.id:>5} fecha {l.fecha_entrada} cant {l.cantidad:>+8.2f} "
                      f"(reg {l.registro_produccion_id})")
            print(f"    estanteria {antes:.2f} -> {antes - suma:.2f}")
            total += len(colados)
            if aplicar:
                for l in colados:
                    l.is_active = False
        if aplicar:
            db.commit()
            print(f"\n  {total} lotes desactivados\n")
            print("  estanteria final:")
            for p in productos_afectados(db):
                print(f"    {p.nombre:30} {get_saldo_congelado(db, p.id):>9.2f} {p.unidad}")
        else:
            print(f"\n  dry run: {total} lotes se desactivarian. Agregar --apply.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
