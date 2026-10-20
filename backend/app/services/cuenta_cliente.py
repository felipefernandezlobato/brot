"""La cuenta de un cliente: qué pidió, cuánto lleva, qué compra más.

Hasta ahora esto no se podía ver desde ningún sitio. El dato existía repartido
en cuatro pantallas y ninguna respondía "¿qué me compró Creme?": la lista de
clientes son datos de contacto sin pedidos, el Historial de /entregas apila a
todos los clientes juntos y solo cuenta B2B sin importes, Volumen da una fila
agregada, y las ventas por cliente del inicio son un porcentaje del mes sin
forma de entrar al detalle.

**No calcula nada nuevo.** Los importes salen de `mensual.ventas()`, que es LA
definición de qué cuenta como venta, y el historial de
`pedidos_vista.historial_de_cliente()`, el mismo que ve el propio cliente en
"Mis Pedidos". Esa reutilización es el punto: el importe de una entrega está
escrito a mano en cinco sitios del proyecto y una ficha con su propia fórmula
acabaría contradiciendo al resumen mensual sin que nadie se diera cuenta.

Deliberadamente NO expone costo ni margen. Felipe lo acotó así el 2026-10-20, y
hay un motivo técnico además del de alcance: `costo_unitario_snapshot` viene
`NULL` en las líneas viejas y en los productos con receta incompleta, así que
un margen por cliente honesto exige arrastrar la cobertura igual que hace
`resumen_mensual` — es una función aparte, no un campo más.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import ClienteB2B
from app.services.mensual import ventas
from app.services.pedidos_vista import historial_de_cliente, nombres_productos

# El rango por defecto es "todo", y por eso el tope es una fecha absurda en vez
# de hoy. Las entregas y los pedidos del portal se cargan con la fecha de
# entrega PRÓXIMA (miércoles o sábado), así que uno marcado entregado por
# adelantado tiene `fecha_entrega` en el futuro: con `hasta = hoy` quedaría
# fuera del facturado del cliente mientras sí aparece en las estadísticas del
# mes, y nadie entendería por qué los dos números no cuadran. Hoy no hay
# ninguna así en producción, pero es cuestión de que alguien adelante un clic.
DESDE_SIEMPRE = date(2020, 1, 1)
HASTA_SIEMPRE = date(2100, 1, 1)

TOP_N = 8


@dataclass
class _Agregado:
    facturado: float
    pedidos: int
    primera: date | None
    ultima: date | None


def _resumen(lineas, entregados) -> _Agregado:
    """La plata sale de las líneas de venta; el número de pedidos, del historial.

    Son dos fuentes a propósito, y no por descuido. `ventas()` da líneas
    planas sin id de pedido, así que ahí no hay forma de contar pedidos: el
    primer intento los distinguió por `(canal, fecha)` y estaba MAL —
    **Creme tiene dos entregas el 2026-08-15**, así que su ficha habría dicho
    18 pedidos en vez de 19. El historial sí trae `origen` + `id`, que es la
    única clave única cuando se mezclan las dos tablas.

    **Se descartan los pedidos sin líneas**, que es lo que mantiene las dos
    fuentes de acuerdo. Una `EntregaB2B` entregada y vacía es alcanzable:
    `create_entrega_b2b` no exige líneas (el portal sí) y `update_entrega_b2b`
    acepta `lineas: []`, que borra las que había. Esa fila no genera ninguna
    `LineaVenta`, así que aportaría 0 al facturado mientras sumaba 1 al
    divisor: el ticket promedio saldría diluido por pedidos que no facturaron
    nada. Hoy no hay ninguna así en producción.
    """
    facturado = sum(l.monto or 0 for l in lineas)
    fechas = sorted(l.fecha for l in lineas)
    return _Agregado(
        facturado=round(facturado, 2),
        pedidos=len({(p.origen, p.id) for p in entregados if p.lineas}),
        primera=fechas[0] if fechas else None,
        ultima=fechas[-1] if fechas else None,
    )


def _top_productos(lineas, nombres: dict[int, str]) -> list[dict]:
    """Qué le vendemos más a este cliente, por plata.

    Por plata y no por unidades a propósito: ordenado por cantidad, un cliente
    que compra 400 medialunas de 1.110 parece comprar más que uno que se lleva
    30 focaccias de 14.160, y es al revés. La cantidad va igual en cada fila,
    que es el dato que sirve para producir.
    """
    acc: dict[int, dict] = {}
    for l in lineas:
        fila = acc.setdefault(
            l.producto_id,
            {"producto_id": l.producto_id, "producto": nombres.get(l.producto_id),
             "cantidad": 0.0, "monto_ars": 0.0},
        )
        fila["cantidad"] += l.cantidad or 0
        fila["monto_ars"] += l.monto or 0
    filas = sorted(acc.values(), key=lambda f: f["monto_ars"], reverse=True)
    for f in filas:
        f["cantidad"] = round(f["cantidad"], 2)
        f["monto_ars"] = round(f["monto_ars"], 2)
    return filas[:TOP_N]


def cuenta_de_cliente(
    db: Session,
    cliente: ClienteB2B,
    desde: date | None = None,
    hasta: date | None = None,
) -> dict:
    """Todo lo de un cliente en una sola llamada, al estilo de
    `GET /api/recetas/{id}/completo`: la pantalla no debería tener que pedir
    cuatro cosas y cruzarlas ella.

    `resumen` y `top_productos` solo cuentan lo entregado, porque salen de
    `ventas()`. `historial` en cambio trae TODO, incluido lo pendiente — si no,
    un pedido que entró ayer y todavía no salió no aparecería en ningún sitio,
    que es precisamente cuando uno mira la ficha.
    """
    desde = desde or DESDE_SIEMPRE
    hasta = hasta or HASTA_SIEMPRE

    mias = [l for l in ventas(db, desde, hasta) if l.cliente_id == cliente.id]
    nombres = nombres_productos(db)
    historial = historial_de_cliente(db, cliente.id)
    # Mismo filtro que `ventas()` por los dos lados: entregado, y dentro del
    # rango por fecha de entrega.
    entregados = [
        p for p in historial
        if p.estado == "entregado" and desde <= p.fecha_entrega <= hasta
    ]
    agg = _resumen(mias, entregados)

    return {
        "cliente": {
            "id": cliente.id,
            "nombre": cliente.nombre,
            "email": cliente.email,
            "telefono": cliente.telefono,
            "direccion": cliente.direccion,
            "contacto": cliente.contacto,
            "notas": cliente.notas,
            "dia_entrega_preferido": cliente.dia_entrega_preferido,
            "is_active": cliente.is_active,
            # Mismo trio que `_cliente_out` en el router: si entra al portal,
            # si confirmo su correo y si esta aprobado.
            "tiene_acceso": bool(cliente.password_hash),
            "email_verificado": bool(cliente.email_verificado_at),
            "aprobado": bool(cliente.aprobado_at),
            "puede_pedir": cliente.puede_pedir,
        },
        "resumen": {
            "facturado_ars": agg.facturado,
            "pedidos": agg.pedidos,
            # None y no 0 cuando no hay nada entregado: un ticket medio de cero
            # no existe, y la pantalla tiene que poder escribir "—".
            "ticket_promedio_ars": round(agg.facturado / agg.pedidos, 2) if agg.pedidos else None,
            "primera_entrega": agg.primera.isoformat() if agg.primera else None,
            "ultima_entrega": agg.ultima.isoformat() if agg.ultima else None,
        },
        "top_productos": _top_productos(mias, nombres),
        "historial": [p.model_dump(mode="json") for p in historial],
        "advertencias": {
            # El mostrador no se registra en ninguna parte, asi que cualquier
            # total de ventas se queda corto. Lo dice tambien el resumen
            # mensual; repetirlo aca evita que esta pantalla se lea como si
            # fuera la facturacion completa del cliente.
            "sin_ventas_mostrador": True,
        },
    }
