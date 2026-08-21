from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ConsumoFifoDetalle,
    Ingrediente,
    InventarioRegistro,
    LineaReceta,
    MovimientoStock,
    ProductoCatalogo,
    ProductoCongelado,
    Receta,
    StockCongelado,
)
from app.services.conversiones import convertir


NOTAS_AUTOMATICAS_MATERIA_PRIMA = ["Consumo automatico:", "Reversion de", "Pedido #"]
NOTAS_AUTOMATICAS_CONGELADO = ["Produccion:", "Ajuste por reversion", "Reversion de", "Stock insuficiente"]


def es_conteo_manual(tipo_stock: str, notas: Optional[str]) -> bool:
    """True if a row was entered by a person, not written automatically by
    production/merma consumption, a reversal give-back, or a pedido receipt --
    those carry a recognizable `notas` prefix. Comparing a physical count
    against one of these would flag a "discrepancy" between two numbers that
    came from the same event in the first place, and editing one directly
    (instead of the record that generated it) would leave the ledger out of
    sync with what the edit actually changed.
    """
    if not notas:
        return True
    prefijos = (
        NOTAS_AUTOMATICAS_MATERIA_PRIMA if tipo_stock == "materia_prima" else NOTAS_AUTOMATICAS_CONGELADO
    )
    return not any(notas.startswith(p) for p in prefijos)


def registrar_movimiento(
    db: Session,
    tipo_stock: str,
    producto_id: int,
    cantidad: float,
    unidad: str,
    tipo_movimiento: str,
    referencia_origen: Optional[str] = None,
    saldo_despues: Optional[float] = None,
    user_id: Optional[int] = None,
    notas: Optional[str] = None,
    fecha: Optional[date] = None,
) -> MovimientoStock:
    mov = MovimientoStock(
        tipo_stock=tipo_stock,
        referencia_producto_id=producto_id,
        cantidad=cantidad,
        unidad=unidad,
        tipo_movimiento=tipo_movimiento,
        referencia_origen=referencia_origen,
        saldo_despues=saldo_despues,
        fecha=fecha or date.today(),
        notas=notas,
        registrado_por=user_id,
        registrado_at=datetime.now(timezone.utc),
    )
    db.add(mov)
    return mov


def get_saldo_materia_prima(db: Session, ingrediente_id: int) -> float:
    reg = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ingrediente_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
    )
    return reg.cantidad if reg else 0.0


def get_saldos_congelado(db: Session, ids: Optional[list[int]] = None) -> dict[int, float]:
    """Current balance (sum of active lots) per producto_congelado_id.

    ids=None batches every product with at least one active lot in one query
    -- same "ids=None means everything" convention as
    historial_movimientos_acumulado. Can go negative once a lot has been
    driven below zero by crear_lote_ajuste().
    """
    q = db.query(StockCongelado.producto_congelado_id, func.sum(StockCongelado.cantidad)).filter(
        StockCongelado.is_active.is_(True)
    )
    if ids is not None:
        q = q.filter(StockCongelado.producto_congelado_id.in_(ids))
    return {pid: total or 0.0 for pid, total in q.group_by(StockCongelado.producto_congelado_id).all()}


def get_saldo_congelado(db: Session, producto_congelado_id: int) -> float:
    return get_saldos_congelado(db, [producto_congelado_id]).get(producto_congelado_id, 0.0)


