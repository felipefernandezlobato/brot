"""Read-only, full-system integrity audit.

Checks referential integrity, the recipe/product graph (cycles, orphans,
receta_id collisions), and stock ledger consistency. Prints findings only --
never mutates the database. Run with the production DATABASE_URL to audit
production, e.g.:

    DATABASE_URL=postgresql://... python scripts/system_audit.py
"""
from collections import defaultdict

from app.database import SessionLocal
from app.models import (
    ConsumoFifoDetalle,
    EntregaB2B,
    Ingrediente,
    LineaEntregaB2B,
    LineaReceta,
    MermaRegistro,
    MovimientoStock,
    ProductoCatalogo,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    StockCongelado,
    TareaProduccion,
)
from app.services.conversiones import convertir
from app.services.stock import get_saldos_congelado

db = SessionLocal()
findings = []


def report(section, msg):
    findings.append((section, msg))
    print(f"[{section}] {msg}")


# ---------------------------------------------------------------------------
print("=" * 70)
print("A. REFERENTIAL INTEGRITY")
print("=" * 70)

ingrediente_ids = {i.id for i in db.query(Ingrediente.id).all()}
receta_ids = {r.id for r in db.query(Receta.id).all()}
producto_congelado_ids = {p.id for p in db.query(ProductoCongelado.id).all()}
producto_congelado_activos = {
    p.id for p in db.query(ProductoCongelado.id).filter(ProductoCongelado.is_active.is_(True)).all()
}
catalogo_ids = {c.id for c in db.query(ProductoCatalogo.id).all()}
tarea_ids = {t.id for t in db.query(TareaProduccion.id).all()}
stock_congelado_ids = {s.id for s in db.query(StockCongelado.id).all()}
movimiento_ids = {m.id for m in db.query(MovimientoStock.id).all()}

for l in db.query(LineaReceta).all():
    if l.ingrediente_id is not None and l.ingrediente_id not in ingrediente_ids:
        report("A1", f"LineaReceta {l.id} (receta {l.receta_id}) references missing ingrediente_id={l.ingrediente_id}")
    if l.subreceta_id is not None and l.subreceta_id not in receta_ids:
        report("A1", f"LineaReceta {l.id} (receta {l.receta_id}) references missing subreceta_id={l.subreceta_id}")
    if l.receta_id not in receta_ids:
        report("A1", f"LineaReceta {l.id} references missing receta_id={l.receta_id}")
    if (l.ingrediente_id is None) == (l.subreceta_id is None):
        report("A1", f"LineaReceta {l.id} (receta {l.receta_id}) violates XOR: ingrediente_id={l.ingrediente_id} subreceta_id={l.subreceta_id}")

for p in db.query(ProductoCongelado).all():
    if p.receta_id is not None and p.receta_id not in receta_ids:
        report("A3", f"ProductoCongelado {p.id} ({p.nombre}) references missing receta_id={p.receta_id}")
    if p.producto_padre_id is not None:
        if p.producto_padre_id not in producto_congelado_ids:
            report("A4", f"ProductoCongelado {p.id} ({p.nombre}) references missing producto_padre_id={p.producto_padre_id}")
        elif p.is_active and p.producto_padre_id not in producto_congelado_activos:
            padre = db.get(ProductoCongelado, p.producto_padre_id)
            report("A4-orphan", f"ACTIVE ProductoCongelado {p.id} ({p.nombre}) has INACTIVE padre {p.producto_padre_id} ({padre.nombre if padre else '?'})")

for c in db.query(ProductoCatalogo).all():
    if c.receta_id is not None and c.receta_id not in receta_ids:
        report("A5", f"ProductoCatalogo {c.id} ({c.nombre}) references missing receta_id={c.receta_id}")

for t in db.query(TareaProduccion).all():
    if t.producto_congelado_id is not None and t.producto_congelado_id not in producto_congelado_ids:
        report("A6", f"TareaProduccion {t.id} ({t.titulo}) references missing producto_congelado_id={t.producto_congelado_id}")
    if t.receta_id is not None and t.receta_id not in receta_ids:
        report("A6", f"TareaProduccion {t.id} ({t.titulo}) references missing receta_id={t.receta_id}")

