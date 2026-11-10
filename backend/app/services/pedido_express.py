"""Cuando un pedido del portal es "express" y cuanto cuesta serlo.

Hasta el 2026-11-07 habia que pedir con 2 dias de antelacion. Ahora se puede
pedir con 1, pagando un recargo. Esta es LA definicion de las dos mitades de
esa regla -- el corte y el porcentaje -- y tiene dos consumidores desde el dia
uno: el backend que cobra y el portal que avisa antes de cobrar. Por eso el
frontend no lo reimplementa: lo pide por `GET /api/cliente/pedidos/config`.
CLAUDE.md documenta tres incidentes distintos causados por la misma regla
escrita en dos sitios que se desincronizaron (el consumo declarado, los
estados de un pedido, NAV_ITEMS); el porcentaje de un recargo, que por
definicion va a cambiar, es el peor candidato posible para una cuarta copia.

**La zona horaria no es un detalle aca, es la regla misma.** Render corre en
UTC y la panaderia esta en UTC-3, asi que entre las 21:00 y la medianoche
argentina el servidor ya cree que es el dia siguiente. Con `date.today()`
pelado, un cliente que pide el martes a las 22:00 para el miercoles seria
rechazado por "pedir para el mismo dia" -- justo la franja donde un pedido
express tiene mas sentido -- mientras su navegador, que si calcula en hora
local, se lo habia permitido. `hoy_arg()` existe por eso y tiene un test que
lo fija (`test_el_borde_utc_no_adelanta_el_dia`).

El resto del sistema sigue leyendo `date.today()` en UTC; arreglarlo entero es
otro trabajo, con riesgo sobre datos historicos. Aca se acota a esta regla.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

# Argentina no observa horario de verano desde 2009: UTC-3 fijo todo el año.
# Un offset fijo en vez de ZoneInfo("America/Argentina/Buenos_Aires") evita
# depender de que el paquete `tzdata` este en la imagen de Render para un caso
# que no lo necesita. Si el pais volviera a mover el huso, esta es la linea.
TZ_ARG = timezone(timedelta(hours=-3))

# El unico lugar donde vive este numero. Es un porcentaje (5.0 == 5%), no una
# fraccion: asi se lee igual en la base, en el payload y en la pantalla, y no
# hay forma de confundir 5 con 500%.
RECARGO_EXPRESS_PCT = 5.0

# Dias de antelacion que NO pagan recargo. Por debajo de esto (pero con al
# menos 1 dia) se puede pedir igual, con recargo.
DIAS_ANTICIPACION_NORMAL = 2


@dataclass(frozen=True)
class Anticipacion:
    """Como cae una fecha de entrega respecto de hoy."""

    dias: int
    se_puede_pedir: bool
    es_express: bool
    recargo_pct: float  # 0.0 cuando no es express


def hoy_arg(ahora: datetime | None = None) -> date:
    """El dia de hoy en hora de Argentina, no en la del servidor.

    `ahora` se inyecta en los tests; en produccion sale del reloj del proceso,
    que en Render esta en UTC.
    """
    base = ahora or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(TZ_ARG).date()


def evaluar(fecha_entrega: date, hoy: date) -> Anticipacion:
    """Clasifica una fecha de entrega en: no se puede / express / normal.

    "Hasta las 23:59 del dia anterior" no necesita mirar la hora: mientras siga
    siendo ese dia en Argentina, la resta de fechas sigue dando 1. El corte
    pedido ES el cambio de fecha local a medianoche, y comparar fechas ya lo
    expresa. Lo que si hay que hacer bien es calcular `hoy` en hora argentina,
    que es lo que hace `hoy_arg()`.
    """
    dias = (fecha_entrega - hoy).days
    if dias < 1:
        # Mismo dia o pasado. No se puede pedir ni pagando.
        return Anticipacion(dias=dias, se_puede_pedir=False, es_express=False, recargo_pct=0.0)
    if dias < DIAS_ANTICIPACION_NORMAL:
        return Anticipacion(
            dias=dias, se_puede_pedir=True, es_express=True, recargo_pct=RECARGO_EXPRESS_PCT
        )
    return Anticipacion(dias=dias, se_puede_pedir=True, es_express=False, recargo_pct=0.0)


def calcular_recargo(subtotal: float, anticipacion: Anticipacion) -> float:
    """El monto en pesos del recargo, o 0.0 si la fecha no es express."""
    if not anticipacion.es_express:
        return 0.0
    return round(subtotal * anticipacion.recargo_pct / 100, 2)
