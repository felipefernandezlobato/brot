from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Ingrediente, InventarioRegistro, LineaPedido, Pedido, User
from app.permissions import require_permission
from app.schemas import InventarioRegistroCreate, InventarioRegistroOut
from app.services.stock import historial_movimientos_acumulado

router = APIRouter(prefix="/api/inventario", tags=["inventario"])


def _to_out(reg: InventarioRegistro) -> dict:
    return {
        "id": reg.id,
        "ingrediente_id": reg.ingrediente_id,
        "cantidad": reg.cantidad,
        "unidad": reg.unidad,
        "fecha_registro": reg.fecha_registro,
        "notas": reg.notas,
        "ubicacion": reg.ubicacion,
    }


def _latest_subquery(db: Session):
    """Subquery returning the latest record per ingrediente_id (by date, then id)."""
    from sqlalchemy import and_
    latest_fecha = (
        db.query(
            InventarioRegistro.ingrediente_id,
            func.max(InventarioRegistro.fecha_registro).label("max_fecha"),
        )
        .group_by(InventarioRegistro.ingrediente_id)
        .subquery()
    )
    return (
        db.query(
            InventarioRegistro.ingrediente_id,
            func.max(InventarioRegistro.id).label("max_id"),
        )
        .join(
            latest_fecha,
            and_(
                InventarioRegistro.ingrediente_id == latest_fecha.c.ingrediente_id,
                InventarioRegistro.fecha_registro == latest_fecha.c.max_fecha,
            ),
        )
        .group_by(InventarioRegistro.ingrediente_id)
        .subquery()
    )


# NOTE: /alertas and /actual must be declared before /{registro_id} so FastAPI
# does not swallow them as path parameters.


