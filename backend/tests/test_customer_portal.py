"""
Customer portal tests: catalog, customer orders, recurring orders, admin management.
"""
from datetime import date, timedelta

from app.auth import hash_pin
from app.main import app
from app.models import User
from app.routers import catalogo, catalogo_admin, pedidos_clientes, pedidos_clientes_admin, recurrentes

# Ensure routers are mounted (already in main.py; explicit for clarity)
app.include_router(catalogo.router)
app.include_router(catalogo_admin.router)
app.include_router(pedidos_clientes.router)
app.include_router(pedidos_clientes_admin.router)
app.include_router(recurrentes.router)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _next_weekday(weekday: int) -> str:
    """Return YYYY-MM-DD of the next occurrence of `weekday` (Mon=0 … Sun=6)."""
    today = date.today()
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).isoformat()


NEXT_WEDNESDAY = _next_weekday(2)
NEXT_SATURDAY = _next_weekday(5)
INVALID_DELIVERY_DAY = _next_weekday(0)  # Monday — not a valid delivery day


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _ensure_admin(db):
    """Create admin user in test DB if it doesn't exist."""
    existing = db.query(User).filter(User.name == "Admin").first()
    if not existing:
        admin = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
        db.add(admin)
        db.commit()


def _admin_token(client, db):
    _ensure_admin(db)
    res = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _register_and_login_cliente(client, email="cliente@test.com", password="secret123", nombre="Test Cliente"):
    client.post("/api/auth/cliente/registro", json={
        "email": email,
        "password": password,
        "nombre": nombre,
    })
    res = client.post("/api/auth/cliente/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _create_catalog_product(client, admin_token, nombre="Pan de Centeno", precio=4.5):
    res = client.post(
        "/api/admin/catalogo",
        json={"nombre": nombre, "precio": precio, "categoria": "Panes", "disponible": True, "posicion": 0},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_catalogo_public(client, db):
    """Public catalog endpoint requires no authentication."""
    admin_tok = _admin_token(client, db)
    _create_catalog_product(client, admin_tok, nombre="Baguette", precio=2.5)

    # List without any auth header
    res = client.get("/api/catalogo")
    assert res.status_code == 200
    nombres = [p["nombre"] for p in res.json()]
    assert "Baguette" in nombres


def test_catalogo_public_hides_unavailable(client, db):
    """Products with disponible=False do not appear in the public catalog."""
    admin_tok = _admin_token(client, db)
    client.post(
        "/api/admin/catalogo",
        json={"nombre": "Hidden Product", "precio": 1.0, "categoria": "Panes", "disponible": False, "posicion": 99},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    res = client.get("/api/catalogo")
    assert res.status_code == 200
    nombres = [p["nombre"] for p in res.json()]
    assert "Hidden Product" not in nombres


def test_place_order(client, db):
    """Customer can place an order with a valid Wednesday delivery date."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok, nombre="Croissant", precio=3.0)

    cliente_tok = _register_and_login_cliente(client)

    res = client.post(
        "/api/cliente/pedidos",
        json={
            "fecha_entrega": NEXT_WEDNESDAY,
            "lineas": [{"producto_id": product["id"], "cantidad": 2}],
        },
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["estado"] == "pendiente"
    assert body["total"] == 6.0  # 2 × 3.0
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["precio_unitario_snapshot"] == 3.0


def test_place_order_saturday(client, db):
    """Customer can place an order with a Saturday delivery date."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok, nombre="Pain au Chocolat", precio=2.0)

    cliente_tok = _register_and_login_cliente(client, email="sat@test.com")

    res = client.post(
        "/api/cliente/pedidos",
        json={
            "fecha_entrega": NEXT_SATURDAY,
            "lineas": [{"producto_id": product["id"], "cantidad": 1}],
        },
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["fecha_entrega"] == NEXT_SATURDAY


def test_order_invalid_delivery_day(client, db):
    """Orders with a non-Wednesday/Saturday delivery date are rejected (422)."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok)

    cliente_tok = _register_and_login_cliente(client, email="invalid@test.com")

    res = client.post(
        "/api/cliente/pedidos",
        json={
            "fecha_entrega": INVALID_DELIVERY_DAY,
            "lineas": [{"producto_id": product["id"], "cantidad": 1}],
        },
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert res.status_code == 422


def test_order_requires_auth(client):
    """Placing an order without a token returns 401/403."""
    res = client.post(
        "/api/cliente/pedidos",
        json={"fecha_entrega": NEXT_WEDNESDAY, "lineas": []},
    )
    assert res.status_code in (401, 403)


def test_customer_sees_only_own_orders(client, db):
    """A customer cannot see orders from another customer."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok)

    tok_a = _register_and_login_cliente(client, email="a@test.com")
    tok_b = _register_and_login_cliente(client, email="b@test.com")

    # Customer A places an order
    client.post(
        "/api/cliente/pedidos",
        json={"fecha_entrega": NEXT_WEDNESDAY, "lineas": [{"producto_id": product["id"], "cantidad": 1}]},
        headers={"Authorization": f"Bearer {tok_a}"},
    )

    # Customer B's list should be empty
    res = client.get("/api/cliente/pedidos", headers={"Authorization": f"Bearer {tok_b}"})
    assert res.status_code == 200
    assert res.json() == []


def test_order_lifecycle(client, db):
    """Admin can advance an order through the full status lifecycle."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok)
    cliente_tok = _register_and_login_cliente(client, email="lifecycle@test.com")

    # Place order
    order_res = client.post(
        "/api/cliente/pedidos",
        json={
            "fecha_entrega": NEXT_WEDNESDAY,
            "lineas": [{"producto_id": product["id"], "cantidad": 3}],
        },
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert order_res.status_code == 201, order_res.text
    order_id = order_res.json()["id"]

    transitions = ["confirmado", "en_preparacion", "listo", "entregado"]
    for estado in transitions:
        res = client.put(
            f"/api/admin/pedidos-clientes/{order_id}/estado",
            json={"estado": estado},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert res.status_code == 200, f"Failed on transition to '{estado}': {res.text}"
        assert res.json()["estado"] == estado

    # Verify final state visible in admin list
    list_res = client.get(
        "/api/admin/pedidos-clientes",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert list_res.status_code == 200
    ids = [o["id"] for o in list_res.json()]
    assert order_id in ids


def test_admin_list_filter_by_estado(client, db):
    """Admin can filter orders by estado."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok)
    cliente_tok = _register_and_login_cliente(client, email="filter@test.com")

    order_res = client.post(
        "/api/cliente/pedidos",
        json={"fecha_entrega": NEXT_WEDNESDAY, "lineas": [{"producto_id": product["id"], "cantidad": 1}]},
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    order_id = order_res.json()["id"]

    # Confirm the order
    client.put(
        f"/api/admin/pedidos-clientes/{order_id}/estado",
        json={"estado": "confirmado"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )

    # Filter by confirmado
    res = client.get(
        "/api/admin/pedidos-clientes?estado=confirmado",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res.status_code == 200
    assert all(o["estado"] == "confirmado" for o in res.json())


def test_recurring_order_create(client, db):
    """Customer can create a recurring order template."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok, nombre="Sourdough", precio=5.0)

    cliente_tok = _register_and_login_cliente(client, email="recurring@test.com")

    res = client.post(
        "/api/cliente/recurrentes",
        json={
            "dia_entrega": "miercoles",
            "lineas": [{"producto_id": product["id"], "cantidad_default": 2}],
        },
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["dia_entrega"] == "miercoles"
    assert body["activo"] is True
    assert len(body["lineas"]) == 1
    assert body["lineas"][0]["cantidad_default"] == 2


def test_recurring_order_list_and_deactivate(client, db):
    """Customer can list and deactivate a recurring order."""
    admin_tok = _admin_token(client, db)
    product = _create_catalog_product(client, admin_tok, nombre="Brioche", precio=6.0)

    cliente_tok = _register_and_login_cliente(client, email="deact@test.com")

    create_res = client.post(
        "/api/cliente/recurrentes",
        json={"dia_entrega": "sabado", "lineas": [{"producto_id": product["id"], "cantidad_default": 1}]},
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert create_res.status_code == 201, create_res.text
    rec_id = create_res.json()["id"]

    # List
    list_res = client.get("/api/cliente/recurrentes", headers={"Authorization": f"Bearer {cliente_tok}"})
    assert list_res.status_code == 200
    assert any(r["id"] == rec_id for r in list_res.json())

    # Deactivate
    del_res = client.delete(
        f"/api/cliente/recurrentes/{rec_id}",
        headers={"Authorization": f"Bearer {cliente_tok}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["activo"] is False
