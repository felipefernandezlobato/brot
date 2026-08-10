"""Tests for the pedidos (supplier orders) router."""
from app.auth import hash_pin
from app.main import app  # noqa: F401  — routers already mounted in main
from app.models import Categoria, Ingrediente, InventarioRegistro, Proveedor, User


def _setup(client, db):
    """Create admin user, one supplier, one ingredient. Return (token, prov_id, ing_id)."""
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    prov = Proveedor(nombre="Proveedor A", lead_time_dias=2)
    db.add(prov)
    db.commit()
    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=25,
        precio_compra=500, unidad_uso="g",
    )
    db.add(ing)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, prov.id, ing.id


# ── Basic CRUD ─────────────────────────────────────────────────────────────────

def test_create_pedido_with_lines(client, db):
    token, prov_id, ing_id = _setup(client, db)
    res = client.post(
        "/api/pedidos",
        json={
            "proveedor_id": prov_id,
            "lineas": [{"ingrediente_id": ing_id, "cantidad_pedida": 10.0, "unidad": "kg"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["estado"] == "borrador"
    assert body["proveedor_id"] == prov_id
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["cantidad_pedida"] == 10.0


def test_list_pedidos_returns_all(client, db):
    token, prov_id, ing_id = _setup(client, db)
    client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                headers={"Authorization": f"Bearer {token}"})
    client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/pedidos", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_list_pedidos_with_status_filter(client, db):
    token, prov_id, ing_id = _setup(client, db)
    client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                headers={"Authorization": f"Bearer {token}"})
    res_borrador = client.get("/api/pedidos?estado=borrador",
                              headers={"Authorization": f"Bearer {token}"})
    assert all(p["estado"] == "borrador" for p in res_borrador.json())

    res_enviado = client.get("/api/pedidos?estado=enviado",
                             headers={"Authorization": f"Bearer {token}"})
    assert len(res_enviado.json()) == 0


def test_get_pedido(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                          headers={"Authorization": f"Bearer {token}"})
    pid = created.json()["id"]
    res = client.get(f"/api/pedidos/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["id"] == pid


# ── Lifecycle ──────────────────────────────────────────────────────────────────

def test_lifecycle_borrador_enviado_recibido(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post(
        "/api/pedidos",
        json={
            "proveedor_id": prov_id,
            "lineas": [{"ingrediente_id": ing_id, "cantidad_pedida": 5.0, "unidad": "kg"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]

    # borrador → enviado
    enviado = client.post(f"/api/pedidos/{pid}/enviar",
                          headers={"Authorization": f"Bearer {token}"})
    assert enviado.status_code == 200
    assert enviado.json()["estado"] == "enviado"

    # enviado → recibido
    recibido = client.post(f"/api/pedidos/{pid}/recibir",
                           headers={"Authorization": f"Bearer {token}"})
    assert recibido.status_code == 200
    assert recibido.json()["estado"] == "recibido"
    assert recibido.json()["fecha_recepcion"] is not None


def test_enviar_requires_borrador(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                          headers={"Authorization": f"Bearer {token}"})
    pid = created.json()["id"]
    client.post(f"/api/pedidos/{pid}/enviar", headers={"Authorization": f"Bearer {token}"})
    # Trying to send again (now in 'enviado' state) must fail
    res = client.post(f"/api/pedidos/{pid}/enviar",
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 409


def test_recibir_requires_enviado(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                          headers={"Authorization": f"Bearer {token}"})
    pid = created.json()["id"]
    # Trying to receive a borrador directly must fail
    res = client.post(f"/api/pedidos/{pid}/recibir",
                      headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 409


# ── Delete guard ───────────────────────────────────────────────────────────────

def test_delete_borrador_succeeds(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                          headers={"Authorization": f"Bearer {token}"})
    pid = created.json()["id"]
    res = client.delete(f"/api/pedidos/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_delete_blocked_if_not_borrador(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                          headers={"Authorization": f"Bearer {token}"})
    pid = created.json()["id"]
    client.post(f"/api/pedidos/{pid}/enviar", headers={"Authorization": f"Bearer {token}"})
    res = client.delete(f"/api/pedidos/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 409


# ── Auto stock update on receive ───────────────────────────────────────────────

def test_recibir_creates_inventario_entries(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post(
        "/api/pedidos",
        json={
            "proveedor_id": prov_id,
            "lineas": [
                {"ingrediente_id": ing_id, "cantidad_pedida": 20.0, "unidad": "kg"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    client.post(f"/api/pedidos/{pid}/enviar", headers={"Authorization": f"Bearer {token}"})
    client.post(f"/api/pedidos/{pid}/recibir", headers={"Authorization": f"Bearer {token}"})

    registros = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .all()
    )
    assert len(registros) == 1
    assert registros[0].cantidad == 20.0
    assert registros[0].unidad == "kg"


def test_recibir_uses_cantidad_recibida_when_set(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post(
        "/api/pedidos",
        json={
            "proveedor_id": prov_id,
            "lineas": [
                {
                    "ingrediente_id": ing_id,
                    "cantidad_pedida": 20.0,
                    "unidad": "kg",
                    "cantidad_recibida": 18.5,
                },
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    client.post(f"/api/pedidos/{pid}/enviar", headers={"Authorization": f"Bearer {token}"})
    client.post(f"/api/pedidos/{pid}/recibir", headers={"Authorization": f"Bearer {token}"})

    registros = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .all()
    )
    assert registros[0].cantidad == 18.5


# ── Line-level endpoints ───────────────────────────────────────────────────────

def test_add_and_delete_linea(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post("/api/pedidos", json={"proveedor_id": prov_id, "lineas": []},
                          headers={"Authorization": f"Bearer {token}"})
    pid = created.json()["id"]

    # Add a line
    add_res = client.post(
        f"/api/pedidos/{pid}/lineas",
        json={"ingrediente_id": ing_id, "cantidad_pedida": 3.0, "unidad": "kg"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert add_res.status_code == 201
    linea_id = add_res.json()["id"]
    assert add_res.json()["cantidad_pedida"] == 3.0

    # Delete the line
    del_res = client.delete(f"/api/pedidos/{pid}/lineas/{linea_id}",
                            headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200

    # Pedido should now have no lines
    pedido = client.get(f"/api/pedidos/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert len(pedido.json()["lineas"]) == 0


def test_update_linea(client, db):
    token, prov_id, ing_id = _setup(client, db)
    created = client.post(
        "/api/pedidos",
        json={
            "proveedor_id": prov_id,
            "lineas": [{"ingrediente_id": ing_id, "cantidad_pedida": 5.0, "unidad": "kg"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    linea_id = created.json()["lineas"][0]["id"]

    res = client.put(
        f"/api/pedidos/{pid}/lineas/{linea_id}",
        json={"ingrediente_id": ing_id, "cantidad_pedida": 7.5, "unidad": "kg"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["cantidad_pedida"] == 7.5
