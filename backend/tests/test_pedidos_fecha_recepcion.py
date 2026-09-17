"""Reception date on a pedido: the date the goods actually arrived must land
on the pedido AND on every stock row / ledger movement it writes — never
`date.today()` when a real date was given (a delivery is often entered days
late). See `POST /api/pedidos/{id}/recibir`."""
from datetime import date, timedelta

from app.auth import hash_pin
from app.main import app  # noqa: F401  — routers already mounted in main
from app.models import Categoria, Ingrediente, InventarioRegistro, MovimientoStock, Proveedor, User


def _setup(client, db):
    """Create admin user, one supplier, one ingredient. Return (token, prov_id, ing_id)."""
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    prov = Proveedor(nombre="Tregar", lead_time_dias=2)
    db.add(prov)
    db.commit()
    ing = Ingrediente(
        nombre="Leche", categoria_id=cat.id,
        unidad_compra="litro", cantidad_compra=1,
        precio_compra=1740, unidad_uso="litro",
    )
    db.add(ing)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, prov.id, ing.id


def _crear_y_enviar(client, token, prov_id, ing_id, cantidad=1.0, unidad="litro"):
    """Create a pedido with one line and move it to 'enviado'. Returns (pid, linea_id)."""
    created = client.post(
        "/api/pedidos",
        json={
            "proveedor_id": prov_id,
            "lineas": [{"ingrediente_id": ing_id, "cantidad_pedida": cantidad, "unidad": unidad}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    linea_id = created.json()["lineas"][0]["id"]
    enviado = client.post(f"/api/pedidos/{pid}/enviar", headers={"Authorization": f"Bearer {token}"})
    assert enviado.status_code == 200
    return pid, linea_id


def test_recibir_con_fecha_pasada_marca_el_pedido_con_esa_fecha(client, db):
    token, prov_id, ing_id = _setup(client, db)
    pid, linea_id = _crear_y_enviar(client, token, prov_id, ing_id)
    llegada = date.today() - timedelta(days=2)

    res = client.post(
        f"/api/pedidos/{pid}/recibir",
        json={
            "lineas": [{"linea_id": linea_id, "cantidad_recibida": 1.0}],
            "fecha": llegada.isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["estado"] == "recibido"
    assert res.json()["fecha_recepcion"] == llegada.isoformat()


def test_recibir_con_fecha_pasada_fecha_el_inventario_con_esa_fecha(client, db):
    token, prov_id, ing_id = _setup(client, db)
    pid, linea_id = _crear_y_enviar(client, token, prov_id, ing_id)
    llegada = date.today() - timedelta(days=2)

    client.post(
        f"/api/pedidos/{pid}/recibir",
        json={
            "lineas": [{"linea_id": linea_id, "cantidad_recibida": 1.0}],
            "fecha": llegada.isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    registros = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .all()
    )
    assert len(registros) == 1
    assert registros[0].fecha_registro == llegada
    assert registros[0].cantidad == 1.0


def test_recibir_con_fecha_pasada_fecha_el_movimiento_con_esa_fecha(client, db):
    token, prov_id, ing_id = _setup(client, db)
    pid, linea_id = _crear_y_enviar(client, token, prov_id, ing_id)
    llegada = date.today() - timedelta(days=2)

    client.post(
        f"/api/pedidos/{pid}/recibir",
        json={
            "lineas": [{"linea_id": linea_id, "cantidad_recibida": 1.0}],
            "fecha": llegada.isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    movimientos = (
        db.query(MovimientoStock)
        .filter(MovimientoStock.referencia_origen == f"pedido:{pid}")
        .all()
    )
    assert len(movimientos) == 1
    assert movimientos[0].tipo_movimiento == "recepcion"
    assert movimientos[0].fecha == llegada
    assert movimientos[0].cantidad == 1.0


def test_recibir_sin_fecha_usa_hoy(client, db):
    """Omitting `fecha` keeps the old behaviour: pedido, inventario and ledger
    all dated today."""
    token, prov_id, ing_id = _setup(client, db)
    pid, linea_id = _crear_y_enviar(client, token, prov_id, ing_id)

    res = client.post(
        f"/api/pedidos/{pid}/recibir",
        json={"lineas": [{"linea_id": linea_id, "cantidad_recibida": 1.0}]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert res.json()["fecha_recepcion"] == date.today().isoformat()

    registro = db.query(InventarioRegistro).filter(
        InventarioRegistro.ingrediente_id == ing_id
    ).one()
    assert registro.fecha_registro == date.today()

    movimiento = db.query(MovimientoStock).filter(
        MovimientoStock.referencia_origen == f"pedido:{pid}"
    ).one()
    assert movimiento.fecha == date.today()
