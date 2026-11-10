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
from app.services.pedido_express import (
    DIAS_ANTICIPACION_NORMAL,
    RECARGO_EXPRESS_PCT,
    calcular_recargo,
    evaluar,
    hoy_arg,
)
from app.services.pedidos_vista import construir_pedido_out, historial_de_cliente

router = APIRouter(prefix="/api/cliente/pedidos", tags=["pedidos-clientes"])

# Wednesday=2, Saturday=5  (Python weekday: Mon=0 … Sun=6)
VALID_DELIVERY_DAYS = {2, 5}
VALID_ESTADOS = {"pendiente", "confirmado", "en_preparacion", "listo", "entregado"}


def _hoy() -> date:
    """El "hoy" contra el que se mide la antelacion, en hora de Argentina.

    Es una dependencia de FastAPI y no una llamada directa para que los tests
    puedan fijarlo (`app.dependency_overrides[_hoy] = lambda: date(...)`). Sin
    eso, el camino express solo se podria ejercitar los martes y los viernes,
    que es cuando "manana" cae en dia de entrega.
    """
    return hoy_arg()


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
    hoy: date = Depends(_hoy),
):
    if data.fecha_entrega.weekday() not in VALID_DELIVERY_DAYS:
        raise HTTPException(
            status_code=422,
            detail="La fecha de entrega debe ser miércoles o sábado",
        )

    # Hasta el 2026-11-07 esto no se validaba en el servidor: la regla de las
    # 48h vivia solo en el calendario del portal, asi que un POST armado a
    # mano pedia para manana sin consecuencia. Ahora que ese tramo cuesta un
    # 5%, dejarlo sin validar seria dejar el recargo a eleccion del cliente.
    anticipacion = evaluar(data.fecha_entrega, hoy)
    if not anticipacion.se_puede_pedir:
        raise HTTPException(
            status_code=422,
            detail=(
                "Ya no se puede pedir para esa fecha: hace falta al menos "
                "1 día de anticipación. Elegí la siguiente fecha disponible."
            ),
        )

    if not data.lineas:
        raise HTTPException(status_code=422, detail="El pedido debe tener al menos una línea")

    subtotal_productos = 0.0
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
        subtotal_productos += subtotal
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

    subtotal_productos = round(subtotal_productos, 2)
    recargo_monto = calcular_recargo(subtotal_productos, anticipacion)

    pedido = PedidoCliente(
        cliente_id=cliente.id,
        fecha_entrega=data.fecha_entrega,
        notas=data.notas,
        total=round(subtotal_productos + recargo_monto, 2),
        recargo_pct=anticipacion.recargo_pct,
        recargo_monto=recargo_monto,
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
        recargo_monto=pedido.recargo_monto,
        notas=pedido.notas,
    )
    return construir_pedido_out(pedido)


class _ConfigPedidosOut(BaseModel):
    recargo_express_pct: float
    dias_anticipacion_normal: int
    hoy: date


@router.get("/config", response_model=_ConfigPedidosOut)
def get_config_pedidos(
    cliente: ClienteB2B = Depends(get_cliente_aprobado),
    hoy: date = Depends(_hoy),
):
    """Lo que el portal necesita para avisar del recargo ANTES de confirmar.

    Existe para que el porcentaje no quede escrito tambien en el frontend. El
    numero va a cambiar, y una copia en el navegador es una copia que el dia
    del cambio sigue diciendo 5 mientras el servidor ya cobra 7.

    `hoy` viaja tambien a proposito: si el calendario clasificara los dias con
    el reloj del dispositivo, un cliente con la hora mal puesta -- o
    simplemente en otro huso -- veria habilitadas fechas que el backend va a
    rechazar. Mandando el mismo "hoy" que usa la validacion, las dos mitades
    no pueden discrepar.

    Registrado ANTES de `/{pedido_id}` para que "config" no entre por esa ruta
    e intente parsearse como int.
    """
    return _ConfigPedidosOut(
        recargo_express_pct=RECARGO_EXPRESS_PCT,
        dias_anticipacion_normal=DIAS_ANTICIPACION_NORMAL,
        hoy=hoy,
    )


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
