from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_cliente import get_current_cliente
from app.database import get_db
from app.models import (
    ClienteB2B,
    EntregaB2B,
    LineaPedidoCliente,
    PedidoCliente,
    ProductoCatalogo,
)
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


def _nombres_productos(db: Session) -> dict[int, str]:
    return {p.id: p.nombre for p in db.query(ProductoCatalogo).all()}


def _build_pedido_out(
    pedido: PedidoCliente, nombres: Optional[dict[int, str]] = None
) -> PedidoClienteOut:
    nombres = nombres or {}
    return PedidoClienteOut(
        id=pedido.id,
        cliente_id=pedido.cliente_id,
        fecha_pedido=pedido.fecha_pedido,
        fecha_entrega=pedido.fecha_entrega,
        estado=pedido.estado,
        notas=pedido.notas,
        total=pedido.total,
        pedido_recurrente_id=pedido.pedido_recurrente_id,
        origen="portal",
        lineas=[
            {
                "id": l.id,
                "pedido_cliente_id": l.pedido_cliente_id,
                "producto_id": l.producto_id,
                "cantidad": l.cantidad,
                "precio_unitario_snapshot": l.precio_unitario_snapshot,
                "subtotal": l.subtotal,
                "producto_nombre": nombres.get(l.producto_id),
            }
            for l in pedido.lineas
        ],
    )


def _build_entrega_out(
    entrega: EntregaB2B, nombres: Optional[dict[int, str]] = None
) -> PedidoClienteOut:
    """Una EntregaB2B vista como pedido, para el historial del cliente.

    `pedidos_clientes` solo recoge lo que el cliente pide desde la web, pero a
    los clientes B2B el obrador les carga las entregas a mano como `EntregaB2B`.
    Con la tabla del portal vacia, "Mis Pedidos" salia vacio para todo el mundo
    aunque Olula llevara doce entregas. Las dos tablas apuntan al mismo
    `clientes_b2b.id`, asi que se pueden mezclar directamente.

    Solo de lectura: una entrega la crea y la modifica el obrador, el cliente la
    ve pero no la toca. De ahi que el detalle y la cancelacion sigan mirando
    unicamente `PedidoCliente`.
    """
    nombres = nombres or {}
    total = sum(l.cantidad * (l.precio_unitario or 0) for l in entrega.lineas)
    return PedidoClienteOut(
        id=entrega.id,
        cliente_id=entrega.cliente_b2b_id,
        fecha_pedido=entrega.created_at,
        fecha_entrega=entrega.fecha_entrega,
        estado=entrega.estado,
        notas=entrega.notas,
        total=total,
        pedido_recurrente_id=None,
        origen="entrega",
        lineas=[
            {
                "id": l.id,
                "pedido_cliente_id": entrega.id,
                "producto_id": l.producto_id,
                "cantidad": l.cantidad,
                "precio_unitario_snapshot": l.precio_unitario or 0,
                "subtotal": l.cantidad * (l.precio_unitario or 0),
                "producto_nombre": nombres.get(l.producto_id),
            }
            for l in entrega.lineas
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
    nombres = _nombres_productos(db)
    pedidos = (
        db.query(PedidoCliente)
        .filter(PedidoCliente.cliente_id == cliente.id)
        .all()
    )
    entregas = (
        db.query(EntregaB2B)
        .filter(EntregaB2B.cliente_b2b_id == cliente.id)
        .all()
    )
    salida = (
        [_build_pedido_out(p, nombres) for p in pedidos]
        + [_build_entrega_out(e, nombres) for e in entregas]
    )
    # Por fecha de entrega, que es lo que el cliente reconoce; el id desempata
    # dentro del mismo dia para que el orden no baile entre recargas.
    salida.sort(key=lambda p: (p.fecha_entrega, p.id), reverse=True)
    return salida


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
