"""Tests for the proveedores (supplier) router."""
from app.auth import hash_pin
from app.main import app  # noqa: F401  — routers already mounted in main
from app.models import Categoria, Ingrediente, Pedido, User


def _setup(client, db):
    """Create an admin user, return auth token."""
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token


# ── CRUD tests ─────────────────────────────────────────────────────────────────

def test_create_proveedor(client, db):
    token = _setup(client, db)
    res = client.post(
        "/api/proveedores",
        json={"nombre": "Harinera Hnos. García", "lead_time_dias": 3, "telefono": "555-1234"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["nombre"] == "Harinera Hnos. García"
    assert body["lead_time_dias"] == 3
    assert body["telefono"] == "555-1234"
    assert "id" in body


def test_list_proveedores(client, db):
    token = _setup(client, db)
    client.post("/api/proveedores", json={"nombre": "Alfa"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/api/proveedores", json={"nombre": "Beta"}, headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/proveedores", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    nombres = [p["nombre"] for p in res.json()]
    assert "Alfa" in nombres
    assert "Beta" in nombres


def test_get_proveedor(client, db):
    token = _setup(client, db)
    created = client.post(
        "/api/proveedores", json={"nombre": "Solo Uno"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    res = client.get(f"/api/proveedores/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["nombre"] == "Solo Uno"


def test_update_proveedor(client, db):
    token = _setup(client, db)
    created = client.post(
        "/api/proveedores", json={"nombre": "Prov X"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    res = client.put(
        f"/api/proveedores/{pid}",
        json={"telefono": "999-8888", "lead_time_dias": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json()["telefono"] == "999-8888"
    assert res.json()["lead_time_dias"] == 5


def test_delete_proveedor(client, db):
    token = _setup(client, db)
    created = client.post(
        "/api/proveedores", json={"nombre": "Temporal"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    res = client.delete(f"/api/proveedores/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_delete_blocked_if_has_orders(client, db):
    token = _setup(client, db)
    created = client.post(
        "/api/proveedores", json={"nombre": "Prov Con Pedido"},
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = created.json()["id"]
    # Insert a pedido directly to trigger the constraint
    db.add(Pedido(proveedor_id=pid, estado="borrador"))
    db.commit()
    res = client.delete(f"/api/proveedores/{pid}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 409


# ── Price upsert tests ─────────────────────────────────────────────────────────

def _setup_ing_prov(client, db, token):
    """Helper: create an ingredient + supplier, return (ing_id, prov_id)."""
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.commit()
    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=25,
        precio_compra=500, unidad_uso="g",
    )
    db.add(ing)
    db.commit()
    prov = client.post(
        "/api/proveedores", json={"nombre": "Molinero"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return ing.id, prov.json()["id"]


def test_upsert_precio_create(client, db):
    token = _setup(client, db)
    ing_id, prov_id = _setup_ing_prov(client, db, token)
    res = client.post(
        "/api/proveedores/precios",
        json={
            "ingrediente_id": ing_id, "proveedor_id": prov_id,
            "precio": 10.0, "unidad": "kg", "cantidad": 1.0, "precio_por_unidad": 10.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["precio"] == 10.0
    assert res.json()["precio_por_unidad"] == 10.0


def test_upsert_precio_updates_existing(client, db):
    token = _setup(client, db)
    ing_id, prov_id = _setup_ing_prov(client, db, token)
    payload = {
        "ingrediente_id": ing_id, "proveedor_id": prov_id,
        "precio": 10.0, "unidad": "kg", "cantidad": 1.0, "precio_por_unidad": 10.0,
    }
    client.post("/api/proveedores/precios", json=payload, headers={"Authorization": f"Bearer {token}"})
    # Second upsert with a new price should update the existing record
    payload["precio"] = 12.5
    payload["precio_por_unidad"] = 12.5
    res2 = client.post("/api/proveedores/precios", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 201
    assert res2.json()["precio"] == 12.5


def test_comparar_precios(client, db):
    token = _setup(client, db)
    cat = Categoria(nombre="Lácteos", tipo="ingrediente")
    db.add(cat)
    db.commit()
    ing = Ingrediente(
        nombre="Mantequilla", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=5,
        precio_compra=800, unidad_uso="g",
    )
    db.add(ing)
    db.commit()
    prov1 = client.post("/api/proveedores", json={"nombre": "LactoProv"}, headers={"Authorization": f"Bearer {token}"})
    prov2 = client.post("/api/proveedores", json={"nombre": "FrescoProv"}, headers={"Authorization": f"Bearer {token}"})
    p1, p2 = prov1.json()["id"], prov2.json()["id"]

    client.post("/api/proveedores/precios", json={
        "ingrediente_id": ing.id, "proveedor_id": p1,
        "precio": 15.0, "unidad": "kg", "cantidad": 1.0, "precio_por_unidad": 15.0,
    }, headers={"Authorization": f"Bearer {token}"})
    client.post("/api/proveedores/precios", json={
        "ingrediente_id": ing.id, "proveedor_id": p2,
        "precio": 12.0, "unidad": "kg", "cantidad": 1.0, "precio_por_unidad": 12.0,
    }, headers={"Authorization": f"Bearer {token}"})

    res = client.get(f"/api/proveedores/comparar/{ing.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    # Must be ordered cheapest first
    assert data[0]["precio_por_unidad"] <= data[1]["precio_por_unidad"]