for r in db.query(RegistroProduccion).all():
    if r.tarea_id is not None and r.tarea_id not in tarea_ids:
        report("A7", f"RegistroProduccion {r.id} references missing tarea_id={r.tarea_id}")
    if r.receta_id is not None and r.receta_id not in receta_ids:
        report("A7", f"RegistroProduccion {r.id} references missing receta_id={r.receta_id}")
    if r.producto_congelado_id is not None and r.producto_congelado_id not in producto_congelado_ids:
        report("A7", f"RegistroProduccion {r.id} references missing producto_congelado_id={r.producto_congelado_id}")

for m in db.query(MovimientoStock).all():
    if m.tipo_stock == "materia_prima" and m.referencia_producto_id not in ingrediente_ids:
        report("A8", f"MovimientoStock {m.id} (materia_prima) references missing ingrediente_id={m.referencia_producto_id}")
    elif m.tipo_stock == "congelado" and m.referencia_producto_id not in producto_congelado_ids:
        report("A8", f"MovimientoStock {m.id} (congelado) references missing producto_congelado_id={m.referencia_producto_id}")

for cf in db.query(ConsumoFifoDetalle).all():
    if cf.movimiento_stock_id not in movimiento_ids:
        report("A9", f"ConsumoFifoDetalle {cf.id} references missing movimiento_stock_id={cf.movimiento_stock_id}")
    if cf.stock_congelado_id not in stock_congelado_ids:
        report("A9", f"ConsumoFifoDetalle {cf.id} references missing stock_congelado_id={cf.stock_congelado_id}")

for s in db.query(StockCongelado).all():
    if s.producto_congelado_id not in producto_congelado_ids:
        report("A9b", f"StockCongelado {s.id} references missing producto_congelado_id={s.producto_congelado_id}")

for le in db.query(LineaEntregaB2B).all():
    if le.producto_id not in catalogo_ids:
        report("A10", f"LineaEntregaB2B {le.id} (entrega {le.entrega_id}) references missing producto_id={le.producto_id}")

for mr in db.query(MermaRegistro).all():
    if mr.ingrediente_id is not None and mr.ingrediente_id not in ingrediente_ids:
        report("A11", f"MermaRegistro {mr.id} references missing ingrediente_id={mr.ingrediente_id}")
    if mr.receta_id is not None and mr.receta_id not in receta_ids:
        report("A11", f"MermaRegistro {mr.id} references missing receta_id={mr.receta_id}")

print(f"\nSection A findings so far: {len(findings)}")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("B. RECIPE / PRODUCT GRAPH")
print("=" * 70)

# B1: cycle detection across the whole subreceta graph
adjacency = defaultdict(list)
for l in db.query(LineaReceta).filter(LineaReceta.subreceta_id.isnot(None)).all():
    adjacency[l.receta_id].append(l.subreceta_id)

def has_cycle_from(start):
    visited = set()
    stack = [start]
    path = set()

    def dfs(node, path):
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for nxt in adjacency.get(node, []):
            if dfs(nxt, path):
                return True
        path.discard(node)
        return False

    return dfs(start, set())

for rid in adjacency:
    if has_cycle_from(rid):
        report("B1", f"Cycle detected reachable from receta {rid}")

# B2: receta_id shared by more than one ACTIVE ProductoCongelado
by_receta_active = defaultdict(list)
for p in db.query(ProductoCongelado).filter(ProductoCongelado.is_active.is_(True), ProductoCongelado.receta_id.isnot(None)).all():
    by_receta_active[p.receta_id].append(p)
for rid, ps in by_receta_active.items():
    if len(ps) > 1:
        report("B2", f"receta_id={rid} shared by {len(ps)} ACTIVE products: {[(p.id, p.nombre) for p in ps]}")

# B2b: receta_id shared including inactive ones (informational, lower severity)
by_receta_all = defaultdict(list)
for p in db.query(ProductoCongelado).filter(ProductoCongelado.receta_id.isnot(None)).all():
    by_receta_all[p.receta_id].append(p)
for rid, ps in by_receta_all.items():
    if len(ps) > 1 and rid not in by_receta_active:
        report("B2b-info", f"receta_id={rid} shared by {len(ps)} products, none active: {[(p.id, p.nombre, p.is_active) for p in ps]}")
    elif len(ps) > 1 and len(by_receta_active.get(rid, [])) == 1:
        inactive = [p for p in ps if not p.is_active]
        if inactive:
            report("B2c-info", f"receta_id={rid}: 1 active product + {len(inactive)} inactive dupe(s) {[(p.id, p.nombre) for p in inactive]} -- now safe since is_active filter added, but consider deleting dead rows")