def _conteos_manuales_por_fecha(db: Session, tipo_stock: str, ids: list[int]) -> dict[int, dict[str, float]]:
    """The physical count total per (producto, fecha), genuine manual counts
    only (es_conteo_manual) -- what historial_movimientos_acumulado re-anchors
    calculado to from the day AFTER each one.

    materia_prima: InventarioRegistro is a single running snapshot, so a
    same-day recount keeps only the LAST one entered (rows come back sorted
    ascending by id, so a later dict assignment simply overwrites the
    earlier one for the same date).
    congelado: StockCongelado rows are physical lots, several of which can
    legitimately be counted the same day, so same-day entries are summed --
    the same convention the historial pivot table's own aggregation uses.

    NOTE: `cantidad` on a congelado lot can be mutated in place by a later
    FIFO draw, which can make an old lot's anchor read low once any of it
    has been consumed (see Barra Negra Cocinado, 2026-08-21). A same-lot
    "current remaining + still-live ConsumoFifoDetalle draws" reconstruction
    was tried and reverted the same day: `historial_movimientos_acumulado`'s
    per-movement loop ALSO re-applies every one of those same draws via the
    ledger (day_map), so any lot with more than one subsequent draw (edits,
    partial reversals, multi-date consumption) got double-subtracted and
    came out badly wrong for most of the catalog. Reconstructing this
    correctly needs to account for exactly which draws the loop will
    already re-apply itself -- not attempted again without a much more
    careful design.
    """
    if not ids:
        return {}
    out: dict[int, dict[str, float]] = {}
    if tipo_stock == "materia_prima":
        rows = (
            db.query(InventarioRegistro)
            .filter(InventarioRegistro.ingrediente_id.in_(ids))
            .order_by(InventarioRegistro.fecha_registro, InventarioRegistro.id)
            .all()
        )
        for r in rows:
            if not es_conteo_manual("materia_prima", r.notas):
                continue
            out.setdefault(r.ingrediente_id, {})[str(r.fecha_registro)] = r.cantidad
    else:
        rows = db.query(StockCongelado).filter(StockCongelado.producto_congelado_id.in_(ids)).all()
        for r in rows:
            if not es_conteo_manual("congelado", r.notas):
                continue
            dia = out.setdefault(r.producto_congelado_id, {})
            key = str(r.fecha_entrada)
            dia[key] = dia.get(key, 0.0) + r.cantidad
    return out


def historial_movimientos_acumulado(
    db: Session,
    tipo_stock: str,
    ids: Optional[list[int]] = None,
    fecha_hasta: Optional[date] = None,
) -> dict[int, list[dict]]:
    """Cumulative running balance per date, per referencia_producto_id, from
    MovimientoStock. One point per date that has at least one movement,
    ascending by fecha.

    This reads the true append-only ledger, unlike StockCongelado/
    InventarioRegistro (whose "current value" can be a mutated-in-place lot or
    a raw snapshot rather than a delta), so it's the only reliable way to
    answer "what was the stock on date X" -- see
    scripts/limpiar_stock_congelado_masa.py for what happens when you try to
    reconstruct history from StockCongelado's raw rows instead.

    tipo_stock is "congelado" (finished/frozen products) or "materia_prima"
    (raw ingredients) -- same ledger table, disjoint id spaces.

    ids=None means "every id with a movement of this tipo_stock" (used to
    batch a pivot table's calculated column); a single-element list
    reproduces the old per-item behavior of this function's original callers
    -- including stock_actual, which is always exactly the last point's
    cantidad (== sum of all that item's movement cantidades).

    Re-anchors to the physical count from the day AFTER each genuine manual
    count (2026-08-21): a running balance that never resets just accumulates
    untracked drift forever, so a discrepancy from three weeks ago still
    shows up today even though this week's physical count already accounted
    for it. On the count's own date the running balance is still whatever it
    was BEFORE that count (so the gap against the physical count is visible
    right there, same as always); starting the next date, it resets to that
    count's value and accumulates only real movements from then on, until
    the next manual count repeats the cycle. Items never recounted keep
    accumulating from whatever their last real anchor was -- there's nothing
    day-of-week-specific here, it's purely "did THIS item get counted."
    """
    q = db.query(MovimientoStock).filter(MovimientoStock.tipo_stock == tipo_stock)
    if ids is not None:
        q = q.filter(MovimientoStock.referencia_producto_id.in_(ids))
    if fecha_hasta:
        q = q.filter(MovimientoStock.fecha <= fecha_hasta)
    movs = q.order_by(
        MovimientoStock.referencia_producto_id, MovimientoStock.fecha, MovimientoStock.id
    ).all()

    by_id_date: dict[int, dict[str, float]] = {}
    for m in movs:
        day_map = by_id_date.setdefault(m.referencia_producto_id, {})
        key = str(m.fecha)
        day_map[key] = day_map.get(key, 0.0) + m.cantidad

    anclas = _conteos_manuales_por_fecha(db, tipo_stock, list(by_id_date.keys()))

    result: dict[int, list[dict]] = {}
    for rid, day_map in by_id_date.items():
        anclas_rid = sorted(anclas.get(rid, {}).items())
        ancla_idx = 0
        running = 0.0
        points = []
        for fecha_str in sorted(day_map.keys()):
            while ancla_idx < len(anclas_rid) and anclas_rid[ancla_idx][0] < fecha_str:
                running = anclas_rid[ancla_idx][1]
                ancla_idx += 1
            running += day_map[fecha_str]
            points.append({"fecha": fecha_str, "cantidad": round(running, 2)})
        result[rid] = points
    return result


