"""One-off: consolidate the leftover StockCongelado rows on Masa Croissant/Medialuna.

Two separate correction rounds ran against these two products today (the other
session's manteca-laminado fix, and this session's lotes-vs-porciones fix).
Each "revert a partly-consumed batch" cycle zeroes the old lot and, when it
can't give back what's already gone, books a NEW "Ajuste por reversion" row
for the shortfall rather than editing anything in place (see
_revertir_salida_congelado() in services/stock.py -- it never deletes, only
adds). Doing that twice on the same two records left 6 StockCongelado rows
each where 1 would do: a couple of harmless zeroed placeholders, and several
offsetting +/- adjustment rows that all net to the correct total but make the
raw per-date sum (what the Stock Congelado pivot table shows) look like
nonsense -- e.g. Masa Croissant's 14/08 column reads "-1.1667" today even
though physically there's 0.1667u on the shelf.

This folds every row NOT protected by a real constraint into the one lot that
IS protected, so the total is unchanged but the shelf is left with one row
telling one true story:
  - Rows referenced by ConsumoFifoDetalle (a FIFO consumption drew from them)
    can never be deleted -- see the comment in _restaurar_lotes() about why.
  - The row carrying `registro_produccion_id` is the canonical lot for that
    production record -- deleting it would break a future edit/revert of that
    record (it looks the lot up by this field). This becomes the consolidation
    target: its cantidad absorbs every other, unprotected row's cantidad.
  - Everything else -- zeroed placeholders and redundant adjustment rows with
    no registro_produccion_id and no FIFO reference -- gets deleted.

The net total per product is verified unchanged before/after (this only moves
numbers between rows of the SAME product, never changes what's owed).

    DATABASE_URL=... python scripts/limpiar_stock_congelado_masa.py           # dry run
    DATABASE_URL=... python scripts/limpiar_stock_congelado_masa.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ConsumoFifoDetalle, ProductoCongelado, StockCongelado  # noqa: E402

PRODUCTOS = [22, 24]  # Masa Croissant, Masa Medialuna
EPSILON = 1e-9


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        for pid in PRODUCTOS:
            prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == pid).first()
            if not prod:
                print(f"\nproducto#{pid}: NO EXISTE, salteado")
                continue

            filas = (
                db.query(StockCongelado)
                .filter(StockCongelado.producto_congelado_id == pid)
                .order_by(StockCongelado.id)
                .all()
            )
            referenciadas = {
                r.stock_congelado_id
                for r in db.query(ConsumoFifoDetalle.stock_congelado_id)
                .filter(ConsumoFifoDetalle.stock_congelado_id.in_([f.id for f in filas]))
                .all()
            }
            con_registro = [f for f in filas if f.registro_produccion_id is not None]

            print(f"\n{prod.nombre} (id={pid}): {len(filas)} filas, total actual = {sum(f.cantidad for f in filas):.4f}")

            if len(con_registro) != 1:
                print(f"  {len(con_registro)} filas con registro_produccion_id (se esperaba 1) -- salteado, revisar a mano")
                continue

            target = con_registro[0]
            eliminables = [
                f for f in filas
                if f.id != target.id and f.id not in referenciadas
            ]
            protegidas_sin_tocar = [
                f for f in filas
                if f.id != target.id and f.id in referenciadas
            ]

            suma_absorbida = sum(f.cantidad for f in eliminables)
            nueva_cantidad = target.cantidad + suma_absorbida

            print(f"  target: fila#{target.id} (cantidad={target.cantidad}) -> {nueva_cantidad:.4f}")
            for f in eliminables:
                print(f"  eliminar: fila#{f.id} (cantidad={f.cantidad}, notas={f.notas!r})")
            for f in protegidas_sin_tocar:
                print(f"  intacta (referenciada por consumo FIFO): fila#{f.id} (cantidad={f.cantidad})")

            total_despues = nueva_cantidad + sum(f.cantidad for f in protegidas_sin_tocar)
            total_antes = sum(f.cantidad for f in filas)
            if abs(total_despues - total_antes) > EPSILON:
                print(f"  ABORTADO: el total cambiaria de {total_antes} a {total_despues}")
                continue

            if apply:
                target.cantidad = nueva_cantidad
                target.is_active = nueva_cantidad > EPSILON
                for f in eliminables:
                    db.delete(f)

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
