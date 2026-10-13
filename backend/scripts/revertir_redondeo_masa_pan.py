"""One-off: undo redondear_consumo_masa_pan.py completely.

WHY
---
That script re-declared whole-lote masa consumption on 58 historical bakes via
revert+reapply. The movement ledger came out correct, but REAPPLYING a
production dated in August/September created fresh StockCongelado lots dated
before the 2026-10-09 physical count, and a count can only supersede lots that
already existed when it was taken (`reconciliar_lotes_tras_conteo` sweeps by
`id <`). The bread shelves ballooned: Pan 1kg Integral 23 -> 187, Barra Blanca
24 -> 118, ~+480 units across six products.

This is the failure CLAUDE.md already records as open, on these very products:
"logging production dated BEFORE an existing count inflates the saldo ... Found
2026-10-01 on Barra Blanca Cocinado". Reapplying historical production will
ALWAYS do this while a later count exists, so the rounding cannot be achieved
this way at all -- not with better numbers, not with a different rounding rule.

WHAT THIS DOES
--------------
For each of the 60 affected RegistroProduccion rows: `revertir_efectos` and
clear `consumo_padre_declarado`. No reapply. That is the sanctioned path and it
undoes BOTH halves of the damage:

  * the lots the reapply created are shrunk/deactivated by
    `_revertir_salida_congelado`, which finds them by `registro_produccion_id`;
  * the FIFO draws the reapply took out of pre-existing masa lots are put back
    exactly, lot by lot, from the `ConsumoFifoDetalle` rows -- which is why this
    has to go through revertir_efectos rather than just flipping `is_active` on
    the new lots (that was tried in a dry run and left the masas at 3,04 and
    0,53 instead of 0, because the in-place draws are invisible to it).

Expected end state, matching the dashboard before any of this ran:

    Masa Pan Blanco / Negro / Barra Blanca / Barra Integral      0
    Pan 1kg Integral 23, Pan 500g Integral 21
    Barra Blanca 24, Barra Negra 22
    Pan 1kg Blanco and Pan 500g Blanco: negative (they already were -- their
    2026-10-09 count was itself superseded by deliveries on 10-10)

The records keep `completada=True` with no stock movements, which is the same
shape any record has before it is applied; `aplicar_efectos` is guarded by
`tiene_efectos_stock`, so nothing reapplies on its own.

Snapshot of the lot table taken before running: /tmp/snapshot_lotes_antes_revert.json

    DATABASE_URL=... python scripts/revertir_redondeo_masa_pan.py           # dry run
    DATABASE_URL=... python scripts/revertir_redondeo_masa_pan.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, RegistroProduccion  # noqa: E402
from app.services.produccion_registro import revertir_efectos  # noqa: E402
from app.services.stock import get_saldo_congelado  # noqa: E402

MASAS = ["Masa Pan Blanco", "Masa Pan Negro", "Masa Barra Blanca", "Masa Barra Integral"]
USER_ID = 1

ESPERADO = {
    "Masa Pan Blanco": 0.0,
    "Masa Pan Negro": 0.0,
    "Masa Barra Blanca": 0.0,
    "Masa Barra Integral": 0.0,
    "Pan 1kg Integral Cocinado": 23.0,
    "Pan 500g Integral Cocinado": 21.0,
    "Barra Blanca Cocinado": 24.0,
    "Barra Negra Cocinado": 22.0,
}


def afectados(db):
    prods, regs = [], []
    for nombre in MASAS:
        masa = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == nombre).first()
        if not masa:
            continue
        hijos = db.query(ProductoCongelado).filter(
            ProductoCongelado.producto_padre_id == masa.id).all()
        prods.append(masa)
        prods += hijos
        regs += (
            db.query(RegistroProduccion)
            .filter(
                RegistroProduccion.completada.is_(True),
                RegistroProduccion.producto_congelado_id.in_([h.id for h in hijos]),
            )
            .order_by(RegistroProduccion.fecha, RegistroProduccion.id)
            .all()
        )
    return prods, regs


def saldos(db, prods, etiqueta):
    print(f"\n  {etiqueta}")
    for p in prods:
        v = get_saldo_congelado(db, p.id)
        esp = ESPERADO.get(p.nombre)
        marca = ""
        if esp is not None:
            marca = "  OK" if abs(v - esp) < 0.01 else f"  != esperado {esp:g}"
        print(f"    {p.nombre:30} {v:>9.2f}{marca}")


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        prods, regs = afectados(db)
        print(f"{'REVIRTIENDO' if aplicar else 'DRY RUN'} -- {len(regs)} registros")
        saldos(db, prods, "saldos ANTES (inflados)")

        if not aplicar:
            con_valor = [r for r in regs if r.consumo_padre_declarado is not None]
            print(f"\n  {len(con_valor)} registros tienen consumo declarado y se limpiarian")
            print("  dry run: no se escribio nada. Agregar --apply.")
            return

        for r in regs:
            revertir_efectos(db, r, USER_ID)
            r.consumo_padre_declarado = None
            db.flush()
        db.commit()
        print(f"\n  {len(regs)} registros revertidos")
        saldos(db, prods, "saldos DESPUES")
    finally:
        db.close()


if __name__ == "__main__":
    main()