def deducir_materia_prima(
    db: Session,
    ingrediente_id: int,
    cantidad: float,
    unidad_receta: str,
    referencia: str,
    user_id: Optional[int] = None,
    fecha: Optional[date] = None,
    origen_subreceta: Optional[str] = None,
    tipo_movimiento: str = "produccion_consumo",
) -> MovimientoStock:
    ing = db.query(Ingrediente).filter(Ingrediente.id == ingrediente_id).first()
    if not ing:
        return None

    consumo = convertir(cantidad, unidad_receta, ing.unidad_uso)
    saldo_actual = get_saldo_materia_prima(db, ingrediente_id)
    # Deliberately unclamped: consuming more than what's on hand is a sign
    # something else wasn't recorded (a delivery, a production run), and that
    # should surface as a visible negative balance instead of silently
    # vanishing at zero.
    nuevo_saldo = saldo_actual - consumo

    db.add(InventarioRegistro(
        ingrediente_id=ingrediente_id,
        cantidad=nuevo_saldo,
        unidad=ing.unidad_uso,
        fecha_registro=fecha or date.today(),
        notas=f"Consumo automatico: {referencia}",
    ))
    # Session is autoflush=False: without this, a second deduction against the
    # same ingredient later in this same production (e.g. a direct line plus a
    # subreceta that also uses it) would read the pre-consumption balance.
    db.flush()

    # Both lines share the same referencia_origen (revertir_consumos matches on it
    # exactly, so splitting it would break edit/delete reversal). The subreceta tag
    # rides in `notas` instead, parsed by nombre_origen_movimiento() for display, so
    # "Consumido para Masa Pan Blanco" and "Consumido para Masa Madre" show as two
    # separate movements even though both belong to the same production event.
    notas = f"subreceta:{origen_subreceta}" if origen_subreceta else None
    if nuevo_saldo < -1e-9:
        aviso = f"Stock insuficiente: quedo en {nuevo_saldo:.3f} {ing.unidad_uso}."
        notas = f"{notas} | {aviso}" if notas else aviso

    return registrar_movimiento(
        db, "materia_prima", ingrediente_id, -consumo, ing.unidad_uso,
        tipo_movimiento, referencia, nuevo_saldo, user_id, notas=notas, fecha=fecha,
    )


def crear_lote_ajuste(
    db: Session,
    producto_congelado_id: int,
    cantidad: float,
    fecha: date,
    notas: str,
) -> StockCongelado:
    """A synthetic StockCongelado row for stock that isn't backed by a real lot
    -- always `cantidad` negative in practice, `is_active=True` so it counts
    in get_saldo_congelado()'s sum (a deficit that doesn't count isn't visible
    at all). Shared by deducir_congelado_fifo (real lots didn't cover the full
    request) and produccion_registro._revertir_salida_congelado (a produced
    batch was already consumed downstream by the time it's reversed) -- same
    "debit stock we can't source from a real lot" shape, two different triggers.
    """
    lote = StockCongelado(
        producto_congelado_id=producto_congelado_id,
        cantidad=cantidad,
        fecha_entrada=fecha,
        is_active=True,
        notas=notas,
    )
    db.add(lote)
    db.flush()  # caller needs lote.id immediately for a ConsumoFifoDetalle row
    return lote


