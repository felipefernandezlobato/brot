"""Tests for the monthly statistics.

Aimed at what could be silently wrong with nobody noticing:
  - month boundaries (a sale on the last day counts, the next day's does not)
  - cost reconstructed at the sale's date, not with today's prices
  - data gaps counted rather than read as 0
"""
from datetime import date

from app.models import (
    Categoria,
    ClienteB2B,
    EntregaB2B,
    HistorialPrecio,
    Ingrediente,
    LineaEntregaB2B,
    LineaPedido,
    LineaReceta,
    Pedido,
    ProductoCatalogo,
    Proveedor,
    Receta,
)
from app.services.costes import precio_compra_en
from app.services.mensual import (
    TOP_N,
    monto_compras_recibidas,
    rango_mes,
    resumen_compras_mensual,
    resumen_mensual,
    ultimos_n_meses,
)

HOY = date(2026, 10, 13)


# ── month boundaries ──────────────────────────────────────────────────────────


def test_mes_en_curso_es_parcial_y_corta_hoy():
    r = rango_mes(2026, 10, hoy=HOY)
    assert r.es_parcial is True
    assert r.fin == HOY, "el mes en curso no puede incluir dias futuros"
    assert (r.dias_transcurridos, r.dias_totales) == (13, 31)


def test_mes_cerrado_llega_hasta_el_ultimo_dia():
    r = rango_mes(2026, 9, hoy=HOY)
    assert r.es_parcial is False
    assert r.fin == date(2026, 9, 30)
    assert r.dias_transcurridos == r.dias_totales == 30


def test_ultimos_n_meses_cruza_el_ano():
    meses = ultimos_n_meses(4, hoy=date(2026, 2, 10))
    assert [m.clave for m in meses] == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert [m.es_parcial for m in meses] == [False, False, False, True]


# ── minimal fixture ───────────────────────────────────────────────────────────


def _setup(db, *, precio_harina=1000.0):
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat.id, unidad_compra="kg",
        cantidad_compra=1, precio_compra=precio_harina, unidad_uso="kg",
        merma_porcentaje=0, activo=True,
    )
    db.add(ing)
    db.flush()

    receta = Receta(nombre="Pan", categoria_id=cat.id, porciones_por_lote=10, precio_venta=500)
    db.add(receta)
    db.flush()
    db.add(LineaReceta(receta_id=receta.id, ingrediente_id=ing.id, cantidad=1, unidad="kg"))

    producto = ProductoCatalogo(nombre="Pan", precio=500, categoria="Panes",
                                disponible=True, posicion=1, receta_id=receta.id)
    cliente = ClienteB2B(nombre="Olula", email="o@o.com", password_hash="x", is_active=True)
    db.add_all([producto, cliente])
    db.flush()
    return ing, receta, producto, cliente


def _vender(db, producto, cliente, fecha, cantidad=10, precio=500, costo_snapshot=None):
    e = EntregaB2B(cliente_b2b_id=cliente.id, fecha_entrega=fecha, estado="entregado")
    db.add(e)
    db.flush()
    db.add(LineaEntregaB2B(entrega_id=e.id, producto_id=producto.id, cantidad=cantidad,
                           precio_unitario=precio, costo_unitario_snapshot=costo_snapshot))
    db.flush()
    return e


def _mes(res, clave):
    return next(m for m in res["meses"] if m["mes"] == clave)


# ── the boundary that matters ─────────────────────────────────────────────────


def test_venta_del_ultimo_dia_del_mes_cuenta_en_ese_mes(db):
    _, _, producto, cliente = _setup(db)
    _vender(db, producto, cliente, date(2026, 9, 30))
    db.commit()

    res = resumen_mensual(db, meses=3, hoy=HOY)
    assert _mes(res, "2026-09")["ventas"]["total_ars"] == 5000.0
    assert _mes(res, "2026-10")["ventas"]["total_ars"] == 0.0


def test_venta_del_primero_no_se_filtra_al_mes_anterior(db):
    _, _, producto, cliente = _setup(db)
    _vender(db, producto, cliente, date(2026, 10, 1))
    db.commit()

    res = resumen_mensual(db, meses=3, hoy=HOY)
    assert _mes(res, "2026-09")["ventas"]["total_ars"] == 0.0
    assert _mes(res, "2026-10")["ventas"]["total_ars"] == 5000.0


