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


def get_saldo_congelado(db: Session, producto_congelado_id: int) -> float:
    total = (
        db.query(func.sum(StockCongelado.cantidad))
        .filter(
            StockCongelado.producto_congelado_id == producto_congelado_id,
            StockCongelado.is_active.is_(True),
        )
        .scalar()
    )
    return total or 0.0


def deducir_materia_prima(
    db: Session,
    ingrediente_id: int,
    cantidad: float,
    unidad_receta: str,
    referencia: str,
    user_id: Optional[int] = None,
    fecha: Optional[date] = None,
) -> MovimientoStock:
    ing = db.query(Ingrediente).filter(Ingrediente.id == ingrediente_id).first()
    if not ing:
        return None

    consumo = convertir(cantidad, unidad_receta, ing.unidad_uso)
    saldo_actual = get_saldo_materia_prima(db, ingrediente_id)
    nuevo_saldo = max(0.0, saldo_actual - consumo)

    # Record the movement the balance ACTUALLY moved, not the theoretical demand.
    # When stock is insufficient the balance clamps at zero; storing the unclamped
    # figure here would make a later reversal add back stock that never left.
    consumo_real = saldo_actual - nuevo_saldo
    faltante = consumo - consumo_real

    db.add(InventarioRegistro(
        ingrediente_id=ingrediente_id,
        cantidad=nuevo_saldo,
        unidad=ing.unidad_uso,
        fecha_registro=fecha or date.today(),
        notas=f"Consumo automatico: {referencia}",
    ))

    notas = None
    if faltante > 1e-9:
        notas = (
            f"Stock insuficiente: la receta pedia {consumo:.3f} {ing.unidad_uso}, "
            f"habia {saldo_actual:.3f}. Faltante: {faltante:.3f}."
        )

    return registrar_movimiento(
        db, "materia_prima", ingrediente_id, -consumo_real, ing.unidad_uso,
        "produccion_consumo", referencia, nuevo_saldo, user_id, notas=notas, fecha=fecha,
    )


def deducir_congelado_fifo(
    db: Session,
    producto_congelado_id: int,
    cantidad: float,
    referencia: str,
    user_id: Optional[int] = None,
    fecha: Optional[date] = None,
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

    saldo = get_saldo_congelado(db, producto_congelado_id)
    mov = registrar_movimiento(
        db, "congelado", producto_congelado_id, -cantidad, "u",
        "produccion_consumo" if "produccion" in referencia else "entrega_b2b",
        referencia, saldo, user_id, fecha=fecha,
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


def producir_producto(
    db: Session,
    producto_congelado_id: int,
    cantidad_producida: float,
    bastones_consumidos: Optional[float],
    referencia: str,
    user_id: Optional[int] = None,
    fecha_produccion: Optional[date] = None,
    registro_produccion_id: Optional[int] = None,
) -> list[MovimientoStock]:
    """
    Register production of a product. Handles the full chain:

    1. If product has receta_id with ingredient lines -> auto-deduct from Stock MP
    2. If product has producto_padre_id:
       - If padre is a baston -> use bastones_consumidos (manual input)
       - Otherwise -> auto-calculate from cantidad_producida / cantidad_por_padre
       Deducts from padre's StockCongelado
    3. Adds produced quantity to this product's StockCongelado
    """
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == producto_congelado_id).first()
    if not prod:
        return []

    movimientos: list[MovimientoStock] = []

    fecha = fecha_produccion or date.today()

    # 1. Consume ingredients from Stock MP (if product has a recipe with ingredient lines)
    if prod.receta_id:
        receta = db.query(Receta).filter(Receta.id == prod.receta_id).first()
        if receta and receta.porciones_por_lote:
            lotes = cantidad_producida / receta.porciones_por_lote
            lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
            for linea in lineas:
                if linea.ingrediente_id:
                    consumo = linea.cantidad * lotes
                    mov = deducir_materia_prima(
                        db, linea.ingrediente_id, consumo, linea.unidad, referencia, user_id, fecha=fecha
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
                db, padre.id, consumo_padre, referencia, user_id, fecha=fecha
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

    prod_cong = (
        db.query(ProductoCongelado)
        .filter(ProductoCongelado.receta_id == cat.receta_id)
        .first()
    )
    if not prod_cong:
        return None

    return deducir_congelado_fifo(db, prod_cong.id, cantidad, referencia, user_id, fecha=fecha)


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
        if devuelto <= 0:
            continue  # not a consumption; caller deals with outputs

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