# B3: ProductoCatalogo.receta_id collisions
by_receta_catalogo = defaultdict(list)
for c in db.query(ProductoCatalogo).filter(ProductoCatalogo.receta_id.isnot(None)).all():
    by_receta_catalogo[c.receta_id].append(c)
for rid, cs in by_receta_catalogo.items():
    if len(cs) > 1:
        report("B3", f"receta_id={rid} shared by {len(cs)} ProductoCatalogo rows: {[(c.id, c.nombre, c.disponible) for c in cs]}")

# B4: orphaned active children whose entire ancestor chain breaks (already covered by A4-orphan,
# but also check for children with a padre that itself has no receta/stock chain reaching a masa)
for p in db.query(ProductoCongelado).filter(ProductoCongelado.is_active.is_(True), ProductoCongelado.nivel != "masa").all():
    if p.producto_padre_id is None:
        report("B4", f"ACTIVE non-masa product {p.id} ({p.nombre}, nivel={p.nivel}) has NO producto_padre_id -- dead end in the production chain")

# B5: recipes with zero lines, referenced by something active
recetas_con_lineas = {l.receta_id for l in db.query(LineaReceta.receta_id).distinct().all()}
for r in db.query(Receta).all():
    if r.id in recetas_con_lineas:
        continue
    used_by_producto = db.query(ProductoCongelado).filter(ProductoCongelado.receta_id == r.id, ProductoCongelado.is_active.is_(True)).first()
    used_by_tarea = db.query(TareaProduccion).filter(TareaProduccion.receta_id == r.id, TareaProduccion.is_active.is_(True)).first()
    used_by_catalogo = db.query(ProductoCatalogo).filter(ProductoCatalogo.receta_id == r.id, ProductoCatalogo.disponible.is_(True)).first()
    if used_by_producto or used_by_tarea or used_by_catalogo:
        report("B5", f"Receta {r.id} ({r.nombre}) has NO ingredient/subreceta lines but is referenced by an active product/tarea/catalogo item")

# B6: unit-family mismatches on ingredient lines (would crash convertir() at production time)
for l in db.query(LineaReceta).filter(LineaReceta.ingrediente_id.isnot(None)).all():
    ing = db.get(Ingrediente, l.ingrediente_id)
    if not ing:
        continue
    try:
        convertir(1.0, l.unidad, ing.unidad_uso)
    except ValueError as e:
        report("B6", f"LineaReceta {l.id} (receta {l.receta_id}, ingrediente {ing.nombre}): unit mismatch line uses '{l.unidad}' but ingrediente uses '{ing.unidad_uso}' -- {e}")

# B7: subreceta lines pointing at a receta with porciones_por_lote in (None, 0) -- would crash lotes calc
for l in db.query(LineaReceta).filter(LineaReceta.subreceta_id.isnot(None)).all():
    sub = db.get(Receta, l.subreceta_id)
    if sub and (not sub.porciones_por_lote or sub.porciones_por_lote <= 0):
        report("B7", f"LineaReceta {l.id} (receta {l.receta_id}) points at subreceta {sub.id} ({sub.nombre}) with invalid porciones_por_lote={sub.porciones_por_lote}")

print(f"\nSection B findings so far: {len(findings)}")

# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("C. STOCK LEDGER CONSISTENCY")
print("=" * 70)

# C1: ledger cumulative balance vs active StockCongelado lot sum, per active product
saldos_ledger = get_saldos_congelado(db, list(producto_congelado_activos))
for pid in producto_congelado_activos:
    lote_sum = sum(
        s.cantidad for s in db.query(StockCongelado).filter(
            StockCongelado.producto_congelado_id == pid, StockCongelado.is_active.is_(True)
        ).all()
    )
    ledger = saldos_ledger.get(pid, 0.0)
    if abs(lote_sum - ledger) > 0.01:
        p = db.get(ProductoCongelado, pid)
        report("C1", f"ProductoCongelado {pid} ({p.nombre}): ledger balance {ledger:.3f} != active-lot sum {lote_sum:.3f} (diff {ledger - lote_sum:.3f})")

