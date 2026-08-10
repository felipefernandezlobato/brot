from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import PedidoCliente, User
from app.schemas import PedidoClienteOut

router = APIRouter(prefix="/api/admin/pedidos-clientes", tags=["pedidos-clientes-admin"])

VALID_ESTADOS = ["pendiente", "confirmado", "en_preparacion", "listo", "entregado"]


class _EstadoUpdate(BaseModel):
    estado: str


def _build_pedido_out(pedido: PedidoCliente) -> PedidoClienteOut:
    return PedidoClienteOut(
        id=pedido.id,
        cliente_id=pedido.cliente_id,
        fecha_pedido=pedido.fecha_pedido,
        fecha_entrega=pedido.fecha_entrega,
        estado=pedido.estado,
        notas=pedido.notas,
        total=pedido.total,
        pedido_recurrente_id=pedido.pedido_recurrente_id,
        lineas=[
            {
                "id": l.id,
                "pedido_cliente_id": l.pedido_cliente_id,
                "producto_id": l.producto_id,
                "cantidad": l.cantidad,
                "precio_unitario_snapshot": l.precio_unitario_snapshot,
                "subtotal": l.subtotal,
            }
            for l in pedido.lineas
        ],
    )


@router.get("", response_model=list[PedidoClienteOut])
def list_all_pedidos(
    estado: Optional[str] = Query(None),
    fecha_entrega: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    q = db.query(PedidoCliente)
    if estado:
        q = q.filter(PedidoCliente.estado == estado)
    if fecha_entrega:
        q = q.filter(PedidoCliente.fecha_entrega == fecha_entrega)
    pedidos = q.order_by(PedidoCliente.fecha_pedido.desc()).all()
    return [_build_pedido_out(p) for p in pedidos]


@router.put("/{pedido_id}/estado", response_model=PedidoClienteOut)
def update_estado(
    pedido_id: int,
    data: _EstadoUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if data.estado not in VALID_ESTADOS:
        raise HTTPException(
            status_code=422,
            detail=f"Estado inválido. Valores permitidos: {', '.join(VALID_ESTADOS)}",
        )
    pedido = db.query(PedidoCliente).filter(PedidoCliente.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    pedido.estado = data.estado
    db.commit()
    db.refresh(pedido)
    return _build_pedido_out(pedido)