def test_venta_futura_queda_afuera(db):
    _, _, producto, cliente = _setup(db)
    _vender(db, producto, cliente, date(2026, 10, 31))  # posterior a HOY
    db.commit()

    res = resumen_mensual(db, meses=2, hoy=HOY)
    assert _mes(res, "2026-10")["ventas"]["total_ars"] == 0.0


# ── historical cost, not today's ──────────────────────────────────────────────


def test_precio_compra_en_reconstruye_hacia_atras(db):
    ing, *_ = _setup(db, precio_harina=2400.0)
    db.add(HistorialPrecio(ingrediente_id=ing.id, precio_anterior=1250.0,
                           precio_nuevo=2400.0, fecha_cambio=date(2026, 9, 28)))
    db.commit()

    # before the change the old price applies
    assert precio_compra_en(db, ing, date(2026, 8, 15)) == 1250.0
    # on the day of the change the new one already applies
    assert precio_compra_en(db, ing, date(2026, 9, 28)) == 2400.0
    assert precio_compra_en(db, ing, date(2026, 10, 5)) == 2400.0
    # with no date, today's: no existing caller changes behaviour
    assert precio_compra_en(db, ing, None) == 2400.0


def test_margen_usa_el_precio_de_la_fecha_no_el_de_hoy(db):
    """Lo que motivo todo esto: la harina paso de 1250 a 2400 (+92%).

    Una venta de agosto tiene que costearse a 1250. Con el precio de hoy el
    costo se duplicaria y el margen de agosto quedaria inventado.
    """
    ing, _, producto, cliente = _setup(db, precio_harina=2400.0)
    db.add(HistorialPrecio(ingrediente_id=ing.id, precio_anterior=1250.0,
                           precio_nuevo=2400.0, fecha_cambio=date(2026, 9, 28)))
    _vender(db, producto, cliente, date(2026, 8, 20))   # 10 u a 500 = 5000
    _vender(db, producto, cliente, date(2026, 10, 2))   # 10 u a 500 = 5000
    db.commit()

    res = resumen_mensual(db, meses=3, hoy=HOY)
    # recipe: 1 kg of flour / 10 portions -> unit cost = price/10
    assert _mes(res, "2026-08")["margen"]["cogs_ars"] == 1250.0
    assert _mes(res, "2026-10")["margen"]["cogs_ars"] == 2400.0
    assert _mes(res, "2026-08")["margen"]["bruto_ars"] == 3750.0
    assert _mes(res, "2026-10")["margen"]["bruto_ars"] == 2600.0


def test_el_snapshot_le_gana_a_la_reconstruccion(db):
    """Si la venta ya tiene costo congelado, ese manda: es lo que de verdad
    costo, y no se recalcula aunque cambie la receta o los precios."""
    ing, _, producto, cliente = _setup(db, precio_harina=2400.0)
    _vender(db, producto, cliente, date(2026, 10, 2), costo_snapshot=99.0)
    db.commit()

    res = resumen_mensual(db, meses=1, hoy=HOY)
    assert _mes(res, "2026-10")["margen"]["cogs_ars"] == 990.0  # 99 * 10 u


def test_precio_reconstruido_coincide_con_lo_pagado(db):
    """Cruce contra la realidad: el precio reconstruido a una fecha tiene que
    coincidir con lo que se pago de verdad en una recepcion de ese dia.

    Son dos fuentes independientes (HistorialPrecio y LineaPedido) y en los
    datos de produccion concuerdan; si alguna vez dejan de hacerlo, la
    reconstruccion del margen historico dejo de ser confiable.
    """
    ing, *_ = _setup(db, precio_harina=2400.0)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    db.add(HistorialPrecio(ingrediente_id=ing.id, precio_anterior=1250.0,
                           precio_nuevo=2400.0, fecha_cambio=date(2026, 9, 28)))
    p = Pedido(fecha=date(2026, 9, 10), proveedor_id=prov.id, estado="recibido",
               fecha_recepcion=date(2026, 9, 10))
    db.add(p)
    db.flush()
    db.add(LineaPedido(pedido_id=p.id, ingrediente_id=ing.id, cantidad_pedida=100,
                       unidad="kg", cantidad_recibida=100, precio_unitario=1250.0))
    db.commit()

    pagado = (
        db.query(LineaPedido.precio_unitario)
        .join(Pedido, Pedido.id == LineaPedido.pedido_id)
        .filter(Pedido.fecha_recepcion == date(2026, 9, 10))
        .scalar()
    )
    assert precio_compra_en(db, ing, date(2026, 9, 10)) == pagado


