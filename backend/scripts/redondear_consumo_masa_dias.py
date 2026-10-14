"""One-off: round the masa consumption of historical bakes to whole lotes.

WHY
---
A bake's masa consumption is derived as `cantidad_real / cantidad_por_padre`,
and for bread that is almost never whole: one lote of Masa Pan Blanco is
nominally 20 panes de 1 kg or 36 de medio, so the standard bake (24 + 30)
derives 24/20 + 30/36 = 2,0333 lotes against the 2 actually mixed. The
historial fills up with 1,2000 / 0,8333 / 1,0833 and the balances end in
things like -3,3750.

Felipe asked for whole numbers (2026-10-14): "cuando haya un consumo de masa de
1.04 por ejemplo, tienes que hacer que el consumo sea de 1.00. El input de
ingredientes y el output se tiene que quedar igual, no cambies eso."

HOW THIS DIFFERS FROM redondear_consumo_masa_pan.py (which broke production)
---------------------------------------------------------------------------
That script did the same arithmetic through `revertir_efectos` +
`aplicar_efectos`. The reapply recreated each record's OUTPUT lot, dated in the
past, and a lot inserted after a physical count is never swept by it
(`reconciliar_lotes_tras_conteo` filters by `id <`). Pan 1kg Integral went
23 -> 187. See CLAUDE.md, "NUNCA reaplicar produccion historica".

This one calls `ajustar_consumo_padre`, which only ever touches the parent's
own consumption movement and the parent's lots. It never calls
`producir_producto`/`aplicar_efectos`, never reads a lot carrying a
`registro_produccion_id`, and never touches `InventarioRegistro`. The output
and the ingredients are out of reach by construction.

THE TWO RULES, as chosen by Felipe
----------------------------------
1. **Per masa and day, not per record.** A day's lines are summed, the total is
   rounded, and the result is distributed back over the lines (largest
   remainder). A normal bread day gives 1 + 1 = 2, matching what was mixed.
   Rounding each line separately with a floor of 1 is what made Masa Pan Negro
   read -3 in the previous attempt: three irregular lines summing to 1,4333
   became 3 lotes.
2. **Only days already within TOLERANCIA of a whole number.** 51 of 58
   masa-days are pure derivation noise (Felipe's 1,04 case). The other 7 are
   genuinely fractional -- 1 bastón out of a 3-bastón lote of Masa Hojaldre
   really is a third of a lote -- and rounding those would invent or erase real
   masa, so they are left alone. Consequence, accepted up front: Masa Pan
   Blanco lands on 1,40 and Pan Negro on 1,57 rather than whole, because the
   leftover decimals ARE those untouched days (mostly 2026-08-22).

Raising TOLERANCIA to 1.0 rounds everything, at the cost of putting Masa
Hojaldre at -1 and Masa Medialunas at -0,5 when both physically sit at 0.

SAFETY
------
Dry run by default. On --apply it writes a full snapshot of the StockCongelado
table first (not just the balances -- not having that is what made the previous
incident unrecoverable), then verifies every affected masa's saldo against the
value predicted during the dry run and ROLLS BACK if any differs.

    DATABASE_URL=... python scripts/redondear_consumo_masa_dias.py           # dry run
    DATABASE_URL=... python scripts/redondear_consumo_masa_dias.py --apply
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ProductoCongelado,
    RegistroProduccion,
    StockCongelado,
)
from app.services.produccion_registro import referencia_de  # noqa: E402
from app.services.stock import (  # noqa: E402
    _conteo_posterior,
    ajustar_consumo_padre,
    get_saldo_congelado,
)

# A day further than this from a whole number is real, not derivation noise.
TOLERANCIA = 0.25
USER_ID = 1
SNAPSHOT = Path("/tmp/snapshot_lotes_antes_redondeo_masa.json")


def planificar(db):
    """[(masa, fecha, [(registro, derivado, objetivo)])] for every day to touch."""
    prods = {p.id: p for p in db.query(ProductoCongelado).all()}
    dias = defaultdict(list)
    for r in db.query(RegistroProduccion).filter(RegistroProduccion.completada.is_(True)).all():
        hijo = prods.get(r.producto_congelado_id)
        if not hijo or not hijo.producto_padre_id or not hijo.cantidad_por_padre:
            continue
        if not r.cantidad_real:
            continue
        padre = prods[hijo.producto_padre_id]
        # Only masas, and only where nobody has already declared a value by
        # hand -- a typed number is a person's judgement, not noise to round.
        if padre.nivel != "masa" or r.consumo_padre_declarado is not None:
            continue
        dias[(padre.id, r.fecha)].append((r, hijo, r.cantidad_real / hijo.cantidad_por_padre))

    plan = []
    saltados = []
    for (padre_id, fecha), items in sorted(
        dias.items(), key=lambda kv: (prods[kv[0][0]].nombre, kv[0][1])
    ):
        derivado = sum(d for _, _, d in items)
        if abs(derivado - round(derivado)) > TOLERANCIA:
            saltados.append((prods[padre_id], fecha, derivado))
            continue
        objetivo = max(0, round(derivado))
        reparto = _repartir(items, objetivo)
        cambios = [
            (r, d, float(b)) for b, (r, _h, d) in zip(reparto, items) if abs(b - d) >= 1e-9
        ]
        if cambios:
            plan.append((prods[padre_id], fecha, derivado, objetivo, cambios))
    return plan, saltados


def _repartir(items, objetivo: int) -> list[int]:
    """Whole lotes per line, summing exactly to the day's rounded total.

    Rounding each line independently usually already sums right (1,2 + 0,8333
    -> 1 + 1 = 2). When it doesn't, the line furthest from its own rounding
    absorbs the difference, which keeps every other line on its natural value.
    """
    base = [round(d) for _, _, d in items]
    while sum(base) != objetivo:
        paso = 1 if sum(base) < objetivo else -1
        orden = sorted(
            range(len(items)), key=lambda i: abs(items[i][2] - base[i]), reverse=True
        )
        for i in orden:
            if paso < 0 and base[i] <= 0:
                continue  # never push a line negative to satisfy the total
            base[i] += paso
            break
        else:
            break  # can't reach the target without going negative; leave as is
    return base


def snapshot_lotes(db) -> int:
    filas = [
        {
            "id": l.id,
            "producto_congelado_id": l.producto_congelado_id,
            "cantidad": l.cantidad,
            "cantidad_original": l.cantidad_original,
            "fecha_entrada": str(l.fecha_entrada),
            "is_active": l.is_active,
            "notas": l.notas,
            "registro_produccion_id": l.registro_produccion_id,
        }
        for l in db.query(StockCongelado).order_by(StockCongelado.id).all()
    ]
    SNAPSHOT.write_text(json.dumps(
        {"tomado": datetime.now().isoformat(), "lotes": filas}, indent=1))
    return len(filas)


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        plan, saltados = planificar(db)
        total = sum(len(c) for _, _, _, _, c in plan)
        print(f"{'APLICANDO' if aplicar else 'DRY RUN'} -- tolerancia {TOLERANCIA}")
        print(f"  {len(plan)} dias-masa a corregir, {total} registros")
        print(f"  {len(saltados)} dias saltados por ser genuinamente fraccionados\n")

        for padre, fecha, derivado, objetivo, cambios in plan:
            print(f"  {fecha}  {padre.nombre:20} {derivado:.4f} -> {objetivo}")
            for r, d, nuevo in cambios:
                print(f"      reg {r.id:>4}  {d:.4f} -> {nuevo:.0f}")

        if saltados:
            print("\n  saltados (se dejan con su fraccion real):")
            for padre, fecha, derivado in saltados:
                print(f"      {fecha}  {padre.nombre:20} {derivado:.4f}")

        # Predicted saldo per masa. A day BEHIND a physical count moves the
        # ledger only (ajustar_consumo_padre leaves the lots alone, because
        # the count already re-anchored them), so it contributes nothing to
        # the shelf. Only days with no count after them move it, by exactly
        # derived - rounded.
        #
        # The first version of this prediction assumed every day moved the
        # shelf, and the verification below caught it: Masa Barra Blanca came
        # out at -1,88 against a predicted -3,00, because giving stock back to
        # a count-swept lot reactivates it along with everything it still
        # held. Nothing was written.
        prediccion = {}
        for padre, fecha, derivado, objetivo, _c in plan:
            prediccion.setdefault(padre, get_saldo_congelado(db, padre.id))
            if not _conteo_posterior(db, padre.id, fecha):
                prediccion[padre] += derivado - objetivo
        print(f"\n  {'masa':22} {'ahora':>10} {'quedaria':>10}")
        for padre, esperado in sorted(prediccion.items(), key=lambda kv: kv[0].nombre):
            print(f"  {padre.nombre:22} {get_saldo_congelado(db, padre.id):>10.4f} {esperado:>10.4f}")

        if not aplicar:
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        n = snapshot_lotes(db)
        print(f"\n  snapshot de {n} lotes en {SNAPSHOT}")

        ajustados = 0
        for _padre, _fecha, _derivado, _objetivo, cambios in plan:
            for r, _d, nuevo in cambios:
                mov = ajustar_consumo_padre(db, r.producto_congelado_id, referencia_de(r), nuevo, USER_ID)
                if mov is None:
                    db.rollback()
                    print(f"\n  ABORTADO: el registro {r.id} no tenia consumo del padre que ajustar.")
                    return
                r.consumo_padre_declarado = nuevo
                ajustados += 1
        db.flush()

        for padre, esperado in prediccion.items():
            real = get_saldo_congelado(db, padre.id)
            if abs(real - esperado) > 0.005:
                db.rollback()
                print(f"\n  ABORTADO sin escribir: {padre.nombre} dio {real:.4f}, "
                      f"se esperaba {esperado:.4f}. Nada fue modificado.")
                return

        db.commit()
        print(f"\n  {ajustados} registros ajustados, saldos coinciden con la prediccion.")
        for padre in sorted(prediccion, key=lambda p: p.nombre):
            print(f"      {padre.nombre:22} {get_saldo_congelado(db, padre.id):>10.4f}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
