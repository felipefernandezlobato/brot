from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import MovimientoStock, User
from app.schemas import MovimientoStockOut

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])


@router.get("", response_model=list[MovimientoStockOut])
def list_movimientos(
    tipo_stock: Optional[str] = Query(None),
    tipo_movimiento: Optional[str] = Query(None),
    referencia_producto_id: Optional[int] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    limit: int = Query(100, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MovimientoStock)
    if tipo_stock:
        q = q.filter(MovimientoStock.tipo_stock == tipo_stock)
    if tipo_movimiento:
        q = q.filter(MovimientoStock.tipo_movimiento == tipo_movimiento)
    if referencia_producto_id:
        q = q.filter(MovimientoStock.referencia_producto_id == referencia_producto_id)
    if fecha_desde:
        q = q.filter(MovimientoStock.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(MovimientoStock.fecha <= fecha_hasta)
    return q.order_by(MovimientoStock.id.desc()).limit(limit).all()