# ── gaps are counted, not hidden ──────────────────────────────────────────────


def test_receta_sin_lineas_no_cuenta_como_costo_cero(db):
    """Baston Cinnamon Roll no tiene lineas. Si eso se tomara como costo 0,
    el producto mostraria 100% de margen y pareceria el mejor del negocio."""
    _, receta, producto, cliente = _setup(db)
    db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).delete()
    _vender(db, producto, cliente, date(2026, 10, 2))
    db.commit()

    res = resumen_mensual(db, meses=1, hoy=HOY)
    m = _mes(res, "2026-10")
    assert m["margen"]["cogs_ars"] == 0.0
    assert m["margen"]["lineas_sin_costo"] == 1, "el hueco tiene que quedar visible"
    # sin ninguna linea costeable no hay margen que informar: None, no 100%.
    # Dejar la venta en el numerador y el costo afuera INFLA el margen, que es
    # justo lo contrario de avisar que falta un dato.
    assert m["margen"]["bruto_pct"] is None
    assert m["margen"]["cobertura_pct"] == 0.0
    assert m["ventas"]["total_ars"] == 5000.0, "la venta se sigue informando igual"


def test_subreceta_vacia_anidada_no_pasa_como_costo_valido(db):
    """El caso real de Cinnamon Roll, que casi se escapa.

    Cinnamon Roll -> Cinnamon Roll Crudo -> Baston Cinnamon Roll (0 lineas).
    El baston vacio esta DOS niveles abajo, asi que el costo no sale 0: sale
    33.91 contra un precio de 1.000, o sea 96.6% de margen, cuando todo lo bien
    costeado da ~67%. Una guarda que solo mire "costo == 0" lo deja pasar y el
    producto aparece como el mas rentable del negocio.
    """
    ing, receta_top, producto, cliente = _setup(db)

    vacia = Receta(nombre="Baston Vacio", categoria_id=receta_top.categoria_id,
                   porciones_por_lote=1, precio_venta=0, es_subreceta=True)
    db.add(vacia)
    db.flush()
    intermedia = Receta(nombre="Crudo", categoria_id=receta_top.categoria_id,
                        porciones_por_lote=40, precio_venta=0, es_subreceta=True)
    db.add(intermedia)
    db.flush()
    # the middle recipe DOES have lines: a real ingredient + the empty sub-recipe
    db.add_all([
        LineaReceta(receta_id=intermedia.id, subreceta_id=vacia.id, cantidad=1, unidad="u"),
        LineaReceta(receta_id=intermedia.id, ingrediente_id=ing.id, cantidad=0.04, unidad="kg"),
    ])
    db.query(LineaReceta).filter(LineaReceta.receta_id == receta_top.id).delete()
    db.add(LineaReceta(receta_id=receta_top.id, subreceta_id=intermedia.id, cantidad=1, unidad="u"))
    _vender(db, producto, cliente, date(2026, 10, 2))
    db.commit()

    from app.services.costes import receta_incompleta
    assert receta_incompleta(receta_top, db) is True

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["margen"]["cogs_ars"] == 0.0
    assert m["margen"]["lineas_sin_costo"] == 1, \
        "un costo no-cero pero incompleto tiene que contarse como hueco"
    assert m["margen"]["bruto_pct"] is None


def test_margen_se_calcula_solo_sobre_lo_costeable(db):
    """Con una venta costeable y otra que no, el % tiene que medirse sobre la
    primera nada mas, e informar que cubre la mitad.

    Si la venta sin costo quedara en el numerador con costo 0, el margen subiria
    en vez de avisar que hay un dato faltante.
    """
    ing, receta, producto, cliente = _setup(db)
    sin_receta = ProductoCatalogo(nombre="Sin receta", precio=500, categoria="Panes",
                                  disponible=True, posicion=2, receta_id=None)
    db.add(sin_receta)
    db.flush()
    _vender(db, producto, cliente, date(2026, 10, 2))      # 5000, costeable
    _vender(db, sin_receta, cliente, date(2026, 10, 3))    # 5000, no costeable
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["ventas"]["total_ars"] == 10000.0
    assert m["margen"]["ventas_costeadas_ars"] == 5000.0
    assert m["margen"]["cobertura_pct"] == 50.0
    # 1 kg de harina a 1000 / 10 porciones = 100/u, 10u -> 1000 de costo
    assert m["margen"]["cogs_ars"] == 1000.0
    assert m["margen"]["bruto_pct"] == 80.0  # (5000-1000)/5000, NO sobre 10000