def deducir_congelado_fifo(
    db: Session,
    producto_congelado_id: int,
    cantidad: float,
    referencia: str,
    user_id: Optional[int] = None,
    fecha: Optional[date] = None,
    tipo_movimiento: str = "entrega_b2b",
) -> MovimientoStock:
    restante = cantidad
    entries = (
        db.query(StockCongelado)
        .filter(
            StockCongelado.producto_congelado_id == producto_congelado_id,
            StockCongelado.is_active.is_(True),
            StockCongelado.cantidad > 0,
        )
        .order_by(StockCongelado.fecha_entrada)
        .all()
    )

    # Remember which lots we drew from, so a reversal can put the quantity back
    # on the same lots instead of creating a new one with today's date.
    tomado: list[tuple[StockCongelado, float]] = []

    for entry in entries:
        if restante <= 0:
            break
        if entry.cantidad <= restante:
            tomado.append((entry, entry.cantidad))
            restante -= entry.cantidad
            entry.cantidad = 0
            entry.is_active = False
        else:
            tomado.append((entry, restante))
            entry.cantidad -= restante
            restante = 0

    # Session is autoflush=False: the lot updates above are only pending in the
    # ORM until flushed, so get_saldo_congelado() would otherwise read the
    # pre-consumption balance (same class of bug fixed in deducir_materia_prima).
    db.flush()

    # Deliberately unclamped: when real lots don't cover the full request, book
    # the remainder on a synthetic negative lot instead of dropping it. That
    # makes the shortfall a visible negative balance (someone forgot to record
    # a production run) instead of silently vanishing at zero, and keeps the
    # ledger movement equal to the full theoretical demand -- not just what a
    # real lot happened to cover.
    notas = None
    if restante > 1e-9:
        notas = f"Stock insuficiente: se pidieron {cantidad:.3f}, habia {cantidad - restante:.3f}. Faltante: {restante:.3f}."
        ajuste = crear_lote_ajuste(db, producto_congelado_id, -restante, fecha or date.today(), notas)
        tomado.append((ajuste, restante))
        restante = 0

    saldo = get_saldo_congelado(db, producto_congelado_id)
    mov = registrar_movimiento(
        db, "congelado", producto_congelado_id, -cantidad, "u",
        tipo_movimiento, referencia, saldo, user_id, notas=notas, fecha=fecha,
    )

    if tomado:
        db.flush()  # need mov.id and any freshly-created lot ids
        for entry, tomado_de_lote in tomado:
            db.add(ConsumoFifoDetalle(
                movimiento_stock_id=mov.id,
                stock_congelado_id=entry.id,
                cantidad=tomado_de_lote,
            ))

    return mov


def _tiene_stock_propio(db: Session, receta_id: int) -> bool:
    """True if a recipe is produced/stocked on its own (has a ProductoCongelado).

    Subrecetas like Masa de Croissant already get their ingredients deducted
    when THEY are produced, so a bastón/terminado line pointing at them must
    not deduct ingredients again -- that consumption already happened.
    """
    return (
        db.query(ProductoCongelado)
        .filter(ProductoCongelado.receta_id == receta_id, ProductoCongelado.is_active.is_(True))
        .first()
        is not None
    )


def _es_ancestro_congelado(db: Session, producto_id: int, candidato_id: int) -> bool:
    """True if candidato_id is somewhere in producto_id's producto_padre_id chain.

    The cost graph (lineas_receta.subreceta_id) and the physical stock chain
    (producto_padre_id) don't always match level-for-level: a terminado's recipe
    often references a baston directly for cost rollup, while its actual padre
    is an intermediate crudo whose own padre is that same baston. Without this
    check, producing the terminado would deduct the baston's stock a second time
    on top of what producing the crudo already took.
    """
    visto = set()
    actual = producto_id
    while actual and actual not in visto:
        visto.add(actual)
        prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == actual).first()
        if not prod or not prod.producto_padre_id:
            return False
        if prod.producto_padre_id == candidato_id:
            return True
        actual = prod.producto_padre_id
    return False


def _consumir_ingredientes_subreceta(
    db: Session,
    receta_id: int,
    cantidad_necesaria: float,
    unidad_necesaria: str,
    referencia: str,
    user_id: Optional[int],
    fecha: date,
    movimientos: list[MovimientoStock],
    visited: set[int],
) -> None:
    """Deduct raw ingredients for a subreceta with no stock of its own (e.g. Masa Madre).

    Recurses through nested subreceta lines the same way, stopping at any
    subreceta that DOES have its own stock (already handled elsewhere).
    """
    if receta_id in visited:
        return
    visited.add(receta_id)

    receta = db.query(Receta).filter(Receta.id == receta_id).first()
    if not receta or not receta.porciones_por_lote:
        return

    rendimiento_unidad = receta.unidad_rendimiento or unidad_necesaria
    cantidad_en_rendimiento = convertir(cantidad_necesaria, unidad_necesaria, rendimiento_unidad)
    lotes = cantidad_en_rendimiento / receta.porciones_por_lote

    lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
    for linea in lineas:
        if linea.ingrediente_id:
            consumo = linea.cantidad * lotes
            mov = deducir_materia_prima(
                db, linea.ingrediente_id, consumo, linea.unidad, referencia, user_id, fecha=fecha,
                origen_subreceta=receta.nombre,
            )
            if mov:
                movimientos.append(mov)
        elif linea.subreceta_id and not _tiene_stock_propio(db, linea.subreceta_id):
            consumo = linea.cantidad * lotes
            _consumir_ingredientes_subreceta(
                db, linea.subreceta_id, consumo, linea.unidad, referencia, user_id, fecha,
                movimientos, visited,
            )


