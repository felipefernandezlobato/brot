from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    EntregaB2B,
    Ingrediente,
    InventarioRegistro,
    LineaEntregaB2B,
    LineaPedido,
    LineaReceta,
    MermaRegistro,
    MovimientoStock,
    Pedido,
    ProductoCatalogo,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    StockCongelado,
    User,
)
from app.services.conversiones import convertir
from app.services.produccion_registro import movimiento_no_revertido

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/flujo")
def flujo_completo(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not fecha_desde:
        from datetime import timedelta
        fecha_desde = date.today() - timedelta(days=30)
    if not fecha_hasta:
        fecha_hasta = date.today()

    # Compras recibidas en el periodo
    pedidos_recibidos = (
        db.query(func.sum(LineaPedido.cantidad_recibida * LineaPedido.precio_unitario))
        .join(Pedido, Pedido.id == LineaPedido.pedido_id)
        .filter(
            Pedido.estado == "recibido",
            Pedido.fecha_recepcion >= fecha_desde,
            Pedido.fecha_recepcion <= fecha_hasta,
        )
        .scalar()
    ) or 0

    # Stock materia prima actual
    subq = (
        db.query(
            InventarioRegistro.ingrediente_id,
            func.max(InventarioRegistro.id).label("max_id"),
        )
        .group_by(InventarioRegistro.ingrediente_id)
        .subquery()
    )
    stock_mp_rows = (
        db.query(InventarioRegistro, Ingrediente)
        .join(subq, InventarioRegistro.id == subq.c.max_id)
        .join(Ingrediente, Ingrediente.id == InventarioRegistro.ingrediente_id)
        .all()
    )
    stock_mp_valor = sum(
        r.InventarioRegistro.cantidad * i.Ingrediente.precio_compra
        for r, i in [(row, row) for row in stock_mp_rows]
    ) if stock_mp_rows else 0

    # Recalculate properly
    stock_mp_valor = 0
    stock_mp_items = []
    for row in stock_mp_rows:
        reg = row[0]
        ing = row[1]
        valor = reg.cantidad * ing.precio_compra
        stock_mp_valor += valor
        stock_mp_items.append({
            "ingrediente": ing.nombre,
            "cantidad": reg.cantidad,
            "unidad": ing.unidad_uso,
            "valor": round(valor, 2),
        })

    # Produccion en el periodo
    produccion = (
        db.query(RegistroProduccion)
        .filter(
            RegistroProduccion.completada.is_(True),
            RegistroProduccion.fecha >= fecha_desde,
            RegistroProduccion.fecha <= fecha_hasta,
        )
        .all()
    )
    total_producido = sum(r.cantidad_real or 0 for r in produccion)

    # Stock congelado actual — latest entry per product (most recent fecha_entrada)
    latest_cong_subq = (
        db.query(
            StockCongelado.producto_congelado_id,
            func.max(StockCongelado.fecha_entrada).label("max_fecha"),
        )
        .filter(StockCongelado.is_active.is_(True))
        .group_by(StockCongelado.producto_congelado_id)
        .subquery()
    )
    latest_cong_entries = (
        db.query(
            ProductoCongelado.nombre,
            ProductoCongelado.id,
            StockCongelado.cantidad,
        )
        .join(StockCongelado, StockCongelado.producto_congelado_id == ProductoCongelado.id)
        .join(
            latest_cong_subq,
            (StockCongelado.producto_congelado_id == latest_cong_subq.c.producto_congelado_id)
            & (StockCongelado.fecha_entrada == latest_cong_subq.c.max_fecha),
        )
        .all()
    )
    stock_cong: list = [
        type("Row", (), {"nombre": r.nombre, "id": r.id, "total": r.cantidad})()
        for r in latest_cong_entries
    ]
    stock_cong_total = sum(r.total for r in stock_cong)

    # Entregas B2B en el periodo
    entregas_b2b_total = (
        db.query(func.sum(LineaEntregaB2B.cantidad))
        .join(EntregaB2B, EntregaB2B.id == LineaEntregaB2B.entrega_id)
        .filter(
            EntregaB2B.fecha_entrega >= fecha_desde,
            EntregaB2B.fecha_entrega <= fecha_hasta,
        )
        .scalar()
    ) or 0

    # Mermas en el periodo
    mermas_total = (
        db.query(func.sum(MermaRegistro.coste_total))
        .filter(
            MermaRegistro.fecha >= fecha_desde,
            MermaRegistro.fecha <= fecha_hasta,
        )
        .scalar()
    ) or 0

    # Por producto: producido vs entregado vs stock vs merma
    por_producto = []
    for cong in stock_cong:
        prod_cat = (
            db.query(ProductoCatalogo)
            .filter(ProductoCatalogo.receta_id == db.query(ProductoCongelado.receta_id).filter(ProductoCongelado.id == cong.id).scalar())
            .first()
        )
        entregado = 0
        if prod_cat:
            entregado = (
                db.query(func.sum(LineaEntregaB2B.cantidad))
                .join(EntregaB2B, EntregaB2B.id == LineaEntregaB2B.entrega_id)
                .filter(
                    LineaEntregaB2B.producto_id == prod_cat.id,
                    EntregaB2B.fecha_entrega >= fecha_desde,
                    EntregaB2B.fecha_entrega <= fecha_hasta,
                )
                .scalar()
            ) or 0

        por_producto.append({
            "nombre": cong.nombre,
            "stock_congelado": cong.total,
            "entregado": entregado,
        })

    # Movimientos recientes
    movimientos = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.fecha >= fecha_desde,
            MovimientoStock.fecha <= fecha_hasta,
            movimiento_no_revertido(),
        )
        .order_by(MovimientoStock.id.desc())
        .limit(50)
        .all()
    )

    return {
        "periodo": {"desde": str(fecha_desde), "hasta": str(fecha_hasta)},
        "resumen": {
            "comprado_total_ars": round(pedidos_recibidos, 2),
            "stock_mp_valor_ars": round(stock_mp_valor, 2),
            "stock_mp_items": len(stock_mp_items),
            "producido_total_unidades": total_producido,
            "stock_congelado_total": stock_cong_total,
            "entregado_b2b_total": entregas_b2b_total,
            "merma_total_ars": round(mermas_total, 2),
        },
        "stock_materia_prima": stock_mp_items,
        "stock_congelado": [
            {"nombre": c.nombre, "cantidad": c.total} for c in stock_cong
        ],
        "por_producto": por_producto,
        "movimientos_recientes": [
            {
                "id": m.id,
                "tipo_stock": m.tipo_stock,
                "tipo_movimiento": m.tipo_movimiento,
                "cantidad": m.cantidad,
                "referencia_origen": m.referencia_origen,
                "fecha": m.fecha,
                "saldo_despues": m.saldo_despues,
            }
            for m in movimientos
        ],
    }