def test_receta_completa_no_se_marca_incompleta(db):
    """Contracara del anterior: la guarda no puede ensuciar las recetas buenas."""
    from app.services.costes import receta_incompleta

    _, receta, _, _ = _setup(db)
    assert receta_incompleta(receta, db) is False


def test_compra_sin_cantidad_recibida_no_usa_la_pedida(db):
    """/flujo sumaba esto con SQL crudo: cantidad_recibida NULL hacia NULL el
    producto y SUM descartaba la fila, o sea aportaba 0. Si ahora cayera en
    cantidad_pedida, un `comprado_total_ars` historico cambiaria de valor solo
    por el refactor."""
    ing, *_ = _setup(db)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    p = Pedido(fecha=date(2026, 10, 2), proveedor_id=prov.id, estado="recibido",
               fecha_recepcion=date(2026, 10, 2))
    db.add(p)
    db.flush()
    db.add(LineaPedido(pedido_id=p.id, ingrediente_id=ing.id, cantidad_pedida=10,
                       unidad="kg", cantidad_recibida=None, precio_unitario=100.0))
    db.commit()

    assert monto_compras_recibidas(db, date(2026, 10, 1), date(2026, 10, 31)) == 0.0
    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["compras_total_ars"] == 0.0
    assert m["avisos"]["lineas_compra_sin_precio"] == 1


def test_cambio_de_precio_a_mitad_de_mes_se_aplica_por_fecha(db):
    """La cache no puede ser por mes: el orden de iteracion es de insercion, no
    cronologico (las entregas se cargan tarde), asi que la primera linea que
    toque un producto definiria el costo de todo el mes."""
    ing, _, producto, cliente = _setup(db, precio_harina=2000.0)
    db.add(HistorialPrecio(ingrediente_id=ing.id, precio_anterior=1000.0,
                           precio_nuevo=2000.0, fecha_cambio=date(2026, 10, 10)))
    # inserted out of order on purpose: the later sale first
    _vender(db, producto, cliente, date(2026, 10, 12))  # costo 200
    _vender(db, producto, cliente, date(2026, 10, 3))   # costo 100
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    # 10u * 200 + 10u * 100 = 3000, not 2*(10*200) nor 2*(10*100)
    assert m["margen"]["cogs_ars"] == 3000.0


def test_linea_vendida_a_precio_cero_se_cuenta(db):
    _, _, producto, cliente = _setup(db)
    _vender(db, producto, cliente, date(2026, 10, 2), precio=0)
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["ventas"]["total_ars"] == 0.0
    assert m["avisos"]["lineas_precio_cero"] == 1


def test_compra_sin_precio_no_se_suma_como_cero(db):
    ing, *_ = _setup(db)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    p = Pedido(fecha=date(2026, 10, 2), proveedor_id=prov.id, estado="recibido",
               fecha_recepcion=date(2026, 10, 2))
    db.add(p)
    db.flush()
    db.add_all([
        LineaPedido(pedido_id=p.id, ingrediente_id=ing.id, cantidad_pedida=10,
                    unidad="kg", cantidad_recibida=10, precio_unitario=100.0),
        LineaPedido(pedido_id=p.id, ingrediente_id=ing.id, cantidad_pedida=5,
                    unidad="kg", cantidad_recibida=5, precio_unitario=None),
    ])
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["compras_total_ars"] == 1000.0
    assert m["avisos"]["lineas_compra_sin_precio"] == 1


def test_pedido_no_recibido_no_es_gasto(db):
    ing, *_ = _setup(db)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    p = Pedido(fecha=date(2026, 10, 2), proveedor_id=prov.id, estado="enviado")
    db.add(p)
    db.flush()
    db.add(LineaPedido(pedido_id=p.id, ingrediente_id=ing.id, cantidad_pedida=10,
                       unidad="kg", precio_unitario=100.0))
    db.commit()

    assert monto_compras_recibidas(db, date(2026, 10, 1), date(2026, 10, 31)) == 0.0


