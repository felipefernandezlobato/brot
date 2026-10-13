"""Recovery step: reapply the 60 bread/barra productions with DERIVED
consumption (consumo_padre_declarado = None), restoring the movement ledger to
exactly what it was before any of this started.

Context: redondear_consumo_masa_pan.py re-declared whole-lote consumption and
inflated the shelves (lots dated before a later count). revertir_redondeo_masa_pan.py
then reverted without reapplying, which removed each record's production output
entirely and drove the terminados deeply negative -- the counts could not
absorb the loss because they had already absorbed those same outputs once.

This puts the outputs back. After it, the LEDGER is correct and matches the
pre-script state. The physical shelf will still be inflated by lots dated
before the 2026-10-09 count, which a count cannot retroactively sweep; that is
re-established with a fresh count, the mechanism built for it.

    DATABASE_URL=... python scripts/reaplicar_masa_pan_derivado.py           # dry run
    DATABASE_URL=... python scripts/reaplicar_masa_pan_derivado.py --apply
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, RegistroProduccion, MovimientoStock  # noqa: E402
from app.services.produccion_registro import aplicar_efectos  # noqa: E402
from app.services.stock import get_saldo_congelado  # noqa: E402

MASAS = ["Masa Pan Blanco", "Masa Pan Negro", "Masa Barra Blanca", "Masa Barra Integral"]
USER_ID = 1


def main():
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        prods, regs = [], []
        for n in MASAS:
            m = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == n).first()
            hijos = db.query(ProductoCongelado).filter(
                ProductoCongelado.producto_padre_id == m.id).all()
            prods += [m] + hijos
            regs += db.query(RegistroProduccion).filter(
                RegistroProduccion.completada.is_(True),
                RegistroProduccion.producto_congelado_id.in_([h.id for h in hijos])
            ).order_by(RegistroProduccion.fecha, RegistroProduccion.id).all()

        print(f"{'REAPLICANDO' if aplicar else 'DRY RUN'} -- {len(regs)} registros")
        sin = [r for r in regs if r.consumo_padre_declarado is None]
        print(f"  {len(sin)} con consumo_padre_declarado None (derivaran solos)")
        for p in prods:
            print(f"    {p.nombre:30} {get_saldo_congelado(db, p.id):>9.2f}")
        if not aplicar:
            print("\n  dry run. Agregar --apply.")
            return
        n_ok = 0
        for r in regs:
            r.consumo_padre_declarado = None
            db.flush()
            if aplicar_efectos(db, r, USER_ID):
                n_ok += 1
        db.commit()
        print(f"\n  {n_ok} registros reaplicados")
        print("\n  saldos (estanteria) y ledger:")
        for p in prods:
            led = sum(x.cantidad for x in db.query(MovimientoStock).filter(
                MovimientoStock.tipo_stock == "congelado",
                MovimientoStock.referencia_producto_id == p.id))
            print(f"    {p.nombre:30} estanteria {get_saldo_congelado(db, p.id):>9.2f}   ledger {led:>+9.4f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
