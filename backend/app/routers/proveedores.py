from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Ingrediente, Pedido, PrecioProveedor, Proveedor, User
from app.permissions import require_permission
from app.schemas import (
    PrecioProveedorCreate,
    PrecioProveedorOut,
    ProveedorCreate,
    ProveedorOut,
    ProveedorUpdate,
)

router = APIRouter(prefix="/api/proveedores", tags=["proveedores"])


def _proveedor_out(p: Proveedor) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "notas": p.notas,
        "lead_time_dias": p.lead_time_dias,
        "ciclo_pedido_dias": p.ciclo_pedido_dias,
        "telefono": p.telefono,
        "email": p.email,
    }


def _precio_out(pp: PrecioProveedor) -> dict:
    return {
        "id": pp.id,
        "ingrediente_id": pp.ingrediente_id,
        "proveedor_id": pp.proveedor_id,
        "precio": pp.precio,
        "unidad": pp.unidad,
        "cantidad": pp.cantidad,
        "precio_por_unidad": pp.precio_por_unidad,
        "fecha": pp.fecha,
        "notas": pp.notas,
    }


# ── Static sub-routes must appear before /{proveedor_id} ──────────────────────

@router.post("/precios", response_model=PrecioProveedorOut, status_code=201)
def upsert_precio(
    data: PrecioProveedorCreate,
    user: User = require_permission("pedidos_proveedores", "create"),
    db: Session = Depends(get_db),
):
    """Create or update a supplier price for one ingredient."""
    existing = (
        db.query(PrecioProveedor)
        .filter(
            PrecioProveedor.ingrediente_id == data.ingrediente_id,
            PrecioProveedor.proveedor_id == data.proveedor_id,
        )
        .first()
    )
    if existing:
        for key, val in data.model_dump(exclude_unset=True).items():
            setattr(existing, key, val)
        if existing.fecha is None:
            existing.fecha = date.today()
        db.commit()
        db.refresh(existing)
        return _precio_out(existing)

    pp_data = data.model_dump()
    if pp_data.get("fecha") is None:
        pp_data["fecha"] = date.today()
    pp = PrecioProveedor(**pp_data)
    db.add(pp)
    db.commit()
    db.refresh(pp)
    return _precio_out(pp)


@router.get("/comparar/{ingrediente_id}", response_model=list[PrecioProveedorOut])
def comparar_precios(
    ingrediente_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All supplier prices for one ingredient, ordered cheapest first."""
    if not db.query(Ingrediente).filter(Ingrediente.id == ingrediente_id).first():
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    rows = (
        db.query(PrecioProveedor)
        .filter(PrecioProveedor.ingrediente_id == ingrediente_id)
        .order_by(PrecioProveedor.precio_por_unidad)
        .all()
    )
    return [_precio_out(pp) for pp in rows]


# ── Collection + item routes ───────────────────────────────────────────────────

@router.get("", response_model=list[ProveedorOut])
def list_proveedores(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [_proveedor_out(p) for p in db.query(Proveedor).order_by(Proveedor.nombre).all()]


@router.post("", response_model=ProveedorOut, status_code=201)
def create_proveedor(
    data: ProveedorCreate,
    user: User = require_permission("pedidos_proveedores", "create"),
    db: Session = Depends(get_db),
):
    if db.query(Proveedor).filter(Proveedor.nombre == data.nombre).first():
        raise HTTPException(status_code=409, detail="Proveedor con ese nombre ya existe")
    p = Proveedor(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _proveedor_out(p)


@router.get("/{proveedor_id}", response_model=ProveedorOut)
def get_proveedor(
    proveedor_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return _proveedor_out(p)


@router.put("/{proveedor_id}", response_model=ProveedorOut)
def update_proveedor(
    proveedor_id: int,
    data: ProveedorUpdate,
    user: User = require_permission("pedidos_proveedores", "edit"),
    db: Session = Depends(get_db),
):
    p = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(p, key, val)
    db.commit()
    db.refresh(p)
    return _proveedor_out(p)


@router.delete("/{proveedor_id}")
def delete_proveedor(
    proveedor_id: int,
    user: User = require_permission("pedidos_proveedores", "delete"),
    db: Session = Depends(get_db),
):
    p = db.query(Proveedor).filter(Proveedor.id == proveedor_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if db.query(Pedido).filter(Pedido.proveedor_id == proveedor_id).count() > 0:
        raise HTTPException(status_code=409, detail="El proveedor tiene pedidos asociados")
    db.delete(p)
    db.commit()
    return {"ok": True}