def producir_producto(
    db: Session,
    producto_congelado_id: int,
    cantidad_producida: float,
    lotes: float,
    bastones_consumidos: Optional[float],
    referencia: str,
    user_id: Optional[int] = None,
    fecha_produccion: Optional[date] = None,
    registro_produccion_id: Optional[int] = None,
) -> list[MovimientoStock]:
    """
    Register production of a product. Handles the full chain:

    1. If product has receta_id with ingredient lines -> auto-deduct from Stock MP,
       scaled by `lotes` (how many full recipe batches this represents -- see
       lotes_de_receta() in produccion_registro.py; NOT derived from
       cantidad_producida here, since for some recipes (masas) those two numbers
       are the same and for others (terminados) they aren't)
    2. If product has producto_padre_id:
       - If padre is a baston -> use bastones_consumidos (manual input)
       - Otherwise -> auto-calculate from cantidad_producida / cantidad_por_padre
       Deducts from padre's StockCongelado
    3. Adds produced quantity (cantidad_producida, in this product's own unit) to
       its StockCongelado
    """
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == producto_congelado_id).first()
    if not prod:
        return []

    movimientos: list[MovimientoStock] = []

    fecha = fecha_produccion or date.today()

    # 1. Consume ingredients from Stock MP (if product has a recipe with ingredient lines)
    if prod.receta_id:
        receta = db.query(Receta).filter(Receta.id == prod.receta_id).first()
        if receta:
            lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
            for linea in lineas:
                if linea.ingrediente_id:
                    consumo = linea.cantidad * lotes
                    mov = deducir_materia_prima(
                        db, linea.ingrediente_id, consumo, linea.unidad, referencia, user_id, fecha=fecha
                    )
                    if mov:
                        movimientos.append(mov)
                elif linea.subreceta_id and not _tiene_stock_propio(db, linea.subreceta_id):
                    consumo = linea.cantidad * lotes
                    _consumir_ingredientes_subreceta(
                        db, linea.subreceta_id, consumo, linea.unidad, referencia, user_id, fecha,
                        movimientos, visited={receta.id},
                    )
                elif linea.subreceta_id and _tiene_stock_propio(db, linea.subreceta_id):
                    sub_prod = (
                        db.query(ProductoCongelado)
                        .filter(
                            ProductoCongelado.receta_id == linea.subreceta_id,
                            ProductoCongelado.is_active.is_(True),
                        )
                        .first()
                    )
                    if sub_prod and not _es_ancestro_congelado(db, prod.id, sub_prod.id):
                        consumo = linea.cantidad * lotes
                        mov = deducir_congelado_fifo(
                            db, sub_prod.id, consumo, referencia, user_id, fecha=fecha,
                            tipo_movimiento="produccion_consumo",
                        )
                        if mov:
                            movimientos.append(mov)

    # 2. Consume from parent product's StockCongelado
    if prod.producto_padre_id and prod.cantidad_por_padre:
        padre = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod.producto_padre_id).first()
        if padre:
            is_baston = padre.nivel == "semi" and "baston" in padre.nombre.lower()
            if is_baston and bastones_consumidos is not None:
                consumo_padre = bastones_consumidos
            else:
                consumo_padre = cantidad_producida / prod.cantidad_por_padre

            mov = deducir_congelado_fifo(
                db, padre.id, consumo_padre, referencia, user_id, fecha=fecha,
                tipo_movimiento="produccion_consumo",
            )
            if mov:
                movimientos.append(mov)

    # 3. Add produced quantity to StockCongelado
    entry = StockCongelado(
        producto_congelado_id=prod.id,
        cantidad=cantidad_producida,
        fecha_entrada=fecha,
        is_active=True,
        notas=f"Produccion: {referencia}",
        registro_produccion_id=registro_produccion_id,
    )
    db.add(entry)

    saldo = get_saldo_congelado(db, prod.id) + cantidad_producida
    mov = registrar_movimiento(
        db, "congelado", prod.id, +cantidad_producida, prod.unidad,
        "produccion_salida", referencia, saldo, user_id, fecha=fecha,
    )
    movimientos.append(mov)

    return movimientos


