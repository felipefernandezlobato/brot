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
    User,
)
from app.services.conversiones import convertir
from app.services.produccion_registro import movimiento_no_revertido
from app.services.stock import es_conteo_manual, get_saldos_congelado

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

    # Stock congelado actual — sum of active lots per product, same method
    # every other stock display uses (get_saldo_congelado). The old version
    # here took only the single most-recently-dated lot per product, which
    # under-/over-counted any product with more than one active lot.
    productos_cong = db.query(ProductoCongelado).filter(ProductoCongelado.is_active.is_(True)).all()
    saldos_cong = get_saldos_congelado(db, [p.id for p in productos_cong])
    stock_cong = [
        {"nombre": p.nombre, "id": p.id, "total": saldos_cong.get(p.id, 0.0)}
        for p in productos_cong
        if abs(saldos_cong.get(p.id, 0.0)) > 1e-9
    ]
    stock_cong_total = sum(r["total"] for r in stock_cong)

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
            .filter(ProductoCatalogo.receta_id == db.query(ProductoCongelado.receta_id).filter(ProductoCongelado.id == cong["id"]).scalar())
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
            "nombre": cong["nombre"],
            "stock_congelado": cong["total"],
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
        .order_by(MovimientoStock.fecha.desc(), MovimientoStock.id.desc())
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
            {"nombre": c["nombre"], "cantidad": c["total"]} for c in stock_cong
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


def _es_conteo_manual(notas: Optional[str]) -> bool:
    return es_conteo_manual("materia_prima", notas)


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
        conteos = (
            db.query(InventarioRegistro)
            .filter(InventarioRegistro.ingrediente_id == ing.id)
            .order_by(InventarioRegistro.id.desc())
            .all()
        )
        conteos_manuales = [c for c in conteos if _es_conteo_manual(c.notas)]

        # Stock snapshot at end of period (latest MANUAL count on or before fecha_hasta)
        snapshot_fin = next((c for c in conteos_manuales if c.fecha_registro <= fecha_hasta), None)
        conteo_fisico = snapshot_fin.cantidad if snapshot_fin else 0
        fecha_conteo = str(snapshot_fin.fecha_registro) if snapshot_fin else None

        # Baseline: latest MANUAL count on or before fecha_desde. When none exists
        # (e.g. counting only started mid-window), fall back to the EARLIEST manual
        # count inside the window and start the movement sums from ITS date instead
        # -- otherwise every ingredient with no pre-window baseline would compare a
        # real physical count against a fake "0 + a week of consumption" total and
        # look like a huge discrepancy that was never real.
        snapshot_inicio = next((c for c in conteos_manuales if c.fecha_registro <= fecha_desde), None)
        if snapshot_inicio:
            conteo_inicio = snapshot_inicio.cantidad
            fecha_inicio = str(snapshot_inicio.fecha_registro)
            ventana_desde = fecha_desde
        else:
            fallback = next(
                (c for c in reversed(conteos_manuales) if fecha_desde < c.fecha_registro <= fecha_hasta),
                None,
            )
            conteo_inicio = fallback.cantidad if fallback else 0
            fecha_inicio = str(fallback.fecha_registro) if fallback else None
            # Sum movements strictly AFTER the fallback count's own date -- that
            # count already reflects everything up to and including that day.
            ventana_desde = (fallback.fecha_registro + timedelta(days=1)) if fallback else fecha_desde

        def _sum_movimientos(tipo_mov: str) -> float:
            val = (
                db.query(func.coalesce(func.sum(MovimientoStock.cantidad), 0))
                .filter(
                    MovimientoStock.tipo_stock == "materia_prima",
                    MovimientoStock.referencia_producto_id == ing.id,
                    MovimientoStock.tipo_movimiento == tipo_mov,
                    MovimientoStock.fecha >= ventana_desde,
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
