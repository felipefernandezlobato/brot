from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
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
) -> MovimientoStock:
    mov = MovimientoStock(
        tipo_stock=tipo_stock,
        referencia_producto_id=producto_id,
        cantidad=cantidad,
        unidad=unidad,
        tipo_movimiento=tipo_movimiento,
        referencia_origen=referencia_origen,
        saldo_despues=saldo_despues,
        fecha=date.today(),
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
) -> MovimientoStock:
    ing = db.query(Ingrediente).filter(Ingrediente.id == ingrediente_id).first()
    if not ing:
        return None

    consumo = convertir(cantidad, unidad_receta, ing.unidad_uso)
    saldo_actual = get_saldo_materia_prima(db, ingrediente_id)
    nuevo_saldo = max(0.0, saldo_actual - consumo)

    db.add(InventarioRegistro(
        ingrediente_id=ingrediente_id,
        cantidad=nuevo_saldo,
        unidad=ing.unidad_uso,
        fecha_registro=date.today(),
        notas=f"Consumo automatico: {referencia}",
    ))

    return registrar_movimiento(
        db, "materia_prima", ingrediente_id, -consumo, ing.unidad_uso,
        "produccion_consumo", referencia, nuevo_saldo, user_id,
    )


def deducir_congelado_fifo(
    db: Session,
    producto_congelado_id: int,
    cantidad: float,
    referencia: str,
    user_id: Optional[int] = None,
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

    for entry in entries:
        if restante <= 0:
            break
        if entry.cantidad <= restante:
            restante -= entry.cantidad
            entry.cantidad = 0
            entry.is_active = False
        else:
            entry.cantidad -= restante
            restante = 0

    saldo = get_saldo_congelado(db, producto_congelado_id)
    return registrar_movimiento(
        db, "congelado", producto_congelado_id, -cantidad, "u",
        "produccion_consumo" if "produccion" in referencia else "entrega_b2b",
        referencia, saldo, user_id,
    )


def deducir_por_receta(
    db: Session,
    receta_id: int,
    cantidad_lotes: float,
    referencia: str,
    user_id: Optional[int] = None,
) -> list[MovimientoStock]:
    receta = db.query(Receta).filter(Receta.id == receta_id).first()
    if not receta:
        return []

    lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == receta_id).all()
    movimientos = []

    for linea in lineas:
        consumo = linea.cantidad * cantidad_lotes

        if linea.ingrediente_id:
            mov = deducir_materia_prima(
                db, linea.ingrediente_id, consumo, linea.unidad, referencia, user_id
            )
            if mov:
                movimientos.append(mov)

        elif linea.subreceta_id:
            prod_cong = (
                db.query(ProductoCongelado)
                .filter(ProductoCongelado.receta_id == linea.subreceta_id)
                .first()
            )
            if prod_cong:
                mov = deducir_congelado_fifo(
                    db, prod_cong.id, consumo, referencia, user_id
                )
                if mov:
                    movimientos.append(mov)

    return movimientos


def registrar_produccion_stock(
    db: Session,
    receta_id: int,
    cantidad_producida: float,
    referencia: str,
    user_id: Optional[int] = None,
) -> Optional[MovimientoStock]:
    prod_cong = (
        db.query(ProductoCongelado)
        .filter(ProductoCongelado.receta_id == receta_id)
        .first()
    )
    if not prod_cong:
        return None

    entry = StockCongelado(
        producto_congelado_id=prod_cong.id,
        cantidad=cantidad_producida,
        fecha_entrada=date.today(),
        is_active=True,
        notas=f"Produccion: {referencia}",
    )
    db.add(entry)

    saldo = get_saldo_congelado(db, prod_cong.id) + cantidad_producida
    return registrar_movimiento(
        db, "congelado", prod_cong.id, +cantidad_producida, "u",
        "produccion_salida", referencia, saldo, user_id,
    )


def deducir_congelado_por_catalogo(
    db: Session,
    producto_catalogo_id: int,
    cantidad: float,
    referencia: str,
    tipo_movimiento: str = "entrega_b2b",
    user_id: Optional[int] = None,
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

    return deducir_congelado_fifo(db, prod_cong.id, cantidad, referencia, user_id)
