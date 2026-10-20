from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_cliente import get_cliente_aprobado, get_current_cliente
from app.database import get_db
from app.models import (
    ClienteB2B,
    EntregaB2B,
    LineaPedidoCliente,
    PedidoCliente,
    ProductoCatalogo,
)
from app.schemas import PedidoClienteOut
from app.services.avisos_pedido import avisar_pedido_nuevo
from app.services.pedidos_vista import construir_pedido_out, historial_de_cliente

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


@router.post("", response_model=PedidoClienteOut, status_code=201)
def create_pedido(
    data: _PedidoRequest,
    tareas: BackgroundTasks,
    cliente: ClienteB2B = Depends(get_cliente_aprobado),
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
    para_el_aviso: list[tuple[str, float]] = []

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
        # El nombre se guarda aca, con la sesion viva: el aviso al panadero
        # corre despues de responder y ya no puede ir a buscarlo.
        para_el_aviso.append((producto.nombre, linea.cantidad))

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

    # Despues del commit y en segundo plano, las dos cosas a proposito: el
    # pedido ya esta guardado cuando se intenta el correo, asi que un fallo de
    # SMTP no puede perderlo ni dejar al cliente esperando a Gmail. Es lo mismo
    # que se aprendio en el alta de clientes, que tardaba segundos por mandar
    # el mail dentro de la peticion.
    tareas.add_task(
        avisar_pedido_nuevo,
        pedido_id=pedido.id,
        cliente=cliente.nombre,
        fecha_entrega=pedido.fecha_entrega,
        fecha_pedido=pedido.fecha_pedido,
        lineas=para_el_aviso,
        total=pedido.total,
        notas=pedido.notas,
    )
    return construir_pedido_out(pedido)


@router.get("", response_model=list[PedidoClienteOut])
def list_pedidos(
    cliente: ClienteB2B = Depends(get_cliente_aprobado),
    db: Session = Depends(get_db),
):
    # Una sola definicion del historial, compartida con la ficha de cliente del
    # admin (`services/cuenta_cliente.py`). Si se bifurcaran, el admin y el
    # cliente verian historiales distintos del mismo cliente, que es el peor
    # tipo de discrepancia: la que nadie nota hasta que uno de los dos reclama.
    return historial_de_cliente(db, cliente.id)


@router.get("/{pedido_id}", response_model=PedidoClienteOut)
def get_pedido(
    pedido_id: int,
    cliente: ClienteB2B = Depends(get_cliente_aprobado),
    db: Session = Depends(get_db),
):
    pedido = (
        db.query(PedidoCliente)
        .filter(PedidoCliente.id == pedido_id, PedidoCliente.cliente_id == cliente.id)
        .first()
    )
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return construir_pedido_out(pedido)
