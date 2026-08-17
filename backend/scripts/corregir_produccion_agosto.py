"""One-off: relink and correct the 14-15/08/2026 production records.

Those records were written before production stock effects became reversible.
Two problems:

  * Their movements carry the old `produccion:{nombre}:{fecha}` tag, so the new
    UI cannot find them. Editing such a record would apply the new quantity on
    top of the old one instead of replacing it.
  * "u receta" tasks were read as portions, so Masa Croissant deducted 1/9 of
    the recipe and Masa Medialuna 1/6.

This re-tags the movements to `registro_produccion:{id}`, links the frozen lots
they produced, and re-runs the two miscounted records through the current logic
so the quantities land where they should.

Two independent steps, because they carry very different risk:

  --retag       Relabel the movements and link the lots. Changes no quantity at
                all, just makes the records editable from the screen. Safe.
  --recalcular  Re-run the two miscounted records so the amounts are corrected.
                DO NOT run this until the butter double-count is resolved: the
                14/08 recipes demand 46.6 kg of Manteca against a 28 kg count,
                because Manteca Laminado produces 23 kg of lamination butter
                that nothing consumes while Masa de Croissant separately deducts
                9 kg of raw butter for the same purpose. Correcting the ledger
                against a broken recipe just clamps stock at zero and invents an
                18 kg shortfall.

Without a flag it does a dry run.

    DATABASE_URL=... python scripts/corregir_produccion_agosto.py --retag
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, MovimientoStock, ProductoCongelado, RegistroProduccion  # noqa: E402
from app.services.produccion_registro import aplicar_efectos, revertir_efectos  # noqa: E402

# registro id -> the tag its movements were written under
TAGS_VIEJOS = {
    42: "produccion:Manteca Laminado:2026-08-14",
    43: "produccion:Masa Croissant:2026-08-14",
    44: "produccion:Masa Medialunas:2026-08-14",
    47: "produccion:Baston Croissant:2026-08-15",
    48: "produccion:Baston Medialuna:2026-08-15",
}

# Only these were measured in "u receta" with porciones_por_lote > 1, so only
# these were scaled wrong. The rest were already correct — they just needed the
# new tag to become editable.
A_RECALCULAR = [43, 44]

USER_ID = 1


def saldos(db, etiqueta):
    print(f"\n  {etiqueta}")
    for ing in db.query(Ingrediente).order_by(Ingrediente.nombre):
        s = db.execute(
            text(
                "SELECT cantidad FROM inventario_registros WHERE ingrediente_id=:i "
                "ORDER BY fecha_registro DESC, id DESC LIMIT 1"
            ),
            {"i": ing.id},
        ).scalar()
        if s is not None:
            print(f"    {ing.nombre:<22} {s:>12.3f} {ing.unidad_uso}")


def main(retag: bool, recalcular: bool) -> None:
    apply = retag or recalcular
    db = SessionLocal()
    try:
        saldos(db, "SALDOS ANTES")

        print("\n  RE-ETIQUETADO" + ("" if retag else "  (omitido)"))
        for reg_id, tag_viejo in TAGS_VIEJOS.items():
            nuevo = f"registro_produccion:{reg_id}"
            movs = db.query(MovimientoStock).filter(
                MovimientoStock.referencia_origen == tag_viejo
            ).all()
            lotes = db.execute(
                text(
                    "SELECT id FROM stock_congelado WHERE notas = :n "
                    "AND registro_produccion_id IS NULL"
                ),
                {"n": f"Produccion: {tag_viejo}"},
            ).fetchall()
            print(f"    reg#{reg_id}: {len(movs)} movimientos, {len(lotes)} lotes -> {nuevo}")

            if retag:
                for m in movs:
                    m.referencia_origen = nuevo
                if lotes:
                    db.execute(
                        text(
                            "UPDATE stock_congelado SET registro_produccion_id = :r "
                            "WHERE notas = :n AND registro_produccion_id IS NULL"
                        ),
                        {"r": reg_id, "n": f"Produccion: {tag_viejo}"},
                    )
        if retag:
            db.flush()

        print("\n  RECALCULO" + ("" if recalcular else "  (omitido — ver docstring)"))
        for reg_id in A_RECALCULAR:
            reg = db.query(RegistroProduccion).filter(RegistroProduccion.id == reg_id).first()
            if not reg:
                print(f"    reg#{reg_id}: NO EXISTE, salteado")
                continue
            print(f"    reg#{reg_id}: {reg.cantidad_real} {reg.tarea.unidad_cantidad} "
                  f"de \"{reg.tarea.titulo}\"")
            if recalcular:
                revertidos = revertir_efectos(db, reg, USER_ID)
                aplicados = aplicar_efectos(db, reg, USER_ID)
                print(f"      revertidos {revertidos}, aplicados {aplicados}")

        if apply:
            db.commit()
            saldos(db, "SALDOS DESPUES")
            print("\n  APLICADO")
        else:
            db.rollback()
            print("\n  DRY RUN — nada escrito. Usa --apply para ejecutar.")
    finally:
        db.close()


if __name__ == "__main__":
    main(retag="--retag" in sys.argv, recalcular="--recalcular" in sys.argv)
