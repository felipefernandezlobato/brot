"""Estadisticas mensuales para el panel de inicio.

Vive en services/ y no dentro del router porque la parte delicada es la
aritmetica de plata y los limites de mes, y asi se puede testear directo sin
levantar HTTP ni auth (mismo criterio que test_costes.py).

Decisiones que conviene conocer antes de tocar esto:

* El bucketeo es en Python, no en SQL — misma convencion que
  mermas.analisis (`_inicio_periodo`). Se traen las filas del rango completo
  UNA vez y se agrupan en memoria: 9 consultas en total, sin importar cuantos
  meses se pidan.

* "Ventas" son DOS canales que se suman: EntregaB2B y PedidoCliente (portal).
  Los dos apuntan a productos_catalogo y a clientes_b2b, asi que agrupan
  limpio. Ambos filtran estado == "entregado": lo pendiente no es venta.

* Las ventas de mostrador NO existen en el sistema, asi que todo total de
  ventas subestima la venta real. Se expone en `advertencias`.

* El costo de lo vendido sale del snapshot congelado al entregar
  (`costo_unitario_snapshot`); para las ventas anteriores a que eso existiera,
  se reconstruye el precio de cada ingrediente a la fecha de la entrega via
  HistorialPrecio (costes.precio_compra_en). NO se usa el costo de hoy: los
  precios se movieron fuerte (Harina Integral +92%, Miel -46%), asi que
  costear agosto con precios de octubre daria un margen inventado.
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
from app.services.costes import costo_receta

TOP_N = 10


# ── limites de mes ────────────────────────────────────────────────────────────
# `hoy` se recibe como parametro en vez de llamar a date.today() adentro, para
# que los bordes de mes se puedan testear sin congelar el reloj.


@dataclass(frozen=True)
class RangoMes:
    inicio: date
    fin: date  # ultimo dia del mes, o `hoy` si el mes esta en curso
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
    """Del mas viejo al mas nuevo; el ultimo es el mes en curso."""
    out = []
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        out.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    return [rango_mes(a, m, hoy=hoy) for a, m in reversed(out)]


# ── filas crudas ──────────────────────────────────────────────────────────────


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
    ingrediente_id: int
    proveedor_id: int | None
    cantidad: float
    monto: float | None  # None = la linea no tiene precio cargado


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
            # el portal ya guarda el subtotal calculado y es inmutable
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
        cantidad = l.cantidad_recibida if l.cantidad_recibida is not None else l.cantidad_pedida
        # precio_unitario es nullable: se deja monto=None en vez de 0 para poder
        # sumar ignorandolo Y contar el hueco desde las mismas filas
        monto = None if l.precio_unitario is None else (cantidad or 0) * l.precio_unitario
        out.append(_LineaCompra(
            clave_mes=_clave(p.fecha_recepcion), ingrediente_id=l.ingrediente_id,
            proveedor_id=p.proveedor_id, cantidad=cantidad or 0, monto=monto,
        ))
    return out


def monto_compras_recibidas(db: Session, desde: date, hasta: date) -> float:
    """Lo gastado en pedidos recibidos entre dos fechas.

    Una sola definicion de "lo que gastamos", compartida con
    GET /api/dashboard/flujo, que antes la tenia escrita aparte. Si hay dos,
    tarde o temprano dan distinto.
    """
    return sum(c.monto or 0 for c in _compras(db, desde, hasta))


# ── costo de lo vendido ───────────────────────────────────────────────────────


def _costo_unitario(
    db: Session,
    linea: _LineaVenta,
    catalogo: dict[int, ProductoCatalogo],
    cache: dict[tuple[int, str], float | None],
) -> float | None:
    """Costo por unidad de una linea vendida, o None si no se puede saber.

    Prioridad:
      1. el snapshot congelado al entregar — inmutable, es la verdad
      2. reconstruccion a la fecha de la entrega via HistorialPrecio
    Nunca el costo de hoy.

    La cache es por (producto, mes) y no por producto: dentro de un mes los
    precios casi no se mueven, y asi no se recalcula la receta por cada linea.
    """
    if linea.costo_snapshot is not None:
        return linea.costo_snapshot

    key = (linea.producto_id, linea.clave_mes)
    if key in cache:
        return cache[key]

    cat = catalogo.get(linea.producto_id)
    costo: float | None = None
    if cat and cat.receta_id:
        receta = db.get(Receta, cat.receta_id)
        if receta:
            _, por_porcion = costo_receta(receta, db, fecha=linea.fecha)
            # 0 significa "receta sin lineas", no "sale gratis"
            costo = por_porcion if por_porcion and por_porcion > 0 else None
    cache[key] = costo
    return costo


# ── armado del mes ────────────────────────────────────────────────────────────


@dataclass
class _Acum:
    ventas_b2b: float = 0.0
    ventas_portal: float = 0.0
    unidades: float = 0.0
    lineas_precio_cero: int = 0
    por_producto: dict = field(default_factory=lambda: defaultdict(lambda: {"unidades": 0.0, "monto": 0.0}))
    por_cliente: dict = field(default_factory=lambda: defaultdict(float))
    cogs: float = 0.0
    lineas_sin_costo: int = 0
    compras: float = 0.0
    lineas_sin_precio: int = 0
    por_ingrediente: dict = field(default_factory=lambda: defaultdict(float))
    por_proveedor: dict = field(default_factory=lambda: defaultdict(float))
    mermas: float = 0.0
    mermas_count: int = 0
    cambios_precio: list = field(default_factory=list)


def resumen_mensual(db: Session, *, meses: int = 6, hoy: date | None = None) -> dict:
    hoy = hoy or date.today()
    rangos = ultimos_n_meses(meses, hoy=hoy)
    desde, hasta = rangos[0].inicio, rangos[-1].fin

    ventas = _ventas(db, desde, hasta)
    compras = _compras(db, desde, hasta)
    mermas = (
        db.query(MermaRegistro)
        .filter(MermaRegistro.fecha >= desde, MermaRegistro.fecha <= hasta)
        .all()
    )
    cambios = (
        db.query(HistorialPrecio)
        .options(joinedload(HistorialPrecio.ingrediente_rel))
        .filter(HistorialPrecio.fecha_cambio >= desde, HistorialPrecio.fecha_cambio <= hasta)
        .order_by(HistorialPrecio.fecha_cambio)
        .all()
    )

    # tablas chicas de un obrador unico: se cargan enteras una vez
    catalogo = {p.id: p for p in db.query(ProductoCatalogo).all()}
    ingredientes = {i.id: i.nombre for i in db.query(Ingrediente).all()}
    clientes = {c.id: c.nombre for c in db.query(ClienteB2B).all()}
    proveedores = {p.id: p.nombre for p in db.query(Proveedor).all()}

    acum: dict[str, _Acum] = defaultdict(_Acum)
    cache_costo: dict[tuple[int, str], float | None] = {}

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

    for c in compras:
        a = acum[c.clave_mes]
        if c.monto is None:
            a.lineas_sin_precio += 1
        else:
            a.compras += c.monto
            a.por_ingrediente[c.ingrediente_id] += c.monto
            if c.proveedor_id:
                a.por_proveedor[c.proveedor_id] += c.monto

    for m in mermas:
        a = acum[_clave(m.fecha)]
        a.mermas += m.coste_total or 0
        a.mermas_count += 1

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
        a = acum.get(r.clave, _Acum())
        ventas_total = a.ventas_b2b + a.ventas_portal
        margen = ventas_total - a.cogs
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
            "compras_total_ars": round(a.compras, 2),
            "margen": {
                "cogs_ars": round(a.cogs, 2),
                "bruto_ars": round(margen, 2),
                "bruto_pct": round(100 * margen / ventas_total, 1) if ventas_total else None,
                # cuantas lineas del mes no pudieron costearse: sin esto el
                # margen se leeria como exacto cuando no lo es
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
            "top_ingredientes": [
                {
                    "ingrediente_id": iid,
                    "nombre": ingredientes.get(iid, f"#{iid}"),
                    "monto_ars": round(monto, 2),
                }
                for iid, monto in sorted(a.por_ingrediente.items(), key=lambda kv: -kv[1])[:TOP_N]
            ],
            "por_cliente": [
                {
                    "cliente_id": cid,
                    "nombre": clientes.get(cid, f"#{cid}"),
                    "monto_ars": round(monto, 2),
                    "pct": round(100 * monto / ventas_total, 1) if ventas_total else None,
                }
                for cid, monto in sorted(a.por_cliente.items(), key=lambda kv: -kv[1])
            ],
            "por_proveedor": [
                {
                    "proveedor_id": pid,
                    "nombre": proveedores.get(pid, f"#{pid}"),
                    "monto_ars": round(monto, 2),
                }
                for pid, monto in sorted(a.por_proveedor.items(), key=lambda kv: -kv[1])
            ],
            "cambios_precio": a.cambios_precio,
            "avisos": {
                "lineas_precio_cero": a.lineas_precio_cero,
                "lineas_compra_sin_precio": a.lineas_sin_precio,
            },
        })

    return {
        "periodo": {"desde": str(desde), "hasta": str(hasta), "meses": meses},
        "meses": meses_out,
        "advertencias": {
            # no es un bug ni un hueco de datos: simplemente no existe el modelo
            "sin_ventas_mostrador": True,
            "margen_reconstruido": True,
        },
    }
