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

from sqlalchemy import or_
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


def movimiento_no_revertido():
    """SQLAlchemy filter clause: excludes movements superseded by a reversal.

    A reversed movement and its compensating give-back BOTH end up tagged
    `{referencia}:rev` (see the module docstring above) -- e.g. editing "1.5"
    down to a corrected value leaves "+1.5 Producido" / "-1.5 Producido" sitting
    in the ledger forever, net zero but nonsensical to read in an activity list
    ("-13.5 Producido"?). Recent-activity displays should use this; sums used
    for reconciliation are fine either way since a reversed pair always nets
    to zero.
    """
    return or_(
        MovimientoStock.referencia_origen.is_(None),
        ~MovimientoStock.referencia_origen.like("%:rev"),
    )


def referencia_de(reg: RegistroProduccion) -> str:
    return f"registro_produccion:{reg.id}"


def tiene_efectos_stock(db: Session, referencia: str) -> bool:
    return (
        db.query(MovimientoStock.id)
        .filter(MovimientoStock.referencia_origen == referencia)
        .first()
        is not None
    )


def lotes_de_receta(db: Session, reg: RegistroProduccion) -> float:
    """How many full recipe batches this record represents, for scaling ingredient lines.

    Two different things get called "cantidad" depending on the task:
      - "u receta" tasks (Masa de Croissant/Medialuna/Hojaldre): the operator
        enters batches directly ("1.5" means 1.5 lotes). That IS the lotes
        count already -- for these, `u` of physical stock also means "lotes",
        not "portions" (1.5u of masa stays 1.5u of masa; it becomes 13.5
        bastones only once combined with butter downstream).
      - Everything else (e.g. "6" croissants): the operator enters a count of
        finished pieces, so lotes = pieces / porciones_por_lote.
    Getting this wrong previously inflated a masa's own stock by porciones_por_lote
    (1.5 lotes recorded as 13.5) while fixing ingredient deduction only by accident.
    """
    cantidad = reg.cantidad_real or 0.0

    unidad = None
    receta_id = reg.receta_id
    if reg.tarea_id and reg.tarea:
        unidad = reg.tarea.unidad_cantidad
        receta_id = reg.tarea.receta_id or receta_id

    if unidad == "u receta" or not receta_id:
        return cantidad

    receta = db.query(Receta).filter(Receta.id == receta_id).first()
    if receta and receta.porciones_por_lote:
        return cantidad / receta.porciones_por_lote
    return cantidad


def describir_referencia(db: Session, referencia_origen: Optional[str]) -> Optional[str]:
    """Human-readable name for a `registro_produccion:{id}` (or its `:rev`) tag.

    Movement tables show this next to "Consumido"/"Producido" so a stock change
    reads as "Consumido para Masa Croissant" instead of a bare quantity.
    """
    if not referencia_origen or not referencia_origen.startswith("registro_produccion:"):
        return None
    reg_id_str = referencia_origen.split(":")[1]
    if not reg_id_str.isdigit():
        return None

    reg = db.query(RegistroProduccion).filter(RegistroProduccion.id == int(reg_id_str)).first()
    if not reg:
        return None

    receta_id = None
    if reg.tarea_id and reg.tarea and reg.tarea.receta_id:
        receta_id = reg.tarea.receta_id
    elif reg.receta_id:
        receta_id = reg.receta_id
    if receta_id:
        receta = db.query(Receta).filter(Receta.id == receta_id).first()
        if receta:
            return receta.nombre

    producto_id = resolver_producto_congelado(db, reg)
    if producto_id:
        producto = db.query(ProductoCongelado).filter(ProductoCongelado.id == producto_id).first()
        if producto:
            return producto.nombre

    if reg.titulo_extra:
        return reg.titulo_extra
    if reg.tarea and reg.tarea.titulo:
        return reg.tarea.titulo
    return None


def nombre_origen_movimiento(db: Session, m: MovimientoStock) -> Optional[str]:
    """Display label for one movement: its own subreceta tag if it has one,
    otherwise the production's recipe/product name.

    A stockless subreceta (e.g. Masa Madre) resolves to its own ingredients at
    the moment it's used inline, so its consumption movements are tagged with
    the subreceta's own name -- see deducir_materia_prima() -- instead of
    inheriting the parent recipe's name from referencia_origen.
    """
    if m.notas and m.notas.startswith("subreceta:"):
        return m.notas[len("subreceta:"):].split(" | ", 1)[0].strip()
    return describir_referencia(db, m.referencia_origen)


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
        reg.cantidad_real,
        lotes_de_receta(db, reg),
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
