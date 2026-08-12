from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import ClienteB2B, EntregaB2B, LineaEntregaB2B, ProductoCatalogo, User
from app.services.stock import deducir_congelado_por_catalogo
from app.permissions import require_permission
from app.schemas import (
    ClienteB2BCreate,
    ClienteB2BOut,
    ClienteB2BUpdate,
    EntregaB2BCreate,
    EntregaB2BOut,
    EntregaB2BUpdate,
)

# ─── B2B Clients ─────────────────────────────────────────────────────────────

clientes_router = APIRouter(prefix="/api/clientes-b2b", tags=["clientes-b2b"])


@clientes_router.get("", response_model=list[ClienteB2BOut])
def list_clientes_b2b(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(ClienteB2B).order_by(ClienteB2B.nombre).all()


@clientes_router.get("/{cliente_id}", response_model=ClienteB2BOut)
def get_cliente_b2b(
    cliente_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    obj = db.query(ClienteB2B).filter(ClienteB2B.id == cliente_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cliente B2B no encontrado")
    return obj


@clientes_router.post("", response_model=ClienteB2BOut, status_code=201)
def create_cliente_b2b(
    data: ClienteB2BCreate,
    user: User = require_permission("entregas_b2b", "create"),
    db: Session = Depends(get_db),
):
    obj = ClienteB2B(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@clientes_router.put("/{cliente_id}", response_model=ClienteB2BOut)
def update_cliente_b2b(
    cliente_id: int,
    data: ClienteB2BUpdate,
    user: User = require_permission("entregas_b2b", "edit"),
    db: Session = Depends(get_db),
):
    obj = db.query(ClienteB2B).filter(ClienteB2B.id == cliente_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cliente B2B no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, val)
    db.commit()
    db.refresh(obj)
    return obj


@clientes_router.delete("/{cliente_id}")
def delete_cliente_b2b(
    cliente_id: int,
    user: User = require_permission("entregas_b2b", "delete"),
    db: Session = Depends(get_db),
):
    obj = db.query(ClienteB2B).filter(ClienteB2B.id == cliente_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Cliente B2B no encontrado")
    db.delete(obj)
    db.commit()
    return {"ok": True}


# ─── Entregas B2B ─────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/entregas-b2b", tags=["entregas-b2b"])


class EstadoUpdate(BaseModel):
    estado: str


def _entrega_out(entrega: EntregaB2B) -> dict:
    return {
        "id": entrega.id,
        "cliente_b2b_id": entrega.cliente_b2b_id,
        "fecha_entrega": entrega.fecha_entrega,
        "estado": entrega.estado,
        "notas": entrega.notas,
        "created_at": entrega.created_at,
        "lineas": [
            {
                "id": l.id,
                "entrega_id": l.entrega_id,
                "producto_id": l.producto_id,
                "cantidad": l.cantidad,
                "precio_unitario": l.precio_unitario,
            }
            for l in entrega.lineas
        ],
    }


# NOTE: /volumen must be declared before /{entrega_id} so FastAPI matches the
# literal segment first.
@router.get("/volumen")
def volumen_entregas(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate delivery volumes by product and client."""
    q = (
        db.query(
            ClienteB2B.nombre.label("cliente_nombre"),
            ProductoCatalogo.nombre.label("producto_nombre"),
            func.sum(LineaEntregaB2B.cantidad).label("total_cantidad"),
            func.sum(
                LineaEntregaB2B.cantidad * LineaEntregaB2B.precio_unitario
            ).label("total_valor"),
        )
        .join(EntregaB2B, EntregaB2B.id == LineaEntregaB2B.entrega_id)
        .join(ClienteB2B, ClienteB2B.id == EntregaB2B.cliente_b2b_id)
        .join(ProductoCatalogo, ProductoCatalogo.id == LineaEntregaB2B.producto_id)
    )
    if fecha_desde:
        q = q.filter(EntregaB2B.fecha_entrega >= fecha_desde)
    if fecha_hasta:
        q = q.filter(EntregaB2B.fecha_entrega <= fecha_hasta)
    rows = (
        q.group_by(ClienteB2B.id, ProductoCatalogo.id)
        .order_by(ClienteB2B.nombre, ProductoCatalogo.nombre)
        .all()
    )
    return [
        {
            "cliente_nombre": r.cliente_nombre,
            "producto_nombre": r.producto_nombre,
            "total_cantidad": r.total_cantidad,
            "total_valor": round(r.total_valor or 0, 2),
        }
        for r in rows
    ]


@router.get("", response_model=list[EntregaB2BOut])
def list_entregas_b2b(
    fecha: Optional[date] = Query(None),
    cliente_b2b_id: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(EntregaB2B).options(joinedload(EntregaB2B.lineas))
    if fecha:
        q = q.filter(EntregaB2B.fecha_entrega == fecha)
    if cliente_b2b_id:
        q = q.filter(EntregaB2B.cliente_b2b_id == cliente_b2b_id)
    if estado:
        q = q.filter(EntregaB2B.estado == estado)
    entregas = q.order_by(EntregaB2B.fecha_entrega.desc()).all()
    return [_entrega_out(e) for e in entregas]


@router.post("", response_model=EntregaB2BOut, status_code=201)
def create_entrega_b2b(
    data: EntregaB2BCreate,
    user: User = require_permission("entregas_b2b", "create"),
    db: Session = Depends(get_db),
):
    cliente = db.query(ClienteB2B).filter(ClienteB2B.id == data.cliente_b2b_id).first()
    cliente_nombre = cliente.nombre if cliente else ""
    entrega = EntregaB2B(
        cliente_b2b_id=data.cliente_b2b_id,
        fecha_entrega=data.fecha_entrega,
        estado=data.estado,
        notas=data.notas,
    )
    db.add(entrega)
    db.flush()
    ref = f"entrega_b2b:{entrega.id}:{cliente_nombre}"
    for l in data.lineas:
        linea = LineaEntregaB2B(
            entrega_id=entrega.id,
            producto_id=l.producto_id,
            cantidad=l.cantidad,
            precio_unitario=l.precio_unitario,
        )
        db.add(linea)
        if data.estado == "entregado":
            deducir_congelado_por_catalogo(
                db, l.producto_id, l.cantidad,
                ref, "entrega_b2b", user.id,
                fecha=data.fecha_entrega,
            )
    db.commit()
    db.refresh(entrega, ["lineas"])
    return _entrega_out(entrega)


@router.get("/{entrega_id}", response_model=EntregaB2BOut)
def get_entrega_b2b(
    entrega_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entrega = (
        db.query(EntregaB2B)
        .options(joinedload(EntregaB2B.lineas))
        .filter(EntregaB2B.id == entrega_id)
        .first()
    )
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega B2B no encontrada")
    return _entrega_out(entrega)


@router.put("/{entrega_id}", response_model=EntregaB2BOut)
def update_entrega_b2b(
    entrega_id: int,
    data: EntregaB2BUpdate,
    user: User = require_permission("entregas_b2b", "edit"),
    db: Session = Depends(get_db),
):
    entrega = (
        db.query(EntregaB2B)
        .options(joinedload(EntregaB2B.lineas))
        .filter(EntregaB2B.id == entrega_id)
        .first()
    )
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega B2B no encontrada")

    updates = data.model_dump(exclude_unset=True)
    lineas_data = updates.pop("lineas", None)

    for key, val in updates.items():
        setattr(entrega, key, val)

    if lineas_data is not None:
        for old_line in list(entrega.lineas):
            db.delete(old_line)
        db.flush()
        for l in lineas_data:
            linea = LineaEntregaB2B(
                entrega_id=entrega.id,
                producto_id=l["producto_id"],
                cantidad=l["cantidad"],
                precio_unitario=l.get("precio_unitario", 0),
            )
            db.add(linea)

    db.commit()
    db.refresh(entrega, ["lineas"])
    return _entrega_out(entrega)


@router.put("/{entrega_id}/estado")
def update_estado_entrega_b2b(
    entrega_id: int,
    body: EstadoUpdate,
    user: User = require_permission("entregas_b2b", "edit"),
    db: Session = Depends(get_db),
):
    entrega = (
        db.query(EntregaB2B)
        .options(joinedload(EntregaB2B.lineas))
        .filter(EntregaB2B.id == entrega_id)
        .first()
    )
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega B2B no encontrada")
    was_entregado = entrega.estado == "entregado"
    entrega.estado = body.estado
    if body.estado == "entregado" and not was_entregado:
        cliente = db.query(ClienteB2B).filter(ClienteB2B.id == entrega.cliente_b2b_id).first()
        cliente_nombre = cliente.nombre if cliente else ""
        ref = f"entrega_b2b:{entrega.id}:{cliente_nombre}"
        for l in entrega.lineas:
            deducir_congelado_por_catalogo(
                db, l.producto_id, l.cantidad,
                ref, "entrega_b2b", user.id,
                fecha=entrega.fecha_entrega,
            )
    db.commit()
    db.refresh(entrega)
    return {"id": entrega.id, "estado": entrega.estado}


@router.delete("/{entrega_id}")
def delete_entrega_b2b(
    entrega_id: int,
    user: User = require_permission("entregas_b2b", "delete"),
    db: Session = Depends(get_db),
):
    entrega = db.query(EntregaB2B).filter(EntregaB2B.id == entrega_id).first()
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega B2B no encontrada")
    db.delete(entrega)
    db.commit()
    return {"ok": True}
