"""One-off: undo two ledger corrections left over from before the edit
feature was redesigned on 2026-08-21.

Earlier that day, PUT /api/inventario/{id} still called
ajustar_correccion_conteo() on every edit, silently syncing the ledger to
match whatever count was entered. Two accidental edits during that window
(Huevos and Harina 00 Pizza, both dated 20/08) each left a live
`correccion_conteo` movement behind that forces that day's calculado to
match the physical count exactly -- hiding whatever real discrepancy
should be visible there under the current design (editing a count no
longer touches the ledger at all; a physical count is compared against
whatever the ledger actually says, and the day AFTER a count re-anchors
regardless).

This does NOT touch the physical counts themselves (InventarioRegistro
365/627 for Huevos, 359/622 for Harina 00 Pizza) -- those are correct.
It only reverts the two `correccion_conteo` ledger entries, using this
codebase's own revert primitive (retag + compensating entry, never an
in-place edit), so 20/08 shows the ledger's true value again.

    DATABASE_URL=... python scripts/revertir_correcciones_conteo_obsoletas.py           # dry run
    DATABASE_URL=... python scripts/revertir_correcciones_conteo_obsoletas.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import MovimientoStock, User  # noqa: E402
from app.services.stock import _revertir_correccion_conteo  # noqa: E402

REFERENCIAS = [
    "correccion_conteo:materia_prima:627",  # Huevos, 20/08
    "correccion_conteo:materia_prima:622",  # Harina 00 Pizza, 20/08
]


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == "admin").first()
        for referencia in REFERENCIAS:
            vivos = (
                db.query(MovimientoStock)
                .filter(MovimientoStock.referencia_origen == referencia)
                .all()
            )
            if not vivos:
                print(f"{referencia}: nada que revertir, salteado")
                continue
            print(f"{referencia}: revirtiendo {len(vivos)} movimiento(s) -> {[m.cantidad for m in vivos]}")
            if apply:
                _revertir_correccion_conteo(db, referencia, user.id if user else None)

        print(f"\n{'APLICADO' if apply else 'DRY RUN'}")
        if apply:
            db.commit()
        else:
            db.rollback()
            print("Usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
