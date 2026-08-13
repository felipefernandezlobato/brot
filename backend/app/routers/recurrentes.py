from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_cliente import get_current_cliente
from app.database import get_db
from app.models import ClienteB2B, LineaPedidoRecurrente, PedidoRecurrente
from app.schemas import LineaPedidoRecurrenteIn, PedidoRecurrenteOut

router = APIRouter(prefix="/api/cliente/recurrentes", tags=["recurrentes"])


class _RecurrenteRequest(BaseModel):
    dia_entrega: str
    fecha_inicio: Optional[date] = None
    notas: Optional[str] = None
    lineas: list[LineaPedidoRecurrenteIn] = []


class _RecurrenteUpdate(BaseModel):
    dia_entrega: Optional[str] = None
    notas: Optional[str] = None
    lineas: Optional[list[LineaPedidoRecurrenteIn]] = None


def _build_out(rec: PedidoRecurrente) -> PedidoRecurrenteOut:
    return PedidoRecurrenteOut(
        id=rec.id,
        cliente_id=rec.cliente_id,
        dia_entrega=rec.dia_entrega,
        activo=rec.activo,
        fecha_inicio=rec.fecha_inicio,
        notas=rec.notas,
        lineas=[
            {
                "id": l.id,
                "pedido_recurrente_id": l.pedido_recurrente_id,
                "producto_id": l.producto_id,
                "cantidad_default": l.cantidad_default,
            }
            for l in rec.lineas
        ],
    )


@router.post("", response_model=PedidoRecurrenteOut, status_code=201)
def create_recurrente(
    data: _RecurrenteRequest,
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    rec = PedidoRecurrente(
        cliente_id=cliente.id,
        dia_entrega=data.dia_entrega,
        activo=True,
        fecha_inicio=data.fecha_inicio or date.today(),
        notas=data.notas,
    )
    db.add(rec)
    db.flush()

    for linea in data.lineas:
        db.add(
            LineaPedidoRecurrente(
                pedido_recurrente_id=rec.id,
                producto_id=linea.producto_id,
                cantidad_default=linea.cantidad_default,
            )
        )

    db.commit()
    db.refresh(rec)
    return _build_out(rec)


@router.get("", response_model=list[PedidoRecurrenteOut])
def list_recurrentes(
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    recs = (
        db.query(PedidoRecurrente)
        .filter(PedidoRecurrente.cliente_id == cliente.id)
        .all()
    )
    return [_build_out(r) for r in recs]


@router.put("/{rec_id}", response_model=PedidoRecurrenteOut)
def update_recurrente(
    rec_id: int,
    data: _RecurrenteUpdate,
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    rec = (
        db.query(PedidoRecurrente)
        .filter(PedidoRecurrente.id == rec_id, PedidoRecurrente.cliente_id == cliente.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Pedido recurrente no encontrado")

    if data.dia_entrega is not None:
        rec.dia_entrega = data.dia_entrega
    if data.notas is not None:
        rec.notas = data.notas

    if data.lineas is not None:
        # Replace all lines
        for linea in rec.lineas:
            db.delete(linea)
        db.flush()
        for linea in data.lineas:
            db.add(
                LineaPedidoRecurrente(
                    pedido_recurrente_id=rec.id,
                    producto_id=linea.producto_id,
                    cantidad_default=linea.cantidad_default,
                )
            )

    db.commit()
    db.refresh(rec)
    return _build_out(rec)


@router.delete("/{rec_id}")
def deactivate_recurrente(
    rec_id: int,
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    rec = (
        db.query(PedidoRecurrente)
        .filter(PedidoRecurrente.id == rec_id, PedidoRecurrente.cliente_id == cliente.id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Pedido recurrente no encontrado")
    rec.activo = False
    db.commit()
    return {"ok": True, "activo": False}
