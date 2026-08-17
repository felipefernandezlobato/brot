"""One-off: backfill the missing "carga inicial" movement for legacy ingredient stock.

Same gap as scripts/reconciliar_ledger_congelado.py, on the ingredient side:
`load_historical.py`'s `load_inventario()` inserted `InventarioRegistro` rows
directly for whatever was on hand when the app went live, with no matching
`MovimientoStock` row. The manual "Registrar" stock-count screen has the same
gap going forward (`POST /api/inventario` never calls `registrar_movimiento`).
Every real transaction since -- production consumption, mermas, pedido
receptions -- DID get logged in the ledger. Result: summing `MovimientoStock`
for an ingredient only sees those transactions, never the stock they moved
against, so it reads deeply negative for most ingredients even though the
real `InventarioRegistro` balance is fine (Harina 000 showing -2.3kg instead
of 272.7kg is one instance of this).

This inserts ONE `carga_inicial` movement per affected ingredient, dated to
the earliest `InventarioRegistro.fecha_registro` on record for it, sized to
make the ledger sum match the real (latest) `InventarioRegistro` balance
again. Additive only -- no existing row is touched, and deleting the inserted
rows fully undoes this.

    DATABASE_URL=... python scripts/reconciliar_ledger_materia_prima.py           # dry run
    DATABASE_URL=... python scripts/reconciliar_ledger_materia_prima.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, InventarioRegistro, MovimientoStock  # noqa: E402
from app.services.stock import get_saldo_materia_prima  # noqa: E402

REFERENCIA = "carga_inicial:historico"


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        ingredientes = db.query(Ingrediente).order_by(Ingrediente.id).all()
        total_diff = 0.0

        for ing in ingredientes:
            real = get_saldo_materia_prima(db, ing.id)
            ledger = (
                db.query(func.coalesce(func.sum(MovimientoStock.cantidad), 0.0))
                .filter(
                    MovimientoStock.tipo_stock == "materia_prima",
                    MovimientoStock.referencia_producto_id == ing.id,
                )
                .scalar()
            )
            diff = real - ledger
            if abs(diff) < 1e-6:
                continue

            ya_aplicado = (
                db.query(MovimientoStock.id)
                .filter(
                    MovimientoStock.tipo_stock == "materia_prima",
                    MovimientoStock.referencia_producto_id == ing.id,
                    MovimientoStock.referencia_origen == REFERENCIA,
                )
                .first()
            )
            if ya_aplicado:
                print(f"{ing.id:4} {ing.nombre:25} ya tiene carga_inicial, salteado")
                continue

            fecha = (
                db.query(func.min(InventarioRegistro.fecha_registro))
                .filter(InventarioRegistro.ingrediente_id == ing.id)
                .scalar()
            )
            if not fecha:
                print(f"{ing.id:4} {ing.nombre:25} sin InventarioRegistro, salteado")
                continue

            total_diff += diff
            print(f"{ing.id:4} {ing.nombre:25} diff={diff:>10.3f} fecha={fecha} (real={real}, ledger={ledger})")

            if apply:
                db.add(MovimientoStock(
                    tipo_stock="materia_prima",
                    referencia_producto_id=ing.id,
                    cantidad=diff,
                    unidad=ing.unidad_uso,
                    tipo_movimiento="carga_inicial",
                    referencia_origen=REFERENCIA,
                    saldo_despues=ledger + diff,
                    fecha=fecha,
                    notas="Carga inicial: stock cargado en load_historical.py sin movimiento correspondiente",
                ))

        print(f"\n{'APLICADO' if apply else 'DRY RUN'} -- total ajustado: {total_diff:.3f}")
        if apply:
            db.commit()
        else:
            db.rollback()
            print("Usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
