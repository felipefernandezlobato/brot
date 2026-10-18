"""El aviso al panadero cuando entra un pedido por la web.

Lo que de verdad importa aca no es el texto del correo, es que el pedido se
guarde pase lo que pase con el correo. Un pedido perdido es plata perdida y
nadie se entera; un correo que no sale se nota enseguida.
"""

import pytest

from app.services import avisos_pedido
from tests.test_customer_portal import (
    NEXT_WEDNESDAY,
    _admin_token,
    _create_catalog_product,
    _register_and_login_cliente,
)


@pytest.fixture
def correos(monkeypatch):
    """Intercepta los envios y los devuelve como (destino, asunto, cuerpo)."""
    enviados = []
    monkeypatch.setattr(
        avisos_pedido,
        "enviar_email",
        lambda destino, asunto, cuerpo: enviados.append((destino, asunto, cuerpo)) or True,
    )
    return enviados


def _hacer_pedido(client, db, lineas=None, notas=None):
    admin_tok = _admin_token(client, db)
    croissant = _create_catalog_product(client, admin_tok, nombre="Croissant", precio=1550)
    medialuna = _create_catalog_product(client, admin_tok, nombre="Medialunas", precio=1110)
    tok = _register_and_login_cliente(client, db, email="panadero-test@test.com", nombre="Olula")
    cuerpo = {
        "fecha_entrega": NEXT_WEDNESDAY,
        "lineas": lineas or [
            {"producto_id": croissant["id"], "cantidad": 24},
            {"producto_id": medialuna["id"], "cantidad": 30},
        ],
    }
    if notas:
        cuerpo["notas"] = notas
    res = client.post("/api/cliente/pedidos", json=cuerpo,
                      headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 201, res.text
    return res.json()


def test_un_pedido_nuevo_le_avisa_al_panadero(client, db, correos, monkeypatch):
    monkeypatch.setenv("EMAIL_PANADERO", "panadero@example.com")
    pedido = _hacer_pedido(client, db)

    assert len(correos) == 1
    destino, asunto, cuerpo = correos[0]
    assert destino == "panadero@example.com"
    assert "Olula" in asunto
    # Las cantidades son lo que el panadero necesita, y van sin decimales.
    assert "24 u  Croissant" in cuerpo
    assert "30 u  Medialunas" in cuerpo
    assert f"#{pedido['id']}" in cuerpo
    # 24*1550 + 30*1110 = 70.500, escrito a la argentina
    assert "70.500,00" in cuerpo


def test_admite_varios_destinos_separados_por_coma(client, db, correos, monkeypatch):
    monkeypatch.setenv("EMAIL_PANADERO", "uno@example.com, dos@example.com")
    _hacer_pedido(client, db)

    # Un envio por destino, no un To: compartido: asi un rebote de uno no se
    # lleva el aviso del otro.
    assert [c[0] for c in correos] == ["uno@example.com", "dos@example.com"]


def test_sin_configurar_el_destino_no_manda_nada_pero_guarda_el_pedido(
    client, db, correos, monkeypatch
):
    monkeypatch.delenv("EMAIL_PANADERO", raising=False)
    pedido = _hacer_pedido(client, db)

    assert correos == []
    # Lo importante: el pedido existe igual, con su total y sus dos lineas.
    from app.models import PedidoCliente
    guardado = db.query(PedidoCliente).filter(PedidoCliente.id == pedido["id"]).first()
    assert guardado is not None
    assert guardado.total == 70500
    assert len(guardado.lineas) == 2


def test_si_el_correo_explota_el_pedido_queda_guardado(client, db, monkeypatch):
    """Un SMTP caido no puede costarnos un pedido.

    El aviso corre en segundo plano y despues del commit, asi que ni siquiera
    una excepcion deberia tocar al pedido. TestClient propaga lo que lance una
    BackgroundTask, asi que el fallo se ve aca y aun asi el pedido esta.
    """
    monkeypatch.setenv("EMAIL_PANADERO", "panadero@example.com")

    def explota(*a, **k):
        raise RuntimeError("SMTP caido")

    monkeypatch.setattr(avisos_pedido, "enviar_email", explota)

    admin_tok = _admin_token(client, db)
    prod = _create_catalog_product(client, admin_tok, nombre="Croissant", precio=1550)
    tok = _register_and_login_cliente(client, db, email="falla@test.com", nombre="Creme")

    try:
        client.post(
            "/api/cliente/pedidos",
            json={"fecha_entrega": NEXT_WEDNESDAY,
                  "lineas": [{"producto_id": prod["id"], "cantidad": 5}]},
            headers={"Authorization": f"Bearer {tok}"},
        )
    except RuntimeError:
        pass  # el envio fallo, que es justo lo que simulamos

    from app.models import PedidoCliente
    pedidos = db.query(PedidoCliente).all()
    assert len(pedidos) == 1
    assert pedidos[0].total == 7750


def test_la_nota_del_cliente_viaja_en_el_correo(client, db, correos, monkeypatch):
    monkeypatch.setenv("EMAIL_PANADERO", "panadero@example.com")
    _hacer_pedido(client, db, notas="Sin sal en el pan, por favor")

    assert "Sin sal en el pan, por favor" in correos[0][2]


def test_el_asunto_dice_cliente_y_dia_de_entrega(client, db, correos, monkeypatch):
    monkeypatch.setenv("EMAIL_PANADERO", "panadero@example.com")
    _hacer_pedido(client, db)

    asunto = correos[0][1]
    # Se lee de un pantallazo en el movil, sin abrirlo.
    assert asunto.startswith("Pedido de Olula para el miercoles ")


def test_formato_pesos_usa_punto_de_miles_y_coma_decimal():
    assert avisos_pedido.formato_pesos(1234.5) == "1.234,50"
    assert avisos_pedido.formato_pesos(70500) == "70.500,00"
    assert avisos_pedido.formato_pesos(0) == "0,00"


def test_formato_cantidad_no_pone_decimales_de_mas():
    assert avisos_pedido.formato_cantidad(24) == "24"
    assert avisos_pedido.formato_cantidad(24.0) == "24"
    assert avisos_pedido.formato_cantidad(1.5) == "1,50"
