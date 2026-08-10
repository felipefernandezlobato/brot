from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Ingrediente, InventarioRegistro, User
from app.permissions import require_permission
from app.schemas import InventarioRegistroCreate, InventarioRegistroOut

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
    """Subquery returning the max(id) per ingrediente_id (latest snapshot)."""
    return (
        db.query(
            InventarioRegistro.ingrediente_id,
            func.max(InventarioRegistro.id).label("max_id"),
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
