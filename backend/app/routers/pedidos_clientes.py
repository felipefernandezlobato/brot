from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_cliente import get_current_cliente
from app.database import get_db
from app.models import ClienteB2B, LineaPedidoCliente, PedidoCliente, ProductoCatalogo
from app.schemas import PedidoClienteOut

router = APIRouter(prefix="/api/cliente/pedidos", tags=["pedidos-clientes"])

# Wednesday=2, Saturday=5  (Python weekday: Mon=0 … Sun=6)
VALID_DELIVERY_DAYS = {2, 5}
VALID_ESTADOS = {"pendiente", "confirmado", "en_preparacion", "listo", "entregado"}


class _LineaIn(BaseModel):
    producto_id: int
    cantidad: float


class _PedidoRequest(BaseModel):
    fecha_entrega: date
    notas: Optional[str] = None
    lineas: list[_LineaIn]


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


@router.post("", response_model=PedidoClienteOut, status_code=201)
def create_pedido(
    data: _PedidoRequest,
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    if data.fecha_entrega.weekday() not in VALID_DELIVERY_DAYS:
        raise HTTPException(
            status_code=422,
            detail="La fecha de entrega debe ser miércoles o sábado",
        )

    if not data.lineas:
        raise HTTPException(status_code=422, detail="El pedido debe tener al menos una línea")

    total = 0.0
    lineas_db: list[LineaPedidoCliente] = []

    for linea in data.lineas:
        producto = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == linea.producto_id).first()
        if not producto:
            raise HTTPException(
                status_code=404,
                detail=f"Producto {linea.producto_id} no encontrado",
            )
        if not producto.disponible:
            raise HTTPException(
                status_code=422,
                detail=f"Producto '{producto.nombre}' no está disponible",
            )
        subtotal = round(linea.cantidad * producto.precio, 2)
        total += subtotal
        lineas_db.append(
            LineaPedidoCliente(
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                precio_unitario_snapshot=producto.precio,
                subtotal=subtotal,
            )
        )

    pedido = PedidoCliente(
        cliente_id=cliente.id,
        fecha_entrega=data.fecha_entrega,
        notas=data.notas,
        total=round(total, 2),
        estado="pendiente",
    )
    db.add(pedido)
    db.flush()  # get pedido.id before adding lines

    for linea in lineas_db:
        linea.pedido_cliente_id = pedido.id
        db.add(linea)

    db.commit()
    db.refresh(pedido)
    return _build_pedido_out(pedido)


@router.get("", response_model=list[PedidoClienteOut])
def list_pedidos(
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    pedidos = (
        db.query(PedidoCliente)
        .filter(PedidoCliente.cliente_id == cliente.id)
        .order_by(PedidoCliente.fecha_pedido.desc())
        .all()
    )
    return [_build_pedido_out(p) for p in pedidos]


@router.get("/{pedido_id}", response_model=PedidoClienteOut)
def get_pedido(
    pedido_id: int,
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    pedido = (
        db.query(PedidoCliente)
        .filter(PedidoCliente.id == pedido_id, PedidoCliente.cliente_id == cliente.id)
        .first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return _build_pedido_out(pedido)