def test_entrega_pendiente_no_es_venta(db):
    _, _, producto, cliente = _setup(db)
    e = EntregaB2B(cliente_b2b_id=cliente.id, fecha_entrega=date(2026, 10, 2),
                   estado="pendiente")
    db.add(e)
    db.flush()
    db.add(LineaEntregaB2B(entrega_id=e.id, producto_id=producto.id,
                           cantidad=10, precio_unitario=500))
    db.commit()

    assert _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")["ventas"]["total_ars"] == 0.0


# ── one definition of "what we spent" ────────────────────────────────────────


def test_flujo_y_mensual_dan_el_mismo_gasto(db):
    """/flujo y la pantalla mensual comparten monto_compras_recibidas, asi que
    no pueden discrepar. Si alguien vuelve a escribir la consulta aparte, esto
    lo agarra."""
    ing, *_ = _setup(db)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    p = Pedido(fecha=date(2026, 10, 2), proveedor_id=prov.id, estado="recibido",
               fecha_recepcion=date(2026, 10, 2))
    db.add(p)
    db.flush()
    db.add(LineaPedido(pedido_id=p.id, ingrediente_id=ing.id, cantidad_pedida=10,
                       unidad="kg", cantidad_recibida=8, precio_unitario=100.0))
    db.commit()

    # cantidad_recibida (8), not cantidad_pedida (10)
    esperado = 800.0
    assert monto_compras_recibidas(db, date(2026, 10, 1), date(2026, 10, 31)) == esperado
    assert _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")["compras_total_ars"] == esperado


# ── groupings ─────────────────────────────────────────────────────────────────


def _ingrediente(db, nombre, categoria_id, precio=1000.0):
    ing = Ingrediente(
        nombre=nombre, categoria_id=categoria_id, unidad_compra="kg",
        cantidad_compra=1, precio_compra=precio, unidad_uso="kg",
        merma_porcentaje=0, activo=True,
    )
    db.add(ing)
    db.flush()
    return ing


def _comprar(db, prov, ing, fecha, *, cantidad=10, precio=100.0, pedido=None):
    """Una linea de compra recibida. Pasa `pedido` para sumarle otra linea."""
    if pedido is None:
        pedido = Pedido(fecha=fecha, proveedor_id=prov.id, estado="recibido",
                        fecha_recepcion=fecha)
        db.add(pedido)
        db.flush()
    db.add(LineaPedido(pedido_id=pedido.id, ingrediente_id=ing.id,
                       cantidad_pedida=cantidad, unidad="kg",
                       cantidad_recibida=cantidad, precio_unitario=precio))
    db.flush()
    return pedido


def test_desglose_de_compras_por_proveedor_y_por_ingrediente(db):
    """Pinea la FORMA de los dos desgloses de compras, no solo el total.

    Hasta ahora solo estaba cubierto compras_total_ars, asi que un cambio en el
    agrupamiento (o moverlo de lugar) pasaba sin que nada se quejara.
    """
    harina, *_ = _setup(db)
    azucar = _ingrediente(db, "Azucar", harina.categoria_id)
    forzani = Proveedor(nombre="Forzani")
    diarco = Proveedor(nombre="Diarco")
    db.add_all([forzani, diarco])
    db.flush()
    _comprar(db, forzani, harina, date(2026, 10, 2), cantidad=10, precio=100.0)  # 1000
    _comprar(db, diarco, azucar, date(2026, 10, 5), cantidad=2, precio=250.0)    # 500
    _comprar(db, diarco, harina, date(2026, 10, 6), cantidad=1, precio=100.0)    # 100
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["compras_total_ars"] == 1600.0
    # ambos ordenados por monto descendente
    assert [(p["nombre"], p["monto_ars"]) for p in m["por_proveedor"]] == [
        ("Forzani", 1000.0), ("Diarco", 600.0),
    ]
    assert [(i["nombre"], i["monto_ars"]) for i in m["top_ingredientes"]] == [
        ("Harina 000", 1100.0), ("Azucar", 500.0),
    ]


