"""Recovery: put the bread/barra shelf balances back to what they were before
the 2026-10-13 rounding attempt.

The three scripts that ran that day (redondear_consumo_masa_pan,
revertir_redondeo_masa_pan, reaplicar_masa_pan_derivado) left the MovimientoStock
ledger correct and the raw materials untouched, but the StockCongelado lots are
full of artifacts: reapplying production dated before the 2026-10-09 count
created lots the count could no longer sweep, and the two repair attempts added
more. See CLAUDE.md, "NUNCA reaplicar produccion historica...".

This restores the shelf directly: deactivate every current lot for the ten
affected products and insert one lot per product holding the pre-2026-10-13
balance. That is what a fresh physical count does -- supersede everything
before it -- just with the known previous figures instead of a new headcount.

The targets, and how much each is corroborated:

  Pan 1kg Integral     23  |  read off the dashboard before any of this ran
  Pan 500g Integral    21  |  idem
  Barra Blanca         24  |  idem
  Barra Negra          22  |  idem
  the four masas        0  |  measured directly before the first script ran
  Pan 1kg Blanco      -41  |  INFERRED -- see below
  Pan 500g Blanco      -4  |  INFERRED -- see below

The last two were already negative before any of this (their 2026-10-09 count
was itself superseded by deliveries on 10-10), so they never appeared in the
dashboard's top list and there is no direct reading of them. The figures come
from reconstructing "active lots excluding those the first script created",
a rule that reproduced the other four targets exactly (21/23/24/22, 4 of 4),
which is the only reason they are trusted at all. They are the one part of this
restoration worth re-checking against a real count.

Lots are dated 2026-10-09 (the date of the count being restored) rather than
today, so this does not masquerade as a fresh headcount, and carry a notas tag
explaining where they came from.

    DATABASE_URL=... python scripts/restaurar_saldos_pan_pre_1013.py           # dry run
    DATABASE_URL=... python scripts/restaurar_saldos_pan_pre_1013.py --apply
"""
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, StockCongelado  # noqa: E402
from app.services.stock import get_saldo_congelado  # noqa: E402

FECHA = date(2026, 10, 9)
NOTA = "Restauracion del saldo previo al 2026-10-13 (ver scripts/restaurar_saldos_pan_pre_1013.py)"

OBJETIVO = {
    "Masa Pan Blanco": 0.0,
    "Masa Pan Negro": 0.0,
    "Masa Barra Blanca": 0.0,
    "Masa Barra Integral": 0.0,
    "Pan 1kg Integral Cocinado": 23.0,
    "Pan 500g Integral Cocinado": 21.0,
    "Barra Blanca Cocinado": 24.0,
    "Barra Negra Cocinado": 22.0,
    "Pan 1kg Blanco Cocinado": -41.0,
    "Pan 500g Blanco Cocinado": -4.0,
}


def main():
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        print(f"{'RESTAURANDO' if aplicar else 'DRY RUN'}\n")
        print(f"{'producto':30} {'ahora':>9} {'objetivo':>9} {'lotes a desactivar':>19}")
        pendientes = []
        for nombre, objetivo in OBJETIVO.items():
            p = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == nombre).first()
            if not p:
                print(f"  OJO: no existe {nombre}")
                continue
            activos = db.query(StockCongelado).filter(
                StockCongelado.producto_congelado_id == p.id,
                StockCongelado.is_active.is_(True)).all()
            print(f"  {nombre:28} {get_saldo_congelado(db, p.id):>9.2f} {objetivo:>9.2f} {len(activos):>19}")
            pendientes.append((p, objetivo, activos))

        if not aplicar:
            print(f"\n  dry run: {sum(len(a) for _, _, a in pendientes)} lotes se desactivarian "
                  f"y se crearian {len(pendientes)}. Agregar --apply.")
            return

        for p, objetivo, activos in pendientes:
            for l in activos:
                l.is_active = False
            db.add(StockCongelado(
                producto_congelado_id=p.id,
                cantidad=objetivo,
                cantidad_original=objetivo,
                fecha_entrada=FECHA,
                is_active=True,
                notas=NOTA,
            ))
        db.commit()
        print("\n  listo. saldos finales:")
        for p, objetivo, _ in pendientes:
            v = get_saldo_congelado(db, p.id)
            ok = "OK" if abs(v - objetivo) < 0.01 else f"!= {objetivo}"
            print(f"    {p.nombre:30} {v:>9.2f}  {ok}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
