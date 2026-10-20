from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.auth import require_admin
from app.database import get_db
from app.models import PedidoCliente, User
from app.schemas import PedidoClienteOut
from app.services.pedidos_vista import construir_pedido_out, nombres_productos

router = APIRouter(prefix="/api/admin/pedidos-clientes", tags=["pedidos-clientes-admin"])

VALID_ESTADOS = ["pendiente", "confirmado", "en_preparacion", "listo", "entregado"]


class _EstadoUpdate(BaseModel):
    estado: str


def _build_pedido_out(pedido: PedidoCliente, nombres=None) -> PedidoClienteOut:
    """Delega en el constructor compartido y le agrega el nombre del cliente.

    Esta vista mostraba literalmente "Cliente #23" y "10 x null": tenía su
    propia copia del armado, sin resolver ni el cliente ni los productos.
    Ahora reusa `construir_pedido_out` (el mismo que ve el cliente en su
    historial) y solo añade lo que aquí hace falta y allá no: el nombre del
    cliente, porque el cliente ya sabe quién es y el admin no.
    """
    out = construir_pedido_out(pedido, nombres)
    out.cliente_nombre = pedido.cliente.nombre if pedido.cliente else None
    return out


@router.get("", response_model=list[PedidoClienteOut])
def list_all_pedidos(
    estado: Optional[str] = Query(None),
    fecha_entrega: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # `joinedload` del cliente: leer `pedido.cliente.nombre` en el bucle
    # disparaba una consulta por pedido. Es N+1 recien estrenado -- antes esta
    # pantalla no resolvia el cliente en absoluto, por eso decia "Cliente #23".
    q = db.query(PedidoCliente).options(joinedload(PedidoCliente.cliente))
    if estado:
        q = q.filter(PedidoCliente.estado == estado)
    if fecha_entrega:
        q = q.filter(PedidoCliente.fecha_entrega == fecha_entrega)
    pedidos = q.order_by(PedidoCliente.fecha_pedido.desc()).all()
    nombres = nombres_productos(db)
    return [_build_pedido_out(p, nombres) for p in pedidos]


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
    # Same shared helper the /entregas screen uses, so a portal order marked
    # delivered from either place moves stock identically.
    from app.routers.entregas_b2b import aplicar_cambio_estado_portal

    aplicar_cambio_estado_portal(db, pedido, data.estado, admin.id)
    db.commit()
    db.refresh(pedido)
    return _build_pedido_out(pedido)
