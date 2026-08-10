from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import ProductoCongelado, StockCongelado, User
from app.permissions import require_permission
from app.schemas import (
    ProductoCongeladoCreate,
    ProductoCongeladoOut,
    ProductoCongeladoUpdate,
    StockCongeladoCreate,
    StockCongeladoOut,
    StockCongeladoUpdate,
)

router = APIRouter(prefix="/api/congelados", tags=["congelados"])


# ── helpers ────────────────────────────────────────────────────────────────────

def _stock_out(s: StockCongelado) -> dict:
    return {
        "id": s.id,
        "producto_congelado_id": s.producto_congelado_id,
        "cantidad": s.cantidad,
        "fecha_entrada": s.fecha_entrada,
        "fecha_vencimiento": s.fecha_vencimiento,
        "lote": s.lote,
        "ubicacion": s.ubicacion,
        "notas": s.notas,
        "is_active": s.is_active,
        "producto_nombre": s.producto.nombre if s.producto else None,
    }


# ── ProductoCongelado CRUD  (/api/congelados/productos) ────────────────────────

@router.get("/productos", response_model=list[ProductoCongeladoOut])
def list_productos_congelados(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ProductoCongelado)
        .order_by(ProductoCongelado.position, ProductoCongelado.nombre)
        .all()
    )


@router.post("/productos", response_model=ProductoCongeladoOut, status_code=201)
def create_producto_congelado(
    data: ProductoCongeladoCreate,
    user: User = require_permission("congelados", "create"),
    db: Session = Depends(get_db),
):
    prod = ProductoCongelado(**data.model_dump())
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


@router.put("/productos/{prod_id}", response_model=ProductoCongeladoOut)
def update_producto_congelado(
    prod_id: int,
    data: ProductoCongeladoUpdate,
    user: User = require_permission("congelados", "edit"),
    db: Session = Depends(get_db),
):
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto congelado no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(prod, k, v)
    db.commit()
    db.refresh(prod)
    return prod


@router.delete("/productos/{prod_id}")
def delete_producto_congelado(
    prod_id: int,
    user: User = require_permission("congelados", "delete"),
    db: Session = Depends(get_db),
):
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto congelado no encontrado")
    if (
        db.query(StockCongelado)
        .filter(StockCongelado.producto_congelado_id == prod_id)
        .count()
        > 0
    ):
        raise HTTPException(status_code=409, detail="Producto tiene stock asociado")
    db.delete(prod)
    db.commit()
    return {"ok": True}


# ── Stock CRUD  (/api/congelados) ──────────────────────────────────────────────

@router.get("/alertas-vencimiento", response_model=list[StockCongeladoOut])
def alertas_vencimiento(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stock entries already expired or expiring within the next 7 days."""
    cutoff = date.today() + timedelta(days=7)
    entries = (
        db.query(StockCongelado)
        .options(joinedload(StockCongelado.producto))
        .filter(StockCongelado.is_active.is_(True))
        .filter(StockCongelado.fecha_vencimiento.isnot(None))
        .filter(StockCongelado.fecha_vencimiento <= cutoff)
        .order_by(StockCongelado.fecha_vencimiento)
        .all()
    )
    return [_stock_out(e) for e in entries]


@router.get("", response_model=list[StockCongeladoOut])
def list_stock_congelado(
    producto_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(StockCongelado).options(joinedload(StockCongelado.producto))
    if producto_id:
        q = q.filter(StockCongelado.producto_congelado_id == producto_id)
    return [_stock_out(e) for e in q.order_by(StockCongelado.fecha_entrada).all()]


@router.post("", response_model=StockCongeladoOut, status_code=201)
def add_stock_congelado(
    data: StockCongeladoCreate,
    user: User = require_permission("congelados", "create"),
    db: Session = Depends(get_db),
):
    entry = StockCongelado(**data.model_dump(exclude_none=True))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.refresh(entry, ["producto"])
    return _stock_out(entry)


@router.put("/{entry_id}", response_model=StockCongeladoOut)
def update_stock_congelado(
    entry_id: int,
    data: StockCongeladoUpdate,
    user: User = require_permission("congelados", "edit"),
    db: Session = Depends(get_db),
):
    entry = (
        db.query(StockCongelado)
        .options(joinedload(StockCongelado.producto))
        .filter(StockCongelado.id == entry_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de stock no encontrada")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return _stock_out(entry)


@router.delete("/{entry_id}")
def delete_stock_congelado(
    entry_id: int,
    user: User = require_permission("congelados", "delete"),
    db: Session = Depends(get_db),
):
    entry = db.query(StockCongelado).filter(StockCongelado.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de stock no encontrada")
    db.delete(entry)
    db.commit()
    return {"ok": True}