def _unico_terminado_descendiente(db: Session, producto: "ProductoCongelado") -> Optional["ProductoCongelado"]:
    """The single terminado reachable by walking down producto_padre_id children.

    Returns None if the chain branches into more than one terminado (ambiguous --
    caller should not guess) or dead-ends without one.
    """
    encontrados: list[ProductoCongelado] = []
    nivel_actual = [producto]
    visitados = {producto.id}
    while nivel_actual:
        siguiente = []
        for p in nivel_actual:
            hijos = db.query(ProductoCongelado).filter(
                ProductoCongelado.producto_padre_id == p.id,
                ProductoCongelado.is_active.is_(True),
            ).all()
            for h in hijos:
                if h.id in visitados:
                    continue
                visitados.add(h.id)
                if h.nivel == "terminado":
                    encontrados.append(h)
                else:
                    siguiente.append(h)
        nivel_actual = siguiente
    return encontrados[0] if len(encontrados) == 1 else None


def deducir_congelado_por_catalogo(
    db: Session,
    producto_catalogo_id: int,
    cantidad: float,
    referencia: str,
    tipo_movimiento: str = "entrega_b2b",
    user_id: Optional[int] = None,
    fecha: Optional[date] = None,
) -> Optional[MovimientoStock]:
    cat = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == producto_catalogo_id).first()
    if not cat or not cat.receta_id:
        return None

    candidatos = (
        db.query(ProductoCongelado)
        .filter(
            ProductoCongelado.receta_id == cat.receta_id,
            ProductoCongelado.is_active.is_(True),
        )
        .all()
    )
    prod_cong = next((p for p in candidatos if p.nivel == "terminado"), None)
    if not prod_cong and candidatos:
        # No terminado shares this receta_id directly -- e.g. Ensaimadas Cocinado
        # needs no recipe of its own (baking adds no ingredients), so only the
        # masa (Ensaimada Amasada) carries receta_id=17. A catalog sale must
        # still come off the finished good, so walk down the production chain
        # from whatever matched. Only used when it resolves to exactly one
        # terminado -- a branching chain (one masa feeding several distinct
        # terminados, each with its own receta_id already) is left alone rather
        # than guessed at.
        prod_cong = _unico_terminado_descendiente(db, candidatos[0])
    if not prod_cong:
        return None

    return deducir_congelado_fifo(
        db, prod_cong.id, cantidad, referencia, user_id, fecha=fecha,
        tipo_movimiento=tipo_movimiento,
    )


