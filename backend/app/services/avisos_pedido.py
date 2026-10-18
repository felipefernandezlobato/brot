"""Aviso al obrador cuando entra un pedido por la web.

Un pedido del portal no le avisa a nadie: se queda en la base esperando que
alguien abra la pantalla de pedidos. Eso funciono mientras el portal no se
usaba, pero desde que Olula pide por ahi, un pedido cargado un viernes a la
noche para el sabado puede no verlo nadie hasta despues de amasar.

Quien necesita enterarse es el panadero, porque lo que cambia con el pedido es
lo que hay que preparar. De ahi que el correo lleve las cantidades primero y
todo lo demas despues.

**El destino sale de `EMAIL_PANADERO`, no esta escrito en el codigo.** Este
repo es publico en GitHub, asi que una direccion personal escrita aca queda
para siempre en el historial y a mano de cualquier recolector de correos para
spam. Admite varias separadas por coma, para sumar gente sin tocar el codigo.

Sin configurar no manda nada y lo deja dicho en el log. Es deliberado, igual
que en services/email.py: el pedido se guarda igual. Un fallo de correo no
puede perder un pedido, asi que esto corre en segundo plano DESPUES del commit
(ver create_pedido) y nunca dentro de la transaccion.
"""

import logging
import os
from datetime import date, datetime

from app.services.email import app_url, enviar_email

logger = logging.getLogger(__name__)

DIAS = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
        4: "viernes", 5: "sabado", 6: "domingo"}


def destinos_panadero() -> list[str]:
    crudo = os.getenv("EMAIL_PANADERO") or ""
    return [d.strip() for d in crudo.split(",") if d.strip()]


def formato_pesos(monto: float) -> str:
    """1234.5 -> "1.234,50". Como se escribe la plata aca, igual que formatARS
    en el frontend: punto para los miles y coma para los decimales."""
    entero, dec = f"{monto:,.2f}".split(".")
    return f"{entero.replace(',', '.')},{dec}"


def formato_cantidad(n: float) -> str:
    """Sin decimales cuando es entero: "24 u", no "24.0 u"."""
    return str(int(n)) if float(n).is_integer() else formato_pesos(n)


def formato_fecha(d: date) -> str:
    return f"{DIAS.get(d.weekday(), '')} {d.strftime('%d/%m/%Y')}".strip()


def avisar_pedido_nuevo(
    pedido_id: int,
    cliente: str,
    fecha_entrega: date,
    # `PedidoCliente.fecha_pedido` es un datetime (lleva la hora de carga),
    # a diferencia de `fecha_entrega`, que es un date pelado.
    fecha_pedido: datetime,
    lineas: list[tuple[str, float]],
    total: float,
    notas: str | None = None,
) -> bool:
    """Le avisa al panadero de un pedido nuevo del portal.

    Recibe datos planos y no objetos del ORM a proposito: corre en segundo
    plano, despues de que la peticion respondio y cerro su sesion de base, asi
    que cualquier atributo que no estuviera ya cargado explotaria al leerlo.
    Quien llama arma la lista mientras la sesion sigue viva.

    `lineas` es (nombre, cantidad) ya en el orden en que se mostraran. Todo el
    catalogo se vende por unidad -- `ProductoCatalogo` no tiene columna de
    unidad -- asi que la "u" va fija.
    """
    destinos = destinos_panadero()
    if not destinos:
        logger.warning(
            "EMAIL_PANADERO sin configurar: no se avisa del pedido #%s de %s",
            pedido_id, cliente,
        )
        return False

    ancho = max((len(formato_cantidad(c)) for _, c in lineas), default=1)
    detalle = "\n".join(
        f"  {formato_cantidad(cant).rjust(ancho)} u  {nombre}"
        for nombre, cant in lineas
    ) or "  (el pedido entro sin lineas)"

    cuerpo = f"""Entro un pedido nuevo por la web.

  Cliente:  {cliente}
  Entrega:  {formato_fecha(fecha_entrega)}
  Pedido:   #{pedido_id}, cargado el {fecha_pedido.strftime('%d/%m/%Y')}

Lo que hay que preparar:

{detalle}

  Total: $ {formato_pesos(total)}
"""
    if notas:
        cuerpo += f"\nNota del cliente:\n  {notas}\n"
    cuerpo += f"""
Lo ves en {app_url()}/entregas

BROT La Panaderia
"""

    # Un envio por destino: si el segundo falla, el primero ya salio. Mandarlos
    # juntos en un To: haria que un rebote se llevara el aviso de todos.
    resultados = [
        enviar_email(
            destino,
            f"Pedido de {cliente} para el {formato_fecha(fecha_entrega)}",
            cuerpo,
        )
        for destino in destinos
    ]
    return any(resultados)