def test_top_ingredientes_se_corta_en_top_n_y_proveedores_no(db):
    """Asimetria deliberada: top_ingredientes esta capado en TOP_N y
    por_proveedor NO (son pocos y se quieren todos). Es lo mas facil de
    uniformar sin querer al mover este codigo."""
    harina, *_ = _setup(db)
    for n in range(12):
        prov = Proveedor(nombre=f"Prov {n:02d}")
        db.add(prov)
        db.flush()
        ing = _ingrediente(db, f"Ing {n:02d}", harina.categoria_id)
        _comprar(db, prov, ing, date(2026, 10, 2), cantidad=1, precio=100.0 * (n + 1))
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert len(m["top_ingredientes"]) == TOP_N
    assert len(m["por_proveedor"]) == 12


def test_cambios_precio_se_agrupan_por_mes_del_cambio(db):
    ing, *_ = _setup(db)
    db.add_all([
        HistorialPrecio(ingrediente_id=ing.id, precio_anterior=1250.0,
                        precio_nuevo=2400.0, fecha_cambio=date(2026, 10, 4)),
        HistorialPrecio(ingrediente_id=ing.id, precio_anterior=0,
                        precio_nuevo=500.0, fecha_cambio=date(2026, 10, 5)),
        HistorialPrecio(ingrediente_id=ing.id, precio_anterior=100.0,
                        precio_nuevo=200.0, fecha_cambio=date(2026, 9, 30)),
    ])
    db.commit()

    res = resumen_mensual(db, meses=2, hoy=HOY)
    octubre = _mes(res, "2026-10")
    assert [(c["fecha_cambio"], c["variacion_pct"]) for c in octubre["cambios_precio"]] == [
        ("2026-10-04", 92.0),
        ("2026-10-05", None),  # sin precio anterior no hay variacion que calcular
    ]
    assert octubre["cambios_precio"][0]["nombre"] == "Harina 000"
    assert len(_mes(res, "2026-09")["cambios_precio"]) == 1


def test_concentracion_por_cliente(db):
    _, _, producto, cliente = _setup(db)
    otro = ClienteB2B(nombre="Creme", email="c@c.com", password_hash="x", is_active=True)
    db.add(otro)
    db.flush()
    _vender(db, producto, cliente, date(2026, 10, 2), cantidad=8)   # 4000
    _vender(db, producto, otro, date(2026, 10, 3), cantidad=2)      # 1000
    db.commit()

    porc = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")["por_cliente"]
    assert [(c["nombre"], c["pct"]) for c in porc] == [("Olula", 80.0), ("Creme", 20.0)]


# ── the endpoint is admin-only ────────────────────────────────────────────────


def _login(client, db, role):
    from app.auth import hash_pin
    from app.models import User

    db.add(User(name=f"User-{role}", pin_hash=hash_pin("1234"), role=role))
    db.commit()
    res = client.post("/api/auth/login", json={"name": f"User-{role}", "pin": "1234"})
    return res.json()["token"]


def test_compras_mensual_coincide_con_mensual(db):
    """resumen_mensual() compone su mitad de compras desde
    resumen_compras_mensual(), asi que la pantalla de Compras y la de inicio no
    pueden discrepar. Si alguien vuelve a duplicar el agrupamiento, esto lo
    agarra."""
    harina, *_ = _setup(db)
    azucar = _ingrediente(db, "Azucar", harina.categoria_id)
    forzani = Proveedor(nombre="Forzani")
    diarco = Proveedor(nombre="Diarco")
    db.add_all([forzani, diarco])
    db.flush()
    _comprar(db, forzani, harina, date(2026, 10, 2), cantidad=10, precio=100.0)
    _comprar(db, diarco, azucar, date(2026, 10, 5), cantidad=2, precio=250.0)
    # una linea sin precio, para que el aviso tambien tenga que coincidir
    p = Pedido(fecha=date(2026, 10, 7), proveedor_id=forzani.id, estado="recibido",
               fecha_recepcion=date(2026, 10, 7))
    db.add(p)
    db.flush()
    db.add(LineaPedido(pedido_id=p.id, ingrediente_id=harina.id, cantidad_pedida=3,
                       unidad="kg", cantidad_recibida=3, precio_unitario=None))
    db.add(HistorialPrecio(ingrediente_id=harina.id, precio_anterior=1250.0,
                           precio_nuevo=2400.0, fecha_cambio=date(2026, 10, 4)))
    db.commit()

    completo = _mes(resumen_mensual(db, meses=3, hoy=HOY), "2026-10")
    solo_compras = _mes(resumen_compras_mensual(db, meses=3, hoy=HOY), "2026-10")

    assert solo_compras["compras_total_ars"] == completo["compras_total_ars"]
    assert solo_compras["top_ingredientes"] == completo["top_ingredientes"]
    assert solo_compras["por_proveedor"] == completo["por_proveedor"]
    assert solo_compras["cambios_precio"] == completo["cambios_precio"]
    assert solo_compras["lineas_sin_precio"] == completo["avisos"]["lineas_compra_sin_precio"]