def revertir_consumos(
    db: Session,
    referencia: str,
    user_id: Optional[int] = None,
    fecha: Optional[date] = None,
) -> int:
    """Give back everything consumed under `referencia`. Returns movements reversed.

    Used wherever a stock-consuming record can be deleted or edited: production,
    mermas, B2B deliveries. Only handles consumption — production OUTPUT is
    reversed by the caller that knows which lot it created.

    The originals are kept and re-tagged to `{referencia}:rev` alongside a
    compensating movement, so the ledger nets to zero (stock charts sum
    MovimientoStock) and the live tag is freed for a re-apply.

    Pass the record's own date, not today: get_saldo_materia_prima picks the
    latest InventarioRegistro by (fecha_registro, id), so a today-dated give-back
    would outrank a backdated re-apply and hide the corrected consumption.
    """
    movimientos = (
        db.query(MovimientoStock)
        .filter(MovimientoStock.referencia_origen == referencia)
        .all()
    )
    if not movimientos:
        return 0

    rev_ref = f"{referencia}:rev"
    f = fecha or date.today()
    revertidos = 0

    for mov in movimientos:
        devuelto = -mov.cantidad  # consumption is stored negative
        if devuelto < 0:
            continue  # a positive-cantidad output row; caller deals with those

        # devuelto == 0 still needs retagging even though there's nothing to
        # restore -- a shortage that was once fully clamped to zero recorded a
        # real (if empty) consumption row. Skipping it here (as `<= 0` used to)
        # left it permanently un-retagged: a later reprocess creates a fresh
        # movement under the same referencia_origen without ever superseding
        # this one, so the stale "0" sits in activity feeds forever alongside
        # the corrected entry.

        if mov.tipo_stock == "materia_prima":
            saldo = get_saldo_materia_prima(db, mov.referencia_producto_id) + devuelto
            db.add(InventarioRegistro(
                ingrediente_id=mov.referencia_producto_id,
                cantidad=saldo,
                unidad=mov.unidad,
                fecha_registro=f,
                notas=f"Reversion de {referencia} (+{devuelto:.3f})",
            ))
        else:
            _restaurar_lotes(db, mov, devuelto, f)
            db.flush()  # autoflush=False -- the read below must see the just-restored lots
            saldo = get_saldo_congelado(db, mov.referencia_producto_id)

        # Same tipo_movimiento as what it cancels, so reports that bucket by type
        # (dashboard reconciliation) net it out instead of ignoring it.
        registrar_movimiento(
            db, mov.tipo_stock, mov.referencia_producto_id, devuelto, mov.unidad,
            mov.tipo_movimiento, rev_ref, saldo, user_id,
            notas=f"Reversion de {referencia}", fecha=f,
        )
        mov.referencia_origen = rev_ref
        revertidos += 1

    db.flush()
    return revertidos


def _restaurar_lotes(db: Session, mov: MovimientoStock, devuelto: float, fecha: date) -> None:
    """Put a FIFO consumption back on the exact lots it drew from."""
    detalles = (
        db.query(ConsumoFifoDetalle)
        .filter(ConsumoFifoDetalle.movimiento_stock_id == mov.id)
        .all()
    )
    if detalles:
        for det in detalles:
            lote = db.get(StockCongelado, det.stock_congelado_id)
            if lote:
                lote.cantidad += det.cantidad
                if lote.cantidad > 1e-9:
                    lote.is_active = True
            db.delete(det)
    else:
        # Written before per-lot detail existed — a fresh lot is the best we can do.
        db.add(StockCongelado(
            producto_congelado_id=mov.referencia_producto_id,
            cantidad=devuelto,
            fecha_entrada=fecha,
            is_active=True,
            notas=f"Reversion de {mov.referencia_origen} (lote reconstruido)",
        ))


def _revertir_correccion_conteo(db: Session, referencia: str, user_id: Optional[int]) -> None:
    """Undo a previous manual-count correction filed under `referencia`, if any.

    Same retag-and-compensate shape as revertir_consumos, but a count
    correction can be either sign (a recount can go up or down), so it can't
    reuse that function directly -- revertir_consumos silently skips any
    positive-cantidad row, assuming it's production output someone else owns
    the reversal of.

    Dates the compensating entry at the ORIGINAL correction's own `mov.fecha`,
    not whatever date the new edit is using -- a reversed pair must share a
    date to cancel out for any "balance as of X" window between the two, in
    case the edit that triggered this reversal also moved the row to a
    different date.
    """
    existentes = db.query(MovimientoStock).filter(MovimientoStock.referencia_origen == referencia).all()
    for mov in existentes:
        registrar_movimiento(
            db, mov.tipo_stock, mov.referencia_producto_id, -mov.cantidad, mov.unidad,
            mov.tipo_movimiento, f"{referencia}:rev", None, user_id,
            notas=f"Reversion de {referencia}", fecha=mov.fecha,
        )
        mov.referencia_origen = f"{referencia}:rev"
    if existentes:
        db.flush()


