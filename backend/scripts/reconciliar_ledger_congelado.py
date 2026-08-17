"""One-off: backfill the missing "carga inicial" movement for legacy frozen stock.

`load_historical.py` inserted `StockCongelado` rows directly for whatever was
on hand when the app went live, with no matching `MovimientoStock` row. Every
real transaction since (deliveries, mermas, production) DID get logged in the
ledger. Result: summing `MovimientoStock` for a product only sees the
consumption, never the stock it was consumed from, so `stock_actual` (which
prefers that sum whenever any movement exists -- see recetas.py/congelados.py)
reads deeply negative for ~20 products even though the real StockCongelado
count is fine. "Croissant" showing -134 instead of 7 is one instance of this.

This inserts ONE `carga_inicial` movement per affected product, dated to the
earliest date we have on record for it (its earliest StockCongelado.fecha_entrada,
or the day before its earliest ledger movement for the couple of products with
no StockCongelado row left at all), sized to make the ledger sum match the real
StockCongelado count again. Additive only -- no existing row is touched, and
deleting the inserted rows fully undoes this.

    DATABASE_URL=... python scripts/reconciliar_ledger_congelado.py           # dry run
    DATABASE_URL=... python scripts/reconciliar_ledger_congelado.py --apply
"""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import MovimientoStock, ProductoCongelado, StockCongelado  # noqa: E402
from app.services.stock import get_saldo_congelado  # noqa: E402

REFERENCIA = "carga_inicial:historico"


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        productos = db.query(ProductoCongelado).order_by(ProductoCongelado.id).all()
        total_diff = 0.0

        for prod in productos:
            real = get_saldo_congelado(db, prod.id)
            ledger = (
                db.query(func.coalesce(func.sum(MovimientoStock.cantidad), 0.0))
                .filter(
                    MovimientoStock.tipo_stock == "congelado",
                    MovimientoStock.referencia_producto_id == prod.id,
                )
                .scalar()
            )
            diff = real - ledger
            if abs(diff) < 1e-6:
                continue

            ya_aplicado = (
                db.query(MovimientoStock.id)
                .filter(
                    MovimientoStock.tipo_stock == "congelado",
                    MovimientoStock.referencia_producto_id == prod.id,
                    MovimientoStock.referencia_origen == REFERENCIA,
                )
                .first()
            )
            if ya_aplicado:
                print(f"{prod.id:4} {prod.nombre:25} ya tiene carga_inicial, salteado")
                continue

            primer_stock = (
                db.query(func.min(StockCongelado.fecha_entrada))
                .filter(StockCongelado.producto_congelado_id == prod.id)
                .scalar()
            )
            if primer_stock:
                fecha = primer_stock
            else:
                primer_mov = (
                    db.query(func.min(MovimientoStock.fecha))
                    .filter(
                        MovimientoStock.tipo_stock == "congelado",
                        MovimientoStock.referencia_producto_id == prod.id,
                    )
                    .scalar()
                )
                fecha = (primer_mov - timedelta(days=1)) if primer_mov else None
            if not fecha:
                print(f"{prod.id:4} {prod.nombre:25} sin fecha de referencia, salteado")
                continue

            total_diff += diff
            print(f"{prod.id:4} {prod.nombre:25} diff={diff:>8.2f} fecha={fecha} (real={real}, ledger={ledger})")

            if apply:
                db.add(MovimientoStock(
                    tipo_stock="congelado",
                    referencia_producto_id=prod.id,
                    cantidad=diff,
                    unidad=prod.unidad,
                    tipo_movimiento="carga_inicial",
                    referencia_origen=REFERENCIA,
                    saldo_despues=ledger + diff,
                    fecha=fecha,
                    notas="Carga inicial: stock cargado en load_historical.py sin movimiento correspondiente",
                ))

        print(f"\n{'APLICADO' if apply else 'DRY RUN'} -- total ajustado: {total_diff:.2f}")
        if apply:
            db.commit()
        else:
            db.rollback()
            print("Usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
