from datetime import date

from app.main import app
from app.routers.entregas_b2b import clientes_router, router as entregas_router

app.include_router(clientes_router)
app.include_router(entregas_router)

from app.auth import hash_pin
from app.models import ProductoCatalogo, User


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    producto = ProductoCatalogo(
        nombre="Baguette",
        precio=2.50,
        categoria="pan",
        posicion=0,
    )
    db.add(producto)
    db.commit()
    token = client.post(
        "/api/auth/login", json={"name": "Admin", "pin": "0000"}
    ).json()["token"]
    return token, producto.id


def test_create_cliente_b2b(client, db):
    token, _ = _setup(client, db)
    res = client.post(
        "/api/clientes-b2b",
        json={"nombre": "Restaurante La Mar", "telefono": "123456789"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["nombre"] == "Restaurante La Mar"
    assert data["telefono"] == "123456789"
    assert data["id"] is not None
    assert data["is_active"] is True


def test_create_entrega_b2b(client, db):
    token, producto_id = _setup(client, db)

    # Create a B2B client first
    cliente_res = client.post(
        "/api/clientes-b2b",
        json={"nombre": "Cafeteria Norte"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert cliente_res.status_code == 201
    cliente_id = cliente_res.json()["id"]

    # Create delivery with one line
    res = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cliente_id,
            "fecha_entrega": str(date.today()),
            "lineas": [
                {"producto_id": producto_id, "cantidad": 10, "precio_unitario": 2.50}
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["cliente_b2b_id"] == cliente_id
    assert data["estado"] == "pendiente"
    assert len(data["lineas"]) == 1
    assert data["lineas"][0]["cantidad"] == 10
    assert data["lineas"][0]["precio_unitario"] == 2.50


def test_volumen_entregas(client, db):
    token, producto_id = _setup(client, db)

    # Create a B2B client
    cliente_res = client.post(
        "/api/clientes-b2b",
        json={"nombre": "Hotel Central"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cliente_id = cliente_res.json()["id"]

    # Create two deliveries so aggregation has something to sum
    client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cliente_id,
            "fecha_entrega": str(date.today()),
            "lineas": [
                {"producto_id": producto_id, "cantidad": 5, "precio_unitario": 3.00}
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cliente_id,
            "fecha_entrega": str(date.today()),
            "lineas": [
                {"producto_id": producto_id, "cantidad": 3, "precio_unitario": 3.00}
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get(
        "/api/entregas-b2b/volumen",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1  # one product / one client combination
    row = data[0]
    assert row["cliente_nombre"] == "Hotel Central"
    assert row["producto_nombre"] == "Baguette"
    assert row["total_cantidad"] == 8      # 5 + 3
    assert row["total_valor"] == 24.0      # 8 * 3.00
