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
    MovimientoStock,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    StockCongelado,
)
from app.services.stock import (
    get_saldo_congelado,
    producir_producto,
    registrar_movimiento,
    revertir_consumos,
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
    rev_ref = f"{ref}:rev"

    # Reverse the production output first: revertir_consumos re-tags what it
    # touches, so the output movement must be found while the live tag is intact.
    salidas = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.referencia_origen == ref,
            MovimientoStock.tipo_movimiento == "produccion_salida",
        )
        .all()
    )
    for mov in salidas:
        _revertir_salida_congelado(db, reg, mov, rev_ref, user_id, reg.fecha)
        mov.referencia_origen = rev_ref

    # Dated to the production it undoes, never today — see revertir_consumos.
    return len(salidas) + revertir_consumos(db, ref, user_id, fecha=reg.fecha)


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
