"""El recargo express, extremo a extremo por HTTP.

Las fechas son FIJAS y "hoy" se inyecta con el override de `_hoy`. Depender de
`date.today()` dejaria el camino express alcanzable solo los martes y los
viernes, que es cuando "manana" cae en dia de entrega -- un test que solo
corre 2 de cada 7 dias no es un test.
"""

from datetime import date

import pytest

from app.main import app
from app.models import PedidoCliente
from app.routers import pedidos_clientes
from app.services.pedido_express import RECARGO_EXPRESS_PCT
from tests.test_customer_portal import (
    _admin_token,
    _create_catalog_product,
    _register_and_login_cliente,
)

# 2026-01-07 es miercoles de verdad; 01-10 es sabado de verdad.
MIERCOLES = date(2026, 1, 7)
MARTES = date(2026, 1, 6)
LUNES = date(2026, 1, 5)
SABADO = date(2026, 1, 10)
VIERNES = date(2026, 1, 9)


@pytest.fixture
def fijar_hoy():
    """Fija el "hoy" del backend. El fixture `client` limpia los overrides al
    terminar, asi que no hace falta deshacerlo a mano."""

    def _set(d: date):
        app.dependency_overrides[pedidos_clientes._hoy] = lambda: d

    return _set


def _escenario(client, db, precio=1000.0):
    admin = _admin_token(client, db)
    producto = _create_catalog_product(client, admin, nombre="Pan Express", precio=precio)
    token = _register_and_login_cliente(client, db)
    return producto, token


def _pedir(client, token, producto_id, fecha, cantidad=1):
    return client.post(
        "/api/cliente/pedidos",
        json={
            "fecha_entrega": str(fecha),
            "lineas": [{"producto_id": producto_id, "cantidad": cantidad}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )


# ── el cobro ────────────────────────────────────────────────────────────────


def test_con_dos_dias_de_antelacion_no_hay_recargo(client, db, fijar_hoy):
    fijar_hoy(LUNES)
    producto, token = _escenario(client, db)

    res = _pedir(client, token, producto["id"], MIERCOLES)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["recargo_pct"] == 0.0
    assert body["recargo_monto"] == 0.0
    assert body["total"] == 1000.0


def test_con_un_dia_de_antelacion_se_cobra_el_recargo(client, db, fijar_hoy):
    fijar_hoy(MARTES)
    producto, token = _escenario(client, db)

    res = _pedir(client, token, producto["id"], MIERCOLES)

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["recargo_pct"] == RECARGO_EXPRESS_PCT
    assert body["recargo_monto"] == 50.0
    assert body["total"] == 1050.0


def test_el_recargo_tambien_corre_para_el_sabado(client, db, fijar_hoy):
    """El tramo express no es "solo para el miercoles": es un dia de antelacion
    sea cual sea el dia de entrega."""
    fijar_hoy(VIERNES)
    producto, token = _escenario(client, db)

    body = _pedir(client, token, producto["id"], SABADO).json()

    assert body["recargo_monto"] == 50.0
    assert body["total"] == 1050.0


def test_el_recargo_se_calcula_sobre_el_subtotal_completo(client, db, fijar_hoy):
    fijar_hoy(MARTES)
    producto, token = _escenario(client, db, precio=333.33)

    body = _pedir(client, token, producto["id"], MIERCOLES, cantidad=3).json()

    # 3 x 333.33 = 999.99 -> 5% = 50.0 (49.9995 redondeado)
    assert body["total"] == 1049.99
    assert body["recargo_monto"] == 50.0


def test_el_total_guardado_incluye_el_recargo(client, db, fijar_hoy):
    """`total` es lo que paga el cliente: lo leen /entregas, el mail y la ficha."""
    fijar_hoy(MARTES)
    producto, token = _escenario(client, db)

    pedido_id = _pedir(client, token, producto["id"], MIERCOLES).json()["id"]

    guardado = db.query(PedidoCliente).filter(PedidoCliente.id == pedido_id).first()
    assert guardado.total == 1050.0
    assert guardado.recargo_monto == 50.0
    assert guardado.recargo_pct == RECARGO_EXPRESS_PCT
    # La linea NO lleva el recargo adentro: el recargo es del pedido entero.
    assert sum(l.subtotal for l in guardado.lineas) == 1000.0


# ── lo que se rechaza ───────────────────────────────────────────────────────


def test_no_se_puede_pedir_para_el_mismo_dia(client, db, fijar_hoy):
    fijar_hoy(MIERCOLES)
    producto, token = _escenario(client, db)

    res = _pedir(client, token, producto["id"], MIERCOLES)

    assert res.status_code == 422
    assert "anticipación" in res.json()["detail"]


def test_no_se_puede_pedir_para_una_fecha_pasada(client, db, fijar_hoy):
    fijar_hoy(date(2026, 1, 9))
    producto, token = _escenario(client, db)

    assert _pedir(client, token, producto["id"], MIERCOLES).status_code == 422


def test_el_dia_invalido_se_sigue_rechazando_por_su_propio_motivo(client, db, fijar_hoy):
    """Un jueves con antelacion de sobra falla por el dia, no por la antelacion.
    Los dos mensajes tienen que seguir siendo distinguibles."""
    fijar_hoy(LUNES)
    producto, token = _escenario(client, db)

    res = _pedir(client, token, producto["id"], date(2026, 1, 8))  # jueves

    assert res.status_code == 422
    assert "miércoles o sábado" in res.json()["detail"]


def test_el_cliente_no_puede_esquivar_el_recargo(client, db, fijar_hoy):
    """El schema de entrada no acepta recargo_*: Pydantic los descarta y el
    backend los recalcula. Esta es la propiedad que hace que valga la pena
    validar en el servidor y no solo pintar el calendario."""
    fijar_hoy(MARTES)
    producto, token = _escenario(client, db)

    res = client.post(
        "/api/cliente/pedidos",
        json={
            "fecha_entrega": str(MIERCOLES),
            "lineas": [{"producto_id": producto["id"], "cantidad": 1}],
            "recargo_pct": 0,
            "recargo_monto": 0,
            "total": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    assert res.json()["total"] == 1050.0


# ── el config que consume el portal ─────────────────────────────────────────


def test_config_expone_el_porcentaje_y_el_hoy_del_servidor(client, db, fijar_hoy):
    fijar_hoy(MARTES)
    _, token = _escenario(client, db)

    res = client.get(
        "/api/cliente/pedidos/config", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200, res.text
    assert res.json() == {
        "recargo_express_pct": RECARGO_EXPRESS_PCT,
        "dias_anticipacion_normal": 2,
        "hoy": str(MARTES),
    }


def test_config_no_se_confunde_con_la_ruta_de_un_pedido(client, db):
    """`/config` esta registrada antes que `/{pedido_id}`. Si alguien las
    reordena, "config" intenta parsearse como int y esto da 422."""
    _, token = _escenario(client, db)

    res = client.get(
        "/api/cliente/pedidos/config", headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert "recargo_express_pct" in res.json()


def test_config_exige_estar_logueado(client, db):
    assert client.get("/api/cliente/pedidos/config").status_code in (401, 403)