def test_pedidos_recibidos_cuenta_pedidos_y_no_lineas(db):
    harina, *_ = _setup(db)
    azucar = _ingrediente(db, "Azucar", harina.categoria_id)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    # un pedido con DOS lineas, mas otro pedido aparte
    p = _comprar(db, prov, harina, date(2026, 10, 2))
    _comprar(db, prov, azucar, date(2026, 10, 2), pedido=p)
    _comprar(db, prov, harina, date(2026, 10, 9))
    db.commit()

    m = _mes(resumen_compras_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["pedidos_recibidos"] == 2


def test_pedido_con_una_linea_sin_precio_igual_se_cuenta(db):
    """El pedido llego; que no sepamos lo que costo una linea no lo borra."""
    harina, *_ = _setup(db)
    prov = Proveedor(nombre="Forzani")
    db.add(prov)
    db.flush()
    p = Pedido(fecha=date(2026, 10, 2), proveedor_id=prov.id, estado="recibido",
               fecha_recepcion=date(2026, 10, 2))
    db.add(p)
    db.flush()
    db.add(LineaPedido(pedido_id=p.id, ingrediente_id=harina.id, cantidad_pedida=5,
                       unidad="kg", cantidad_recibida=5, precio_unitario=None))
    db.commit()

    m = _mes(resumen_compras_mensual(db, meses=1, hoy=HOY), "2026-10")
    assert m["pedidos_recibidos"] == 1
    assert m["compras_total_ars"] == 0.0
    assert m["lineas_sin_precio"] == 1


def test_compras_mensual_no_expone_ventas_ni_margen(db):
    """La razon por la que esta separado de /mensual. Si alguien le agrega
    ventas o margen, deja de poder ser visible para el staff."""
    _setup(db)
    db.commit()

    m = _mes(resumen_compras_mensual(db, meses=1, hoy=HOY), "2026-10")
    for prohibido in ("ventas", "margen", "por_cliente", "top_productos", "mermas"):
        assert prohibido not in m, f"{prohibido} no puede viajar en este payload"


def test_mensual_solo_admin(client, db):
    """Felipe pidio que las metricas de plata las vea solo el manager (admin).
    El staff ve el panel operativo pero no facturacion ni margenes."""
    token = _login(client, db, "staff")
    res = client.get("/api/dashboard/mensual",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_mensual_admin_entra(client, db):
    token = _login(client, db, "admin")
    res = client.get("/api/dashboard/mensual?meses=2",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["meses"]) == 2
    assert body["meses"][-1]["es_parcial"] is True, "el ultimo mes es el en curso"
    assert body["advertencias"]["sin_ventas_mostrador"] is True


def test_compras_mensual_lo_ve_el_staff(client, db):
    """Al contrario de /mensual: el que carga los pedidos necesita ver el gasto.
    Es un get_current_user pelado, no require_permission, asi que tampoco se
    puede apagar sin querer desde la pantalla de permisos."""
    token = _login(client, db, "staff")
    res = client.get("/api/dashboard/compras-mensual?meses=2",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["meses"]) == 2
    assert body["meses"][-1]["es_parcial"] is True
    assert "ventas" not in body["meses"][-1]


def test_compras_mensual_pide_login(client, db):
    assert client.get("/api/dashboard/compras-mensual").status_code == 401


def test_mermas_como_porcentaje_de_ventas(db):
    from app.models import MermaRegistro

    ing, _, producto, cliente = _setup(db)
    _vender(db, producto, cliente, date(2026, 10, 2))  # 5000
    db.add(MermaRegistro(ingrediente_id=ing.id, cantidad=1, unidad="kg", motivo="dañado",
                         fecha=date(2026, 10, 3), coste_unitario=250.0, coste_total=250.0))
    db.commit()

    m = _mes(resumen_mensual(db, meses=1, hoy=HOY), "2026-10")["mermas"]
    assert m["total_ars"] == 250.0
    assert m["pct_sobre_ventas"] == 5.0
