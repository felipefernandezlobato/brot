"""Stock effects for production records.

Every stock movement caused by production hangs off a RegistroProduccion row and
is tagged `registro_produccion:{id}`. That tag is what makes an edit reversible:
we undo whatever is filed under it, then re-apply from the new values.

Deviation from the pedidos.py reversal convention, on purpose: pedidos deletes the
original MovimientoStock rows *and* inserts a compensating one, which leaves the
ledger summing to -original instead of zero. Stock charts are built by summing
MovimientoStock (see CLAUDE.md), so here we keep the original rows, add the
compensating movement, and re-tag both to `{ref}:rev`. The sum nets to zero, the
audit trail survives, and the live tag is freed for the next apply.
"""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    ConsumoFifoDetalle,
    InventarioRegistro,
    MovimientoStock,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    StockCongelado,
)
from app.services.stock import (
    get_saldo_congelado,
    get_saldo_materia_prima,
    producir_producto,
    registrar_movimiento,
)

EPSILON = 1e-9


def referencia_de(reg: RegistroProduccion) -> str:
    return f"registro_produccion:{reg.id}"


def tiene_efectos_stock(db: Session, referencia: str) -> bool:
    return (
        db.query(MovimientoStock.id)
        .filter(MovimientoStock.referencia_origen == referencia)
        .first()
        is not None
    )


def cantidad_en_porciones(db: Session, reg: RegistroProduccion) -> float:
    """Translate what the operator typed into what producir_producto expects.

    producir_producto works in PORTIONS (it divides by receta.porciones_por_lote).
    Tasks ask the operator for "u receta" — whole batches. Without this conversion,
    typing "1 receta" for Masa Croissant (porciones_por_lote=9) deducted a ninth of
    the recipe.
    """
    cantidad = reg.cantidad_real or 0.0

    unidad = None
    receta_id = reg.receta_id
    if reg.tarea_id and reg.tarea:
        unidad = reg.tarea.unidad_cantidad
        receta_id = reg.tarea.receta_id or receta_id

    if unidad != "u receta" or not receta_id:
        return cantidad

    receta = db.query(Receta).filter(Receta.id == receta_id).first()
    if receta and receta.porciones_por_lote:
        return cantidad * receta.porciones_por_lote
    return cantidad


def resolver_producto_congelado(db: Session, reg: RegistroProduccion) -> Optional[int]:
    """Which frozen product this record produces, if any."""
    if reg.producto_congelado_id:
        return reg.producto_congelado_id
    if reg.tarea_id and reg.tarea and reg.tarea.producto_congelado_id:
        return reg.tarea.producto_congelado_id
    if reg.receta_id:
        prod = (
            db.query(ProductoCongelado)
            .filter(ProductoCongelado.receta_id == reg.receta_id)
            .first()
        )
        if prod:
            return prod.id
    return None


def aplicar_efectos(db: Session, reg: RegistroProduccion, user_id: int) -> int:
    """Apply this record's stock effects. Returns how many movements were written."""
    if not reg.completada or not reg.cantidad_real or reg.cantidad_real <= 0:
        return 0

    producto_id = resolver_producto_congelado(db, reg)
    if not producto_id:
        return 0  # cleaning, notes, tasks with no product — nothing to move

    ref = referencia_de(reg)
    if tiene_efectos_stock(db, ref):
        return 0  # already applied; caller should revert first

    reg.producto_congelado_id = producto_id
    movimientos = producir_producto(
        db,
        producto_id,
        cantidad_en_porciones(db, reg),
        reg.bastones_consumidos,
        ref,
        user_id,
        fecha_produccion=reg.fecha,
        registro_produccion_id=reg.id,
    )
    return len(movimientos)


def revertir_efectos(db: Session, reg: RegistroProduccion, user_id: int) -> int:
    """Undo this record's stock effects. Never blocks and never fails.

    If the produced batch was already consumed downstream, the shortfall is booked
    as an explicit negative adjustment so the net total stays correct — reversing 9
    and re-applying 18 leaves 9 on hand even when the original 9 are already gone.
    """
    ref = referencia_de(reg)
    movimientos = (
        db.query(MovimientoStock)
        .filter(MovimientoStock.referencia_origen == ref)
        .all()
    )
    if not movimientos:
        return 0

    rev_ref = f"{ref}:rev"
    # Date the reversal to the production it undoes, never to today. get_saldo_*
    # picks the latest InventarioRegistro by (fecha_registro, id) — a today-dated
    # give-back would outrank the same-transaction re-apply dated reg.fecha and the
    # corrected consumption would become invisible. Same-dated, id order decides,
    # and the re-apply wins because it is inserted second.
    fecha_rev = reg.fecha

    for mov in movimientos:
        if mov.tipo_stock == "materia_prima":
            _revertir_materia_prima(db, mov, ref, rev_ref, user_id, fecha_rev)
        elif mov.tipo_movimiento == "produccion_consumo":
            _revertir_consumo_congelado(db, mov, rev_ref, user_id, fecha_rev)
        elif mov.tipo_movimiento == "produccion_salida":
            _revertir_salida_congelado(db, reg, mov, rev_ref, user_id, fecha_rev)

        # Keep the original for the audit trail but free the live tag, so the
        # ledger nets to zero and the next apply starts clean.
        mov.referencia_origen = rev_ref

    # Push the re-tag out now: aplicar_efectos queries for the live tag straight
    # after this, and the session may not autoflush.
    db.flush()

    return len(movimientos)