def ajustar_correccion_conteo(
    db: Session,
    tipo_stock: str,
    producto_id: int,
    registro_id: int,
    nueva_cantidad: float,
    unidad: str,
    fecha: date,
    user_id: Optional[int] = None,
) -> Optional[MovimientoStock]:
    """Correct the ledger so its running balance as of `fecha` equals
    `nueva_cantidad` -- the corrected value of an edited historical manual
    count.

    Tied 1:1 to the manual-count row being edited via a stable referencia
    (`correccion_conteo:{tipo_stock}:{registro_id}`), so re-editing that same
    row later finds and reverses THIS correction first, then sizes the fresh
    one against the ledger as it stands once that's undone -- never against
    the row's own previous value. That distinction matters: a plain
    `nueva - vieja` delta would be correct on the very first edit but wrong
    on every edit after that, since the prior correction is fully backed out
    (not superseded) before the new one is computed. Never mutates an
    existing MovimientoStock row -- only appends, same as every other
    reversal in this file.

    Also the right tool for a genuinely NEW baseline (an item that's never
    had a `carga_inicial` run for it): with no correction to revert and no
    other movements yet, `nueva_cantidad - 0` is exactly what
    scripts/reconciliar_ledger_*.py would have inserted by hand.

    Only call this from an EDIT of an existing count, never from creating a
    new one: a fresh count is deliberately left un-ledgered (see
    es_conteo_manual's docstring) so a genuine discrepancy -- a bug in
    production/merma deduction -- stays visible instead of silently
    reconciling itself the moment someone recounts.

    Exception to "never mutate a MovimientoStock row": if the ONLY movement
    on or before `fecha` is a lone `carga_inicial` DATED ON THE SAME DAY AS
    `fecha`, it gets edited in place instead of leaving a correction next to
    it. A carga_inicial was never a real event -- it's just our best guess
    at history when the item was set up (see scripts/reconciliar_ledger_*.py)
    -- so fixing a typo in it isn't erasing evidence of anything real, and
    the ledger reads as one clean correct number instead of "+220 / -219.78"
    forever. The instant a real movement (production/merma/entrega/recepcion)
    exists on or before this date, this can't apply -- rewriting a real
    event would be exactly the "hand-edit the ledger to make a discrepancy
    disappear" this file's other reversal functions all exist to avoid.

    The same-day check matters even when carga_inicial IS the only prior
    movement: editing a LATER count (say, correcting the 20th) with nothing
    real between the 13th's carga_inicial and the 20th would otherwise match
    "only one prior movement" and silently overwrite the 13th's baseline
    with the 20th's corrected value -- fixing one date by corrupting a
    different one. Without a same-day match this falls through to the
    append-only path below, which is always safe: it only ever shifts the
    balance from `fecha` forward, never rewrites an earlier date.
    """
    referencia = f"correccion_conteo:{tipo_stock}:{registro_id}"
    _revertir_correccion_conteo(db, referencia, user_id)

    # Excludes this row's own correction history (live or already reverted):
    # a prior edit's leftover rows aren't an independent real event, so they
    # shouldn't be what stands between a re-edited row and the clean
    # direct-edit path above -- re-correcting the same mistake a second time
    # should collapse right back to editing the carga_inicial in place, same
    # as the first time, as long as nothing ELSE real has happened since.
    previos = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.tipo_stock == tipo_stock,
            MovimientoStock.referencia_producto_id == producto_id,
            MovimientoStock.fecha <= fecha,
            MovimientoStock.referencia_origen != referencia,
            MovimientoStock.referencia_origen != f"{referencia}:rev",
        )
        .all()
    )
    if len(previos) == 1 and previos[0].tipo_movimiento == "carga_inicial" and previos[0].fecha == fecha:
        base = previos[0]
        base.cantidad = nueva_cantidad
        base.unidad = unidad
        base.saldo_despues = nueva_cantidad
        base.registrado_por = user_id
        base.registrado_at = datetime.now(timezone.utc)
        db.flush()
        return base

    ledger_actual = sum(m.cantidad for m in previos)
    delta = nueva_cantidad - ledger_actual
    if abs(delta) < 1e-9:
        return None
    mov = registrar_movimiento(
        db, tipo_stock, producto_id, delta, unidad, "correccion_conteo",
        referencia, nueva_cantidad, user_id, fecha=fecha,
        notas=f"Correccion de conteo manual (registro #{registro_id})",
    )
    # Session is autoflush=False: without this, calling this function twice
    # for the same registro_id in one transaction (no commit in between) --
    # exactly what a caller with its own commit-per-call, like the tests
    # here, does NOT hit, but a future bulk-sync caller might -- would have
    # _revertir_correccion_conteo's next lookup miss this row entirely.
    db.flush()
    return mov