@router.get("/reconciliacion")
def reconciliacion_stock(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compare physical stock count vs calculated stock for each ingredient.

    When fecha_desde/fecha_hasta are provided, uses the stock snapshot at fecha_desde
    as the baseline and compares against the snapshot at fecha_hasta.

    Calculated = stock at fecha_desde
                 + received (pedidos recibidos in period)
                 - consumed (production in period)
                 - wasted (mermas in period)

    Discrepancy = physical - calculated. Positive = more than expected, negative = missing.
    """
    if not fecha_hasta:
        fecha_hasta = date.today()
    if not fecha_desde:
        fecha_desde = fecha_hasta - timedelta(days=7)

    ingredientes = db.query(Ingrediente).filter(Ingrediente.activo.is_(True)).all()
    results = []

    for ing in ingredientes:
        # Stock snapshot at end of period (latest count on or before fecha_hasta)
        snapshot_fin = (
            db.query(InventarioRegistro)
            .filter(
                InventarioRegistro.ingrediente_id == ing.id,
                InventarioRegistro.fecha_registro <= fecha_hasta,
            )
            .order_by(InventarioRegistro.id.desc())
            .first()
        )
        conteo_fisico = snapshot_fin.cantidad if snapshot_fin else 0
        fecha_conteo = str(snapshot_fin.fecha_registro) if snapshot_fin else None

        # Stock snapshot at start of period (latest count on or before fecha_desde)
        snapshot_inicio = (
            db.query(InventarioRegistro)
            .filter(
                InventarioRegistro.ingrediente_id == ing.id,
                InventarioRegistro.fecha_registro <= fecha_desde,
            )
            .order_by(InventarioRegistro.id.desc())
            .first()
        )
        conteo_inicio = snapshot_inicio.cantidad if snapshot_inicio else 0
        fecha_inicio = str(snapshot_inicio.fecha_registro) if snapshot_inicio else None

        def _sum_movimientos(tipo_mov: str) -> float:
            val = (
                db.query(func.coalesce(func.sum(MovimientoStock.cantidad), 0))
                .filter(
                    MovimientoStock.tipo_stock == "materia_prima",
                    MovimientoStock.referencia_producto_id == ing.id,
                    MovimientoStock.tipo_movimiento == tipo_mov,
                    MovimientoStock.fecha >= fecha_desde,
                    MovimientoStock.fecha <= fecha_hasta,
                )
                .scalar()
            )
            return abs(val) if val else 0

        recibido = _sum_movimientos("recepcion")
        consumido = _sum_movimientos("produccion_consumo")
        mermado = _sum_movimientos("merma")

        calculado = round(conteo_inicio + recibido - consumido - mermado, 2)
        discrepancia = round(conteo_fisico - calculado, 2)

        results.append({
            "ingrediente_id": ing.id,
            "ingrediente": ing.nombre,
            "unidad": ing.unidad_uso,
            "conteo_fisico": conteo_fisico,
            "fecha_conteo": fecha_conteo,
            "conteo_anterior": conteo_inicio,
            "fecha_anterior": fecha_inicio,
            "recibido": recibido,
            "consumido": consumido,
            "mermado": mermado,
            "calculado": calculado,
            "discrepancia": discrepancia,
            "status": "ok" if abs(discrepancia) < 0.5 else "discrepancia",
        })

    results.sort(key=lambda x: abs(x.get("discrepancia") or 0), reverse=True)
    return {
        "periodo": {"desde": str(fecha_desde), "hasta": str(fecha_hasta)},
        "total_ingredientes": len(results),
        "con_discrepancia": len([r for r in results if r.get("status") == "discrepancia"]),
        "items": results,
    }
