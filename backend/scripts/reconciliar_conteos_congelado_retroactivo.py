"""One-off: apply the new count-reconciliation retroactively to existing data.

`add_stock_congelado` (routers/congelados.py) now deactivates prior active
lots when a fresh headcount (no fecha_vencimiento) is registered -- see
`reconciliar_lotes_tras_conteo` in services/stock.py for why. That fix only
takes effect for counts registered AFTER it shipped (2026-08-29); counts
already in the database never got their superseded lots deactivated, so
`stock_actual` for those products still double-counts.

This finds each active product's most recent genuine headcount (same
matching rule the live endpoint uses: es_conteo_manual + no
fecha_vencimiento) and runs the exact same `reconciliar_lotes_tras_conteo`
against it -- no separate logic, so this can't drift from what the live fix
does. Additive only in effect: it only ever flips is_active False on stale
rows, never touches MovimientoStock, never deletes anything.

    DATABASE_URL=... python scripts/reconciliar_conteos_congelado_retroactivo.py           # dry run
    DATABASE_URL=... python scripts/reconciliar_conteos_congelado_retroactivo.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, StockCongelado  # noqa: E402
from app.services.stock import (  # noqa: E402
    es_conteo_manual,
    get_saldo_congelado,
    reconciliar_lotes_tras_conteo,
)


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        productos = db.query(ProductoCongelado).order_by(ProductoCongelado.id).all()
        total_afectados = 0

        for prod in productos:
            lotes = (
                db.query(StockCongelado)
                .filter(StockCongelado.producto_congelado_id == prod.id)
                .order_by(StockCongelado.fecha_entrada.desc(), StockCongelado.id.desc())
                .all()
            )
            ultimo_conteo = next(
                (
                    l for l in lotes
                    if es_conteo_manual("congelado", l.notas) and l.fecha_vencimiento is None
                ),
                None,
            )
            if not ultimo_conteo:
                continue

            antes = get_saldo_congelado(db, prod.id)
            n = reconciliar_lotes_tras_conteo(db, ultimo_conteo)
            if n == 0:
                continue

            db.flush()  # get_saldo_congelado must see the just-deactivated lots
            despues = get_saldo_congelado(db, prod.id)
            total_afectados += 1
            print(
                f"{prod.id:4} {prod.nombre:30} conteo={ultimo_conteo.fecha_entrada} "
                f"lotes_desactivados={n}  stock_actual: {antes:.2f} -> {despues:.2f}"
            )

        print(f"\n{'APLICADO' if apply else 'DRY RUN'} -- productos corregidos: {total_afectados}")
        if apply:
            db.commit()
        else:
            db.rollback()
            print("Usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