def _revertir_materia_prima(db, mov, ref, rev_ref, user_id, fecha) -> None:
    saldo_actual = get_saldo_materia_prima(db, mov.referencia_producto_id)
    devuelto = -mov.cantidad  # stored negative, so this is positive
    nuevo_saldo = saldo_actual + devuelto

    db.add(InventarioRegistro(
        ingrediente_id=mov.referencia_producto_id,
        cantidad=nuevo_saldo,
        unidad=mov.unidad,
        fecha_registro=fecha,
        notas=f"Reversion de {ref} (+{devuelto:.3f})",
    ))
    # Same tipo_movimiento as the consumption it cancels, so every report that
    # buckets by tipo_movimiento (dashboard reconciliation) nets it out.
    registrar_movimiento(
        db, "materia_prima", mov.referencia_producto_id, devuelto, mov.unidad,
        "produccion_consumo", rev_ref, nuevo_saldo, user_id,
        notas="Reversion de produccion", fecha=fecha,
    )


def _revertir_consumo_congelado(db, mov, rev_ref, user_id, fecha) -> None:
    detalles = (
        db.query(ConsumoFifoDetalle)
        .filter(ConsumoFifoDetalle.movimiento_stock_id == mov.id)
        .all()
    )
    devuelto = -mov.cantidad

    if detalles:
        # Put each lot back exactly as it was, preserving fecha_entrada and FIFO order.
        for det in detalles:
            lote = db.get(StockCongelado, det.stock_congelado_id)
            if lote:
                lote.cantidad += det.cantidad
                if lote.cantidad > EPSILON:
                    lote.is_active = True
            db.delete(det)
    elif devuelto > EPSILON:
        # Legacy movement with no per-lot detail — best we can do is a fresh lot.
        db.add(StockCongelado(
            producto_congelado_id=mov.referencia_producto_id,
            cantidad=devuelto,
            fecha_entrada=fecha,
            is_active=True,
            notas="Reversion de produccion (lote reconstruido)",
        ))

    saldo = get_saldo_congelado(db, mov.referencia_producto_id)
    registrar_movimiento(
        db, "congelado", mov.referencia_producto_id, devuelto, mov.unidad,
        "produccion_consumo", rev_ref, saldo, user_id,
        notas="Reversion de produccion", fecha=fecha,
    )


def _revertir_salida_congelado(db, reg, mov, rev_ref, user_id, fecha) -> None:
    a_quitar = mov.cantidad  # stored positive

    lote = (
        db.query(StockCongelado)
        .filter(
            StockCongelado.registro_produccion_id == reg.id,
            StockCongelado.producto_congelado_id == mov.referencia_producto_id,
        )
        .first()
    )
    if lote:
        quita = min(max(lote.cantidad, 0.0), a_quitar)
        lote.cantidad -= quita
        a_quitar -= quita
        # Zero the lot but never delete it: ConsumoFifoDetalle rows from a later
        # production may still reference it, and dropping the row would either break
        # the FK or orphan the detail and lose that stock on a future reversal.
        if lote.cantidad <= EPSILON:
            lote.is_active = False
        lote.registro_produccion_id = None

    if a_quitar > EPSILON:
        # The batch was already consumed downstream. Book the shortfall explicitly
        # so the running total stays honest rather than silently over-counting.
        db.add(StockCongelado(
            producto_congelado_id=mov.referencia_producto_id,
            cantidad=-a_quitar,
            fecha_entrada=reg.fecha,
            is_active=True,
            notas="Ajuste por reversion: la produccion ya se habia consumido",
        ))

    saldo = get_saldo_congelado(db, mov.referencia_producto_id)
    registrar_movimiento(
        db, "congelado", mov.referencia_producto_id, -mov.cantidad, mov.unidad,
        "produccion_salida", rev_ref, saldo, user_id,
        notas="Reversion de produccion", fecha=fecha,
    )
