"""Un pedido y una entrega, vistos con la misma forma.

Al cliente le da igual si lo que pidió entró por la web (`PedidoCliente`) o si
el obrador le cargó la entrega a mano (`EntregaB2B`): quiere una sola lista
ordenada por fecha. Estas dos funciones traducen ambas tablas al mismo
`PedidoClienteOut`, con `origen` como único distintivo.

**Vivían dentro de `routers/pedidos_clientes.py`.** Se mudaron acá cuando la
ficha de cliente del admin necesitó exactamente la misma mezcla: un servicio
importando funciones privadas de un router es la dependencia al revés, y
copiarlas habría dejado dos definiciones del total que se desincronizan a la
primera. Son funciones puras — no miran la sesión ni el usuario — así que la
mudanza no cambia nada de comportamiento.

Ojo con las claves: `EntregaB2B` y `PedidoCliente` tienen secuencias de id
distintas, así que sus ids SE SOLAPAN. Lo único que identifica una fila de
forma única en la lista mezclada es `origen` + `id`.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import EntregaB2B, PedidoCliente, ProductoCatalogo
from app.schemas import PedidoClienteOut


def nombres_productos(db: Session) -> dict[int, str]:
    """Catálogo entero en un diccionario: las líneas guardan `producto_id`, no
    el nombre, y resolverlos de uno en uno es un N+1 por línea."""
    return {p.id: p.nombre for p in db.query(ProductoCatalogo).all()}


def construir_pedido_out(
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


def construir_entrega_out(
    entrega: EntregaB2B, nombres: Optional[dict[int, str]] = None
) -> PedidoClienteOut:
    """Una EntregaB2B vista como pedido.

    `pedidos_clientes` solo recoge lo que el cliente pide desde la web, pero a
    los clientes B2B el obrador les carga las entregas a mano. Con la tabla del
    portal vacía, "Mis Pedidos" salía vacío para todo el mundo aunque Olula
    llevara doce entregas. Las dos tablas apuntan al mismo `clientes_b2b.id`,
    así que se pueden mezclar directamente.

    **El total se calcula acá y no se lee de ningún sitio**: a diferencia de
    `PedidoCliente.total`, que es una columna, `EntregaB2B` no guarda su
    importe en ninguna parte. La fórmula es la misma que usa
    `services/mensual.ventas()` para el canal b2b.
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


def historial_de_cliente(db: Session, cliente_id: int) -> list[PedidoClienteOut]:
    """Todo lo que ese cliente pidió o recibió, lo más reciente primero.

    Ordena por `fecha_entrega` y desempata por id para que el orden no baile
    entre recargas cuando hay varios el mismo día. Es la misma mezcla que ve el
    cliente en "Mis Pedidos" y la que ve el admin en su ficha, de una sola
    definición: si divergieran, el admin y el cliente verían historiales
    distintos del mismo cliente.
    """
    nombres = nombres_productos(db)
    pedidos = db.query(PedidoCliente).filter(PedidoCliente.cliente_id == cliente_id).all()
    entregas = db.query(EntregaB2B).filter(EntregaB2B.cliente_b2b_id == cliente_id).all()
    salida = (
        [construir_pedido_out(p, nombres) for p in pedidos]
        + [construir_entrega_out(e, nombres) for e in entregas]
    )
    salida.sort(key=lambda p: (p.fecha_entrega, p.id), reverse=True)
    return salida
