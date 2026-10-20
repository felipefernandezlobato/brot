"""La ficha de cuenta de un cliente: `GET /api/clientes-b2b/{id}/cuenta`.

Lo que importa de esta pantalla es que sus números coincidan con los que ya da
el resto del sistema. Una ficha que diga una facturación distinta a la del
resumen mensual es peor que no tener ficha: no hay forma de saber cuál miente.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.auth import hash_pin
from app.auth_cliente import hash_password
from app.main import app
from app.models import (
    ClienteB2B,
    EntregaB2B,
    LineaEntregaB2B,
    LineaPedidoCliente,
    PedidoCliente,
    ProductoCatalogo,
    User,
)
from app.services.mensual import ventas

HOY = date.today()


def _admin(client, db, role="admin"):
    user = User(name=f"U-{role}", pin_hash=hash_pin("1234"), role=role)
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": f"U-{role}", "pin": "1234"})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _producto(db, nombre, precio):
    p = ProductoCatalogo(nombre=nombre, precio=precio, categoria="Panes", disponible=True)
    db.add(p)
    db.flush()
    return p


def _cliente(db, nombre="Creme", **kw):
    c = ClienteB2B(nombre=nombre, is_active=True, **kw)
    db.add(c)
    db.flush()
    return c


def _entrega(db, cliente, fecha, lineas, estado="entregado"):
    e = EntregaB2B(cliente_b2b_id=cliente.id, fecha_entrega=fecha, estado=estado,
                   created_at=datetime.now(timezone.utc))
    db.add(e)
    db.flush()
    for prod, cant, precio in lineas:
        db.add(LineaEntregaB2B(entrega_id=e.id, producto_id=prod.id,
                               cantidad=cant, precio_unitario=precio))
    db.flush()
    return e


def _pedido_portal(db, cliente, fecha, lineas, estado="entregado"):
    total = sum(c * p for _, c, p in lineas)
    ped = PedidoCliente(cliente_id=cliente.id, fecha_entrega=fecha, estado=estado,
                        total=total, fecha_pedido=datetime.now(timezone.utc))
    db.add(ped)
    db.flush()
    for prod, cant, precio in lineas:
        db.add(LineaPedidoCliente(pedido_cliente_id=ped.id, producto_id=prod.id,
                                  cantidad=cant, precio_unitario_snapshot=precio,
                                  subtotal=cant * precio))
    db.flush()
    return ped


def _cuenta(client, token, cliente_id, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/api/clientes-b2b/{cliente_id}/cuenta" + (f"?{q}" if q else "")
    return client.get(url, headers={"Authorization": f"Bearer {token}"})


def test_mezcla_entregas_b2b_y_pedidos_del_portal(client, db):
    """Un cliente que compra por los dos canales tiene UNA cuenta, no dos."""
    token = _admin(client, db)
    c = _cliente(db)
    croissant = _producto(db, "Croissant", 1550)
    db.commit()

    _entrega(db, c, HOY, [(croissant, 10, 1550)])            # 15.500 b2b
    _pedido_portal(db, c, HOY, [(croissant, 4, 1550)])       # 6.200 portal
    db.commit()

    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["facturado_ars"] == pytest.approx(21700)
    assert cuenta["resumen"]["pedidos"] == 2
    assert {h["origen"] for h in cuenta["historial"]} == {"entrega", "portal"}


def test_dos_entregas_el_mismo_dia_cuentan_como_dos(client, db):
    """Creme tiene dos entregas reales el 2026-08-15.

    El primer intento contaba los pedidos agrupando las líneas de venta por
    `(canal, fecha)` — `LineaVenta` no arrastra el id del pedido — y ese día se
    fusionaba en uno: la ficha habría dicho 18 pedidos donde hay 19. Se cuenta
    sobre el historial, que sí trae `origen` + `id`.
    """
    token = _admin(client, db)
    c = _cliente(db)
    pan = _producto(db, "Pan", 1000)
    db.commit()

    _entrega(db, c, HOY, [(pan, 1, 1000)])
    _entrega(db, c, HOY, [(pan, 2, 1000)])
    db.commit()

    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["pedidos"] == 2
    assert cuenta["resumen"]["facturado_ars"] == pytest.approx(3000)
    assert len(cuenta["historial"]) == 2


def test_solo_lo_entregado_cuenta_como_facturado(client, db):
    """Pero lo pendiente SÍ aparece en el historial: si no, un pedido que entró
    ayer y no salió todavía no se vería en ningún sitio, que es justo cuando
    uno abre la ficha."""
    token = _admin(client, db)
    c = _cliente(db)
    pan = _producto(db, "Pan", 1000)
    db.commit()

    _entrega(db, c, HOY, [(pan, 5, 1000)], estado="entregado")
    _entrega(db, c, HOY + timedelta(days=2), [(pan, 99, 1000)], estado="pendiente")
    db.commit()

    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["facturado_ars"] == pytest.approx(5000)
    assert cuenta["resumen"]["pedidos"] == 1
    # Las dos en el historial, la pendiente incluida.
    assert len(cuenta["historial"]) == 2
    assert {h["estado"] for h in cuenta["historial"]} == {"entregado", "pendiente"}


def test_el_facturado_coincide_con_la_definicion_canonica_de_ventas(client, db):
    """La ficha no puede tener su propia fórmula del importe.

    Hay cinco multiplicaciones escritas a mano repartidas por los routers; esta
    prueba ancla la ficha a `mensual.ventas()`, que es la que alimenta el
    resumen mensual del inicio. Si alguien mete una sexta, esto falla.
    """
    token = _admin(client, db)
    c = _cliente(db)
    a = _producto(db, "Croissant", 1550)
    b = _producto(db, "Focaccia", 14160)
    db.commit()

    _entrega(db, c, HOY, [(a, 7, 1550), (b, 2, 14160)])
    _pedido_portal(db, c, HOY, [(a, 3, 1550)])
    db.commit()

    esperado = sum(l.monto for l in ventas(db, HOY, HOY) if l.cliente_id == c.id)
    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["facturado_ars"] == pytest.approx(round(esperado, 2))


def test_top_productos_ordena_por_plata_no_por_unidades(client, db):
    """400 medialunas baratas no son "más" que 30 focaccias caras."""
    token = _admin(client, db)
    c = _cliente(db)
    medialuna = _producto(db, "Medialuna", 1110)
    focaccia = _producto(db, "Focaccia", 14160)
    db.commit()

    _entrega(db, c, HOY, [(medialuna, 40, 1110), (focaccia, 30, 14160)])
    db.commit()

    top = _cuenta(client, token, c.id).json()["top_productos"]
    assert [t["producto"] for t in top] == ["Focaccia", "Medialuna"]
    # La cantidad sigue estando, que es el dato que sirve para producir.
    assert top[1]["cantidad"] == 40


def test_ticket_promedio_es_nulo_sin_nada_entregado(client, db):
    """Un cliente nuevo no tiene un ticket medio de cero: no tiene ticket."""
    token = _admin(client, db)
    c = _cliente(db, nombre="Recien dado de alta")
    db.commit()

    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["pedidos"] == 0
    assert cuenta["resumen"]["facturado_ars"] == 0
    assert cuenta["resumen"]["ticket_promedio_ars"] is None
    assert cuenta["resumen"]["ultima_entrega"] is None
    assert cuenta["historial"] == []
    assert cuenta["top_productos"] == []


def test_el_rango_de_fechas_recorta_los_totales(client, db):
    token = _admin(client, db)
    c = _cliente(db)
    pan = _producto(db, "Pan", 1000)
    db.commit()

    viejo = HOY - timedelta(days=120)
    _entrega(db, c, viejo, [(pan, 10, 1000)])
    _entrega(db, c, HOY, [(pan, 3, 1000)])
    db.commit()

    completo = _cuenta(client, token, c.id).json()
    assert completo["resumen"]["facturado_ars"] == pytest.approx(13000)

    reciente = _cuenta(client, token, c.id,
                       desde=(HOY - timedelta(days=7)).isoformat(),
                       hasta=HOY.isoformat()).json()
    assert reciente["resumen"]["facturado_ars"] == pytest.approx(3000)
    assert reciente["resumen"]["pedidos"] == 1
    # El historial no se recorta: sigue mostrando todo lo que existe.
    assert len(reciente["historial"]) == 2


def test_muestra_el_estado_del_portal(client, db):
    """Es la pantalla donde se decide invitar o aprobar, así que tiene que
    decir en qué punto está cada uno."""
    token = _admin(client, db)
    sin_acceso = _cliente(db, nombre="Sin portal")
    con_acceso = _cliente(
        db, nombre="Con portal", email="x@test.com",
        password_hash=hash_password("secret123"),
        email_verificado_at=datetime.now(timezone.utc),
        aprobado_at=datetime.now(timezone.utc),
    )
    db.commit()

    a = _cuenta(client, token, sin_acceso.id).json()["cliente"]
    assert a["tiene_acceso"] is False and a["puede_pedir"] is False

    b = _cuenta(client, token, con_acceso.id).json()["cliente"]
    assert b["tiene_acceso"] is True and b["puede_pedir"] is True


def test_solo_admin(client, db):
    """Expone facturación por cliente, igual que /dashboard/mensual."""
    c = _cliente(db)
    db.commit()
    assert _cuenta(client, _admin(client, db, "staff"), c.id).status_code == 403
    assert client.get(f"/api/clientes-b2b/{c.id}/cuenta").status_code == 401


def test_cliente_inexistente_da_404(client, db):
    token = _admin(client, db)
    assert _cuenta(client, token, 99999).status_code == 404


def test_una_entrega_con_fecha_futura_ya_entregada_cuenta(client, db):
    """Las entregas se cargan con la fecha de entrega PRÓXIMA, así que una
    marcada entregada por adelantado tiene `fecha_entrega` en el futuro.

    Con el tope por defecto en `hoy` quedaba fuera del facturado del cliente
    mientras sí aparecía en las estadísticas del mes: dos pantallas dando
    números distintos de la misma venta, sin explicación visible.
    """
    token = _admin(client, db)
    c = _cliente(db)
    pan = _producto(db, "Pan", 1000)
    db.commit()

    _entrega(db, c, HOY + timedelta(days=3), [(pan, 4, 1000)], estado="entregado")
    db.commit()

    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["facturado_ars"] == pytest.approx(4000)
    assert cuenta["resumen"]["pedidos"] == 1


def test_una_entrega_entregada_sin_lineas_no_diluye_el_ticket(client, db):
    """`create_entrega_b2b` no exige líneas y `update` acepta `lineas: []`, así
    que una entrega entregada y vacía es alcanzable.

    No genera ninguna línea de venta, así que aportaría 0 al facturado mientras
    sumaba 1 al divisor del ticket promedio. Se descarta del conteo, que es lo
    que mantiene de acuerdo a las dos fuentes del resumen.
    """
    token = _admin(client, db)
    c = _cliente(db)
    pan = _producto(db, "Pan", 1000)
    db.commit()

    _entrega(db, c, HOY, [(pan, 2, 1000)])
    _entrega(db, c, HOY, [])  # entregada y vacia
    db.commit()

    cuenta = _cuenta(client, token, c.id).json()
    assert cuenta["resumen"]["facturado_ars"] == pytest.approx(2000)
    assert cuenta["resumen"]["pedidos"] == 1
    assert cuenta["resumen"]["ticket_promedio_ars"] == pytest.approx(2000)
    # Pero existe, asi que se sigue viendo en el historial.
    assert len(cuenta["historial"]) == 2