@router.get("/alertas")
def get_alertas(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active ingredients with zero stock or no inventory records at all."""
    ingredientes = db.query(Ingrediente).filter(Ingrediente.activo == True).all()

    subq = _latest_subquery(db)
    latest = (
        db.query(InventarioRegistro)
        .join(subq, InventarioRegistro.id == subq.c.max_id)
        .all()
    )
    latest_by_ing = {r.ingrediente_id: r for r in latest}

    alertas = []
    for ing in ingredientes:
        reg = latest_by_ing.get(ing.id)
        if reg is None or reg.cantidad == 0:
            alertas.append(
                {
                    "ingrediente_id": ing.id,
                    "ingrediente_nombre": ing.nombre,
                    "cantidad": reg.cantidad if reg else None,
                    "unidad": reg.unidad if reg else ing.unidad_uso,
                    "fecha_registro": str(reg.fecha_registro) if reg else None,
                    "alerta": "sin_stock" if (reg and reg.cantidad == 0) else "sin_registro",
                }
            )
    return alertas


@router.get("/actual")
def get_stock_actual(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent inventory record per ingredient (current stock snapshot)."""
    subq = _latest_subquery(db)
    registros = (
        db.query(InventarioRegistro)
        .join(subq, InventarioRegistro.id == subq.c.max_id)
        .all()
    )
    return [_to_out(r) for r in registros]


@router.get("", response_model=list[InventarioRegistroOut])
def list_inventario(
    ingrediente_id: Optional[int] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all inventory records with optional filters."""
    q = db.query(InventarioRegistro)
    if ingrediente_id is not None:
        q = q.filter(InventarioRegistro.ingrediente_id == ingrediente_id)
    if fecha_desde:
        q = q.filter(InventarioRegistro.fecha_registro >= fecha_desde)
    if fecha_hasta:
        q = q.filter(InventarioRegistro.fecha_registro <= fecha_hasta)
    return [
        _to_out(r)
        for r in q.order_by(
            InventarioRegistro.fecha_registro.desc(),
            InventarioRegistro.id.desc(),
        ).all()
    ]


@router.post("", response_model=list[InventarioRegistroOut], status_code=201)
def create_inventario(
    data: list[InventarioRegistroCreate],
    user: User = require_permission("stock", "create"),
    db: Session = Depends(get_db),
):
    """Create one or more inventory snapshot records (batch supported)."""
    registros = []
    for item in data:
        ing = db.query(Ingrediente).filter(Ingrediente.id == item.ingrediente_id).first()
        if not ing:
            raise HTTPException(
                status_code=404,
                detail=f"Ingrediente {item.ingrediente_id} no encontrado",
            )
        payload = item.model_dump()
        if payload.get("fecha_registro") is None:
            payload["fecha_registro"] = date.today()
        reg = InventarioRegistro(**payload)
        db.add(reg)
        registros.append(reg)

    db.commit()
    for r in registros:
        db.refresh(r)
    return [_to_out(r) for r in registros]


@router.get("/recomendacion")
def recomendacion_pedido(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Order recommendation: for each active ingredient, calculate
    cantidad_sugerida = max(0, par_level - stock_actual)

    Par level = average weekly consumption * 2 weeks (safety buffer).
    Consumption estimated from inventory record differences over last 8 weeks.
    """
    ingredientes = db.query(Ingrediente).filter(Ingrediente.activo.is_(True)).all()
    subq = _latest_subquery(db)
    latest_regs = (
        db.query(InventarioRegistro)
        .join(subq, InventarioRegistro.id == subq.c.max_id)
        .all()
    )
    stock_map = {r.ingrediente_id: r.cantidad for r in latest_regs}

    # Estimate weekly consumption from last 8 weeks of inventory data
    hace_8_semanas = date.today() - timedelta(weeks=8)
    items = []

    for ing in ingredientes:
        stock_actual = stock_map.get(ing.id, 0)

        # Get all records for this ingredient in last 8 weeks, oldest first
        records = (
            db.query(InventarioRegistro)
            .filter(
                InventarioRegistro.ingrediente_id == ing.id,
                InventarioRegistro.fecha_registro >= hace_8_semanas,
            )
            .order_by(InventarioRegistro.fecha_registro, InventarioRegistro.id)
            .all()
        )

        # Calculate consumption from consecutive snapshots
        consumo_total = 0
        dias_total = 0
        for i in range(1, len(records)):
            prev_r = records[i - 1]
            curr_r = records[i]
            dias = (curr_r.fecha_registro - prev_r.fecha_registro).days
            if dias <= 0:
                continue

            # Received orders between these two dates
            recibido = (
                db.query(func.coalesce(func.sum(LineaPedido.cantidad_recibida), 0))
                .join(Pedido, Pedido.id == LineaPedido.pedido_id)
                .filter(
                    LineaPedido.ingrediente_id == ing.id,
                    Pedido.estado == "recibido",
                    Pedido.fecha_recepcion > prev_r.fecha_registro,
                    Pedido.fecha_recepcion <= curr_r.fecha_registro,
                )
                .scalar()
            ) or 0

            consumo = prev_r.cantidad + recibido - curr_r.cantidad
            if consumo > 0:
                consumo_total += consumo
                dias_total += dias

        consumo_semanal = (consumo_total / dias_total * 7) if dias_total > 0 else 0
        par_level = consumo_semanal * 2
        cantidad_sugerida = max(0, round(par_level - stock_actual, 1))

        items.append({
            "ingrediente_id": ing.id,
            "ingrediente": ing.nombre,
            "unidad": ing.unidad_uso,
            "proveedor": ing.proveedor or "Sin proveedor",
            "stock_actual": stock_actual,
            "consumo_semanal": round(consumo_semanal, 2),
            "par_level": round(par_level, 1),
            "cantidad_sugerida": cantidad_sugerida,
        })

    # Group by supplier
    by_supplier: dict[str, list] = {}
    for item in items:
        sup = item["proveedor"]
        if sup not in by_supplier:
            by_supplier[sup] = []
        by_supplier[sup].append(item)

    return {
        "fecha": str(date.today()),
        "por_proveedor": [
            {"proveedor": sup, "items": items}
            for sup, items in sorted(by_supplier.items())
        ],
    }


@router.get("/calculado")
def get_inventario_calculado(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculated (ledger) stock over time for every ingredient with movements
    -- companion to GET /api/inventario (the manual/physical counts), for the
    Stock Materia Prima pivot table's "physical vs calculated" comparison.

    fecha_desde is NOT used to filter the underlying query: a running balance
    is only correct when computed from full history up to fecha_hasta, so
    trimming to fecha_desde would silently reset the baseline to zero at the
    window edge. It's trimmed for the response instead, keeping the last
    point before fecha_desde as an opening balance so a "nearest date <= X"
    lookup on the frontend still works for dates right at the start of range.
    """
    historial = historial_movimientos_acumulado(db, "materia_prima", fecha_hasta=fecha_hasta)

    ingredientes_out = []
    for iid, puntos in historial.items():
        if fecha_desde:
            corte = str(fecha_desde)
            antes = [p for p in puntos if p["fecha"] < corte]
            despues = [p for p in puntos if p["fecha"] >= corte]
            puntos = ([antes[-1]] if antes else []) + despues
        ingredientes_out.append({"ingrediente_id": iid, "historial": puntos})

    return {"ingredientes": ingredientes_out}


@router.delete("/{registro_id}")
def delete_inventario(
    registro_id: int,
    user: User = require_permission("stock", "delete"),
    db: Session = Depends(get_db),
):
    """Delete an inventory record (admin / stock-delete permission required)."""
    reg = db.query(InventarioRegistro).filter(InventarioRegistro.id == registro_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db.delete(reg)
    db.commit()
    return {"ok": True}