# C3: unretagged duplicate live movements under the same referencia_origen + producto + tipo_movimiento
grouped = defaultdict(list)
for m in db.query(MovimientoStock).filter(~MovimientoStock.referencia_origen.like("%:rev")).all():
    if m.referencia_origen is None:
        continue
    grouped[(m.referencia_origen, m.tipo_stock, m.referencia_producto_id, m.tipo_movimiento)].append(m)
for key, movs in grouped.items():
    if len(movs) > 1:
        ref, tipo_stock, prod_id, tipo_mov = key
        report("C3", f"Multiple live movements ({len(movs)}) for ref={ref} tipo_stock={tipo_stock} producto={prod_id} tipo_movimiento={tipo_mov}: ids={[m.id for m in movs]} cantidades={[m.cantidad for m in movs]}")

# C4: ConsumoFifoDetalle sums match their parent movement's |cantidad|
mov_by_id = {m.id: m for m in db.query(MovimientoStock).all()}
cf_by_mov = defaultdict(list)
for cf in db.query(ConsumoFifoDetalle).all():
    cf_by_mov[cf.movimiento_stock_id].append(cf)
for mov_id, cfs in cf_by_mov.items():
    mov = mov_by_id.get(mov_id)
    if not mov:
        continue
    total_cf = sum(cf.cantidad for cf in cfs)
    if abs(total_cf - abs(mov.cantidad)) > 0.01:
        report("C4", f"MovimientoStock {mov_id} cantidad={mov.cantidad} but ConsumoFifoDetalle rows sum to {total_cf:.3f} (mismatch)")

# C6: EntregaB2B state vs live movements
for e in db.query(EntregaB2B).all():
    ref_prefix = f"entrega_b2b:{e.id}:"
    live = db.query(MovimientoStock).filter(
        MovimientoStock.referencia_origen.like(f"{ref_prefix}%"),
        ~MovimientoStock.referencia_origen.like("%:rev"),
    ).count()
    if e.estado == "entregado" and live == 0 and len(e.lineas) > 0:
        report("C6", f"EntregaB2B {e.id} (cliente {e.cliente_b2b_id}, {e.fecha_entrega}) is 'entregado' with {len(e.lineas)} lines but has NO live stock movements")
    elif e.estado != "entregado" and live > 0:
        report("C6", f"EntregaB2B {e.id} (cliente {e.cliente_b2b_id}, {e.fecha_entrega}) is '{e.estado}' but has {live} LIVE stock movements (should be reverted)")

# C7: RegistroProduccion completada vs live 'produccion_salida' movement
for r in db.query(RegistroProduccion).all():
    ref = f"registro_produccion:{r.id}"
    live_salida = db.query(MovimientoStock).filter(
        MovimientoStock.referencia_origen == ref, MovimientoStock.tipo_movimiento == "produccion_salida"
    ).count()
    if r.completada and r.cantidad_real and r.cantidad_real > 0 and live_salida == 0:
        report("C7", f"RegistroProduccion {r.id} (fecha {r.fecha}) is completada with cantidad_real={r.cantidad_real} but has NO live produccion_salida movement")
    if not r.completada and live_salida > 0:
        report("C7", f"RegistroProduccion {r.id} (fecha {r.fecha}) is NOT completada but has {live_salida} LIVE produccion_salida movement(s)")

# C8: MermaRegistro should have exactly one live consumption movement
for mr in db.query(MermaRegistro).all():
    ref = f"merma:{mr.id}"
    live = db.query(MovimientoStock).filter(MovimientoStock.referencia_origen == ref).all()
    if (mr.ingrediente_id or mr.receta_id) and len(live) == 0:
        report("C8", f"MermaRegistro {mr.id} (fecha {mr.fecha}, motivo {mr.motivo}) has an ingrediente/receta but NO live movement")
    elif len(live) > 1:
        report("C8", f"MermaRegistro {mr.id} (fecha {mr.fecha}) has {len(live)} live movements (expected 1): ids={[m.id for m in live]}")

print(f"\nSection C findings so far: {len(findings)}")

print("\n" + "=" * 70)
print(f"TOTAL FINDINGS: {len(findings)}")
print("=" * 70)
by_section = defaultdict(int)
for section, _ in findings:
    by_section[section] += 1
for section, count in sorted(by_section.items()):
    print(f"  {section}: {count}")
