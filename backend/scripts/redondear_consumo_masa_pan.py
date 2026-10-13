"""One-off: declare whole-lote consumption on every past bread/barra bake.

WHY
---
The masa consumed by a bake is derived as `cantidad_real / cantidad_por_padre`,
and for bread that is almost never a whole number: a lote of Masa Pan Blanco
yields 20 panes de 1 kg or 36 de medio, so the standard bake (24 + 30) comes out
at 24/20 + 30/36 = 2,0333 lotes. The history is full of 1,2000 / 0,8333 / 1,1250
and the balances end in things like -2,3750.

Those figures are physically CORRECT -- a lote weighs 21.915 g, a pan de 1 kg
takes 1.096 g and a medio 609 g, so 24 + 30 really is 44.560 g against the
43.830 g mixed. The plan asks for 730 g more bread than it mixes, every cycle.

Felipe asked for whole numbers anyway, explicitly accepting it as cosmetic
("me vale aun que solo sea estetico pero que no se vean los 0.xx"). This does
that: each bake line declares a whole number of lotes, minimum 1.

WHAT IT COSTS
-------------
On the 23 regular days (24 + 30) rounding gives 1 + 1 = 2, which matches what
was actually mixed -- those get strictly better. Two Pan Negro days are
irregular and cannot round cleanly:

    2026-08-22  15 + 12 + 15 piezas  derives 1,4333 -> declared 3
    2026-09-19  15 + 12 piezas       derives 1,0167 -> declared 2

Forcing 1 lote per line there overstates consumption, so Masa Pan Negro's
balance moves from -0,78 to about -3. That was accepted as the price of having
no decimals anywhere.

Resulting balances (amasado - consumido), all whole:
    Masa Pan Blanco      +7     (7 lotes mixed and never baked)
    Masa Pan Negro       -3
    Masa Barra Blanca    -2     (2 lotes baked that were never logged as mixed)
    Masa Barra Integral  -1

The +7 and the -2 are NOT created by this script and are not fixed by it. They
are whole lotes missing a record on one side or the other; rounding just stops
a 0,03-per-cycle residue from hiding them.

HOW
---
Via the real revert+reapply path (`revertir_efectos` / `aplicar_efectos`), same
as corregir_lotes_masa.py and corregir_produccion_agosto.py. It does NOT touch
MovimientoStock rows directly -- that is forbidden (see CLAUDE.md, "Never
hand-edit MovimientoStock"), and the machinery already knows how to handle a
batch partly consumed downstream: it books the shortfall as a negative
adjustment lot rather than pretending it can un-consume flour that is gone.

Re-runnable: it writes `consumo_padre_declarado` and reapplies, so running it
again is a no-op, and a different rounding rule can be applied later the same
way.

    DATABASE_URL=... python scripts/redondear_consumo_masa_pan.py           # dry run
    DATABASE_URL=... python scripts/redondear_consumo_masa_pan.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, RegistroProduccion  # noqa: E402
from app.services.produccion_registro import aplicar_efectos, revertir_efectos  # noqa: E402
from app.services.stock import get_saldo_congelado  # noqa: E402

MASAS = ["Masa Pan Blanco", "Masa Pan Negro", "Masa Barra Blanca", "Masa Barra Integral"]
USER_ID = 1


def saldos(db, etiqueta: str) -> None:
    print(f"\n  {etiqueta}")
    for nombre in MASAS:
        prod = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == nombre).first()
        if prod:
            print(f"    {prod.nombre:<22} {get_saldo_congelado(db, prod.id):>10.4f} {prod.unidad}")


def planificar(db):
    """[(registro, derivado, declarado)] for every bake to re-declare."""
    plan = []
    for nombre in MASAS:
        masa = db.query(ProductoCongelado).filter(ProductoCongelado.nombre == nombre).first()
        if not masa:
            print(f"  OJO: no existe {nombre}")
            continue
        hijos = {
            h.id: h
            for h in db.query(ProductoCongelado)
            .filter(ProductoCongelado.producto_padre_id == masa.id)
            .all()
        }
        regs = (
            db.query(RegistroProduccion)
            .filter(
                RegistroProduccion.completada.is_(True),
                RegistroProduccion.producto_congelado_id.in_(list(hijos)),
            )
            .order_by(RegistroProduccion.fecha, RegistroProduccion.id)
            .all()
        )
        for r in regs:
            hijo = hijos[r.producto_congelado_id]
            if not hijo.cantidad_por_padre or not r.cantidad_real:
                continue
            derivado = r.cantidad_real / hijo.cantidad_por_padre
            declarado = max(1, round(derivado))
            plan.append((r, hijo, masa, derivado, float(declarado)))
    return plan


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        plan = planificar(db)
        print(f"{'REAPLICANDO' if aplicar else 'DRY RUN'} -- {len(plan)} registros de horneado")
        saldos(db, "saldos ANTES")

        print("\n  cambios por registro:")
        ya = 0
        for r, hijo, masa, derivado, declarado in plan:
            if r.consumo_padre_declarado == declarado:
                ya += 1
                continue
            flag = "" if abs(derivado - declarado) < 0.005 else "  <-- cambia el consumo"
            print(
                f"    reg {r.id:>4} {r.fecha}  {r.cantidad_real:>5.0f} u "
                f"{hijo.nombre.replace(' Cocinado', ''):<22} "
                f"{derivado:.4f} -> {declarado:.0f} de {masa.nombre}{flag}"
            )
        if ya:
            print(f"    ({ya} ya estaban en su valor, se saltean)")

        if not aplicar:
            print("\n  dry run: no se escribio nada. Agregar --apply para aplicar.")
            return

        tocados = 0
        for r, _hijo, _masa, _derivado, declarado in plan:
            if r.consumo_padre_declarado == declarado:
                continue
            # Revertir primero: aplicar_efectos es idempotente y no hace nada si
            # el registro ya tiene movimientos con su referencia.
            revertir_efectos(db, r, USER_ID)
            r.consumo_padre_declarado = declarado
            db.flush()
            aplicar_efectos(db, r, USER_ID)
            tocados += 1
        db.commit()
        print(f"\n  {tocados} registros reaplicados")
        saldos(db, "saldos DESPUES")
    finally:
        db.close()


if __name__ == "__main__":
    main()
