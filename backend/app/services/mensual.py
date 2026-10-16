"""Monthly statistics for the home dashboard.

Lives in services/ rather than in the router because the delicate parts are the
money arithmetic and the month boundaries, and here they can be tested directly
without HTTP or auth (same reasoning as test_costes.py).

Things worth knowing before changing any of this:

* Bucketing happens in Python, not SQL -- same convention as mermas.analisis
  (`_inicio_periodo`). The rows for the whole range are fetched ONCE and grouped
  in memory: 9 queries total, however many months are requested.

* "Ventas" is TWO channels summed: EntregaB2B and PedidoCliente (the portal).
  Both point at productos_catalogo and at clientes_b2b, so they group cleanly.
  Both filter estado == "entregado" -- a pending order is not a sale.

* Counter sales DO NOT exist in this system, so every sales total understates
  what was really sold. Surfaced in `advertencias` so the UI can say so.

* Cost of goods comes from the snapshot frozen at delivery time
  (`costo_unitario_snapshot`). For sales that predate that column, each
  ingredient's price is reconstructed at the delivery date from HistorialPrecio
  (costes.precio_compra_en). Today's cost is NEVER used: prices moved hard here
  (Harina Integral +92%, Miel -46%), so costing August at October's prices would
  invent a margin.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models import (
    ClienteB2B,
    EntregaB2B,
    HistorialPrecio,
    Ingrediente,
    LineaEntregaB2B,
    LineaPedido,
    LineaPedidoCliente,
    MermaRegistro,
    Pedido,
    PedidoCliente,
    ProductoCatalogo,
    Proveedor,
    Receta,
)
from app.services.costes import costo_receta, receta_incompleta

TOP_N = 10


# ── month boundaries ──────────────────────────────────────────────────────────
# `hoy` is passed in rather than calling date.today() inside, so the month edges
# can be tested without freezing the clock.


@dataclass(frozen=True)
class RangoMes:
    inicio: date
    fin: date  # last day of the month, or `hoy` while the month is in progress
    clave: str  # "2026-10"
    es_parcial: bool
    dias_transcurridos: int
    dias_totales: int


def rango_mes(anio: int, mes: int, *, hoy: date) -> RangoMes:
    dias_totales = calendar.monthrange(anio, mes)[1]
    inicio = date(anio, mes, 1)
    ultimo = date(anio, mes, dias_totales)
    en_curso = (anio, mes) == (hoy.year, hoy.month)
    fin = hoy if en_curso else ultimo
    return RangoMes(
        inicio=inicio,
        fin=fin,
        clave=f"{anio:04d}-{mes:02d}",
        es_parcial=en_curso,
        dias_transcurridos=fin.day if en_curso else dias_totales,
        dias_totales=dias_totales,
    )


def ultimos_n_meses(n: int, *, hoy: date) -> list[RangoMes]:
    """Oldest to newest; the last one is the month in progress."""
    out = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        out.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return [rango_mes(a, m, hoy=hoy) for a, m in reversed(out)]


# ── raw rows ──────────────────────────────────────────────────────────────────


@dataclass
class _LineaVenta:
    fecha: date
    clave_mes: str
    canal: str  # "b2b" | "portal"
    cliente_id: int | None
    producto_id: int
    cantidad: float
    monto: float
    costo_snapshot: float | None


@dataclass
class _LineaCompra:
    clave_mes: str
    pedido_id: int
    ingrediente_id: int
    proveedor_id: int | None
    cantidad: float
    monto: float | None  # None = this line's cost is unknown


def _clave(f: date) -> str:
    return f"{f.year:04d}-{f.month:02d}"


def _ventas(db: Session, desde: date, hasta: date) -> list[_LineaVenta]:
    out: list[_LineaVenta] = []

    b2b = (
        db.query(LineaEntregaB2B, EntregaB2B)
        .join(EntregaB2B, EntregaB2B.id == LineaEntregaB2B.entrega_id)
        .filter(
            EntregaB2B.estado == "entregado",
            EntregaB2B.fecha_entrega >= desde,
            EntregaB2B.fecha_entrega <= hasta,
        )
        .all()
    )
    for l, e in b2b:
        out.append(_LineaVenta(
            fecha=e.fecha_entrega, clave_mes=_clave(e.fecha_entrega), canal="b2b",
            cliente_id=e.cliente_b2b_id, producto_id=l.producto_id,
            cantidad=l.cantidad or 0,
            monto=(l.cantidad or 0) * (l.precio_unitario or 0),
            costo_snapshot=l.costo_unitario_snapshot,
        ))

    portal = (
        db.query(LineaPedidoCliente, PedidoCliente)
        .join(PedidoCliente, PedidoCliente.id == LineaPedidoCliente.pedido_cliente_id)
        .filter(
            PedidoCliente.estado == "entregado",
            PedidoCliente.fecha_entrega >= desde,
            PedidoCliente.fecha_entrega <= hasta,
        )
        .all()
    )
    for l, p in portal:
        out.append(_LineaVenta(
            fecha=p.fecha_entrega, clave_mes=_clave(p.fecha_entrega), canal="portal",
            cliente_id=p.cliente_id, producto_id=l.producto_id,
            cantidad=l.cantidad or 0,
            # the portal already stores a computed subtotal, and it's immutable
            monto=l.subtotal or 0,
            costo_snapshot=l.costo_unitario_snapshot,
        ))
    return out


def _compras(db: Session, desde: date, hasta: date) -> list[_LineaCompra]:
    filas = (
        db.query(LineaPedido, Pedido)
        .join(Pedido, Pedido.id == LineaPedido.pedido_id)
        .filter(
            Pedido.estado == "recibido",
            Pedido.fecha_recepcion >= desde,
            Pedido.fecha_recepcion <= hasta,
        )
        .all()
    )
    out = []
    for l, p in filas:
        # Both nullable, and either one means we don't know what this line cost.
        # monto stays None instead of collapsing to 0 so callers can sum while
        # ignoring it AND count the gap from the same rows.
        #
        # Deliberately does NOT fall back to cantidad_pedida when
        # cantidad_recibida is NULL: the raw SQL this replaced (used by
        # /api/dashboard/flujo) multiplied by NULL and let SUM drop the row, so
        # substituting the ordered quantity would silently change a historical
        # `comprado_total_ars` that someone may already have on record.
        if l.precio_unitario is None or l.cantidad_recibida is None:
            monto = None
        else:
            monto = l.cantidad_recibida * l.precio_unitario
        out.append(_LineaCompra(
            clave_mes=_clave(p.fecha_recepcion), pedido_id=p.id,
            ingrediente_id=l.ingrediente_id,
            proveedor_id=p.proveedor_id,
            cantidad=(l.cantidad_recibida if l.cantidad_recibida is not None else l.cantidad_pedida) or 0,
            monto=monto,
        ))
    return out


def monto_compras_recibidas(db: Session, desde: date, hasta: date) -> float:
    """What was spent on received orders between two dates.

    One definition of "what we spent", shared with GET /api/dashboard/flujo,
    which used to carry its own copy of this query. Two copies drift.
    """
    return sum(c.monto or 0 for c in _compras(db, desde, hasta))


# ── compras por mes ───────────────────────────────────────────────────────────


@dataclass
class _AcumCompras:
    total: float = 0.0
    lineas_sin_precio: int = 0
    pedidos: set = field(default_factory=set)  # ids, para contar pedidos y no lineas
    por_ingrediente: dict = field(default_factory=lambda: defaultdict(float))
    por_proveedor: dict = field(default_factory=lambda: defaultdict(float))
    cambios_precio: list = field(default_factory=list)


def resumen_compras_mensual(db: Session, *, meses: int = 6, hoy: date | None = None) -> dict:
    """La mitad de compras de un mes: gasto, desgloses y cambios de precio.

    El UNICO lugar que le da forma a compras_total_ars / top_ingredientes /
    por_proveedor / cambios_precio. resumen_mensual() compone su salida desde
    aca en vez de quedarse con una segunda copia, asi que la pantalla de
    Compras y la de inicio no pueden mostrar numeros distintos para el mismo
    mes -- lo que cambia entre las dos es QUE se muestra, no CUANTO.

    Separado porque tiene una barrera de permisos mas baja: no expone ventas,
    margen ni concentracion de clientes, asi que lo ve cualquier empleado
    (ver GET /api/dashboard/compras-mensual), mientras resumen_mensual() sigue
    siendo solo-admin.
    """
    hoy = hoy or date.today()
    rangos = ultimos_n_meses(meses, hoy=hoy)
    desde, hasta = rangos[0].inicio, rangos[-1].fin

    compras = _compras(db, desde, hasta)
    cambios = (
        db.query(HistorialPrecio)
        .options(joinedload(HistorialPrecio.ingrediente_rel))
        .filter(HistorialPrecio.fecha_cambio >= desde, HistorialPrecio.fecha_cambio <= hasta)
        .order_by(HistorialPrecio.fecha_cambio)
        .all()
    )
    ingredientes = {i.id: i.nombre for i in db.query(Ingrediente).all()}
    proveedores = {p.id: p.nombre for p in db.query(Proveedor).all()}

    acum: dict[str, _AcumCompras] = defaultdict(_AcumCompras)

    for c in compras:
        a = acum[c.clave_mes]
        # Un pedido cuenta si le gastamos plata, aunque alguna de sus lineas no
        # tenga precio: lo que se cuenta es el pedido, no la linea.
        a.pedidos.add(c.pedido_id)
        if c.monto is None:
            a.lineas_sin_precio += 1
        else:
            a.total += c.monto
            a.por_ingrediente[c.ingrediente_id] += c.monto
            if c.proveedor_id:
                a.por_proveedor[c.proveedor_id] += c.monto

    for h in cambios:
        a = acum[_clave(h.fecha_cambio)]
        ant = h.precio_anterior or 0
        a.cambios_precio.append({
            "ingrediente_id": h.ingrediente_id,
            "nombre": ingredientes.get(h.ingrediente_id, f"#{h.ingrediente_id}"),
            "precio_anterior": round(ant, 2),
            "precio_nuevo": round(h.precio_nuevo or 0, 2),
            "fecha_cambio": str(h.fecha_cambio),
            "variacion_pct": round(100 * ((h.precio_nuevo or 0) - ant) / ant, 1) if ant else None,
        })

    meses_out = []
    for r in rangos:
        a = acum.get(r.clave, _AcumCompras())
        meses_out.append({
            "mes": r.clave,
            "es_parcial": r.es_parcial,
            "dias_transcurridos": r.dias_transcurridos,
            "dias_totales": r.dias_totales,
            "compras_total_ars": round(a.total, 2),
            "pedidos_recibidos": len(a.pedidos),
            "top_ingredientes": [
                {
                    "ingrediente_id": iid,
                    "nombre": ingredientes.get(iid, f"#{iid}"),
                    "monto_ars": round(monto, 2),
                }
                for iid, monto in sorted(a.por_ingrediente.items(), key=lambda kv: -kv[1])[:TOP_N]
            ],
            # Sin cortar en TOP_N, a diferencia de top_ingredientes: son pocos
            # proveedores y se quieren todos.
            "por_proveedor": [
                {
                    "proveedor_id": pid,
                    "nombre": proveedores.get(pid, f"#{pid}"),
                    "monto_ars": round(monto, 2),
                }
                for pid, monto in sorted(a.por_proveedor.items(), key=lambda kv: -kv[1])
            ],
            "cambios_precio": a.cambios_precio,
            "lineas_sin_precio": a.lineas_sin_precio,
        })

    return {
        "periodo": {"desde": str(desde), "hasta": str(hasta), "meses": meses},
        "meses": meses_out,
    }


# ── cost of goods sold ────────────────────────────────────────────────────────


def _costo_unitario(
    db: Session,
    linea: _LineaVenta,
    catalogo: dict[int, ProductoCatalogo],
    cache: dict[tuple[int, date], float | None],
) -> float | None:
    """Unit cost of a sold line, or None when it cannot be known.

    Priority:
      1. the snapshot frozen at delivery time -- immutable, the real figure
      2. reconstruction at the delivery date via HistorialPrecio
    Never today's cost.

    Cached by (producto, exact date), NOT by month. A monthly cache would let
    whichever line happens to be iterated first decide the cost for the whole
    month -- and iteration order here is insertion order, not chronological,
    because deliveries are routinely entered days late. A price change mid-month
    would then be applied to sales on the wrong side of it, which is the same
    failure threading `fecha` exists to prevent, just at a smaller scale.
    """
    if linea.costo_snapshot is not None:
        return linea.costo_snapshot

    key = (linea.producto_id, linea.fecha)
    if key in cache:
        return cache[key]

    cat = catalogo.get(linea.producto_id)
    costo: float | None = None
    if cat and cat.receta_id:
        receta = db.get(Receta, cat.receta_id)
        # An incomplete tree gives a number that is simply too low, not zero --
        # Cinnamon Roll comes out at 33.91 against a 1.000 price (96.6% margin)
        # because its bastón, two levels down, has no lines. Checking only for
        # cost == 0 lets that through and makes it look like the star product.
        if receta and not receta_incompleta(receta, db):
            _, por_porcion = costo_receta(receta, db, fecha=linea.fecha)
            costo = por_porcion if por_porcion and por_porcion > 0 else None
    cache[key] = costo
    return costo


# ── assembling each month ─────────────────────────────────────────────────────


@dataclass
class _Acum:
    ventas_b2b: float = 0.0
    ventas_portal: float = 0.0
    unidades: float = 0.0
    lineas_precio_cero: int = 0
    por_producto: dict = field(default_factory=lambda: defaultdict(lambda: {"unidades": 0.0, "monto": 0.0}))
    por_cliente: dict = field(default_factory=lambda: defaultdict(float))
    cogs: float = 0.0
    # Revenue of the lines whose cost IS known. The margin % is computed over
    # this, not over total sales: counting a line's revenue while dropping its
    # cost would inflate the margin instead of flagging the gap.
    ventas_costeadas: float = 0.0
    lineas_sin_costo: int = 0
    mermas: float = 0.0
    mermas_count: int = 0


def resumen_mensual(db: Session, *, meses: int = 6, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    rangos = ultimos_n_meses(meses, hoy=hoy)
    desde, hasta = rangos[0].inicio, rangos[-1].fin

    ventas = _ventas(db, desde, hasta)
    mermas = (
        db.query(MermaRegistro)
        .filter(MermaRegistro.fecha >= desde, MermaRegistro.fecha <= hasta)
        .all()
    )

    # Toda la mitad de compras sale de una sola implementacion compartida con
    # GET /api/dashboard/compras-mensual, que es lo que mira la pantalla de
    # Compras. Aca solo se la indexa por mes para armar la salida de siempre.
    compras_por_mes = {
        m["mes"]: m
        for m in resumen_compras_mensual(db, meses=meses, hoy=hoy)["meses"]
    }

    # small tables for a single bakery: loaded whole, once
    catalogo = {p.id: p for p in db.query(ProductoCatalogo).all()}
    clientes = {c.id: c.nombre for c in db.query(ClienteB2B).all()}

    acum: dict[str, _Acum] = defaultdict(_Acum)
    cache_costo: dict[tuple[int, date], float | None] = {}

    for v in ventas:
        a = acum[v.clave_mes]
        if v.canal == "b2b":
            a.ventas_b2b += v.monto
        else:
            a.ventas_portal += v.monto
        a.unidades += v.cantidad
        if v.monto == 0 and v.cantidad:
            a.lineas_precio_cero += 1
        p = a.por_producto[v.producto_id]
        p["unidades"] += v.cantidad
        p["monto"] += v.monto
        if v.cliente_id:
            a.por_cliente[v.cliente_id] += v.monto
        cu = _costo_unitario(db, v, catalogo, cache_costo)
        if cu is None:
            a.lineas_sin_costo += 1
        else:
            a.cogs += cu * v.cantidad
            a.ventas_costeadas += v.monto

    for m in mermas:
        a = acum[_clave(m.fecha)]
        a.mermas += m.coste_total or 0
        a.mermas_count += 1

    meses_out = []
    for r in rangos:
        a = acum.get(r.clave, _Acum())
        compras = compras_por_mes[r.clave]
        ventas_total = a.ventas_b2b + a.ventas_portal
        # over the costed subset only -- see _Acum.ventas_costeadas
        margen = a.ventas_costeadas - a.cogs
        meses_out.append({
            "mes": r.clave,
            "es_parcial": r.es_parcial,
            "dias_transcurridos": r.dias_transcurridos,
            "dias_totales": r.dias_totales,
            "ventas": {
                "total_ars": round(ventas_total, 2),
                "b2b_ars": round(a.ventas_b2b, 2),
                "portal_ars": round(a.ventas_portal, 2),
                "unidades": round(a.unidades, 2),
            },
            "compras_total_ars": compras["compras_total_ars"],
            "margen": {
                "cogs_ars": round(a.cogs, 2),
                "bruto_ars": round(margen, 2),
                "bruto_pct": round(100 * margen / a.ventas_costeadas, 1) if a.ventas_costeadas else None,
                # the slice of sales this margin actually covers. Anything under
                # 100% means some lines could not be costed, so the figure
                # describes part of the month, not all of it.
                "ventas_costeadas_ars": round(a.ventas_costeadas, 2),
                "cobertura_pct": round(100 * a.ventas_costeadas / ventas_total, 1) if ventas_total else None,
                "lineas_sin_costo": a.lineas_sin_costo,
            },
            "mermas": {
                "total_ars": round(a.mermas, 2),
                "registros": a.mermas_count,
                "pct_sobre_ventas": round(100 * a.mermas / ventas_total, 2) if ventas_total else None,
            },
            "top_productos": [
                {
                    "producto_id": pid,
                    "nombre": catalogo[pid].nombre if pid in catalogo else f"#{pid}",
                    "unidades": round(d["unidades"], 2),
                    "monto_ars": round(d["monto"], 2),
                }
                for pid, d in sorted(a.por_producto.items(), key=lambda kv: -kv[1]["monto"])[:TOP_N]
            ],
            "top_ingredientes": compras["top_ingredientes"],
            "por_cliente": [
                {
                    "cliente_id": cid,
                    "nombre": clientes.get(cid, f"#{cid}"),
                    "monto_ars": round(monto, 2),
                    "pct": round(100 * monto / ventas_total, 1) if ventas_total else None,
                }
                for cid, monto in sorted(a.por_cliente.items(), key=lambda kv: -kv[1])
            ],
            "por_proveedor": compras["por_proveedor"],
            "cambios_precio": compras["cambios_precio"],
            "avisos": {
                "lineas_precio_cero": a.lineas_precio_cero,
                "lineas_compra_sin_precio": compras["lineas_sin_precio"],
            },
        })

    return {
        "periodo": {"desde": str(desde), "hasta": str(hasta), "meses": meses},
        "meses": meses_out,
        "advertencias": {
            # not a bug or a data gap: the model simply does not exist
            "sin_ventas_mostrador": True,
            "margen_reconstruido": True,
        },
    }
