"""Tests for the /api/congelados router (Module 6 — Frozen Stock)."""
from datetime import date, timedelta

from app.auth import hash_pin
from app.main import app
from app.models import User
from app.routers.congelados import router

app.include_router(router)


# ── helpers ────────────────────────────────────────────────────────────────────

def _admin_token(client, db) -> str:
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    return res.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_producto(client, token, nombre="Croissant Congelado") -> dict:
    res = client.post(
        "/api/congelados/productos",
        json={"nombre": nombre, "categoria": "bolleria", "unidad": "ud"},
        headers=_auth(token),
    )
    assert res.status_code == 201, res.text
    return res.json()


# ── ProductoCongelado tests ────────────────────────────────────────────────────

def test_create_producto_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token, "Pain au Chocolat")
    assert prod["nombre"] == "Pain au Chocolat"
    assert prod["categoria"] == "bolleria"
    assert prod["unidad"] == "ud"
    assert prod["is_active"] is True


def test_list_productos_congelados(client, db):
    token = _admin_token(client, db)
    _create_producto(client, token, "A")
    _create_producto(client, token, "B")
    res = client.get("/api/congelados/productos", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_update_producto_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    res = client.put(
        f"/api/congelados/productos/{prod['id']}",
        json={"nombre": "Croissant Actualizado"},
        headers=_auth(token),
    )
    assert res.status_code == 200
    assert res.json()["nombre"] == "Croissant Actualizado"


def test_delete_producto_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    res = client.delete(f"/api/congelados/productos/{prod['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_delete_producto_con_stock_devuelve_409(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    # Add a stock entry
    client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 10},
        headers=_auth(token),
    )
    res = client.delete(f"/api/congelados/productos/{prod['id']}", headers=_auth(token))
    assert res.status_code == 409


# ── StockCongelado tests ───────────────────────────────────────────────────────

def test_add_stock_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)

    res = client.post(
        "/api/congelados",
        json={
            "producto_congelado_id": prod["id"],
            "cantidad": 50,
            "fecha_entrada": str(date.today()),
            "fecha_vencimiento": str(date.today() + timedelta(days=30)),
            "lote": "LOTE-001",
        },
        headers=_auth(token),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["cantidad"] == 50
    assert body["lote"] == "LOTE-001"
    assert body["producto_nombre"] == prod["nombre"]


def test_list_stock_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    for qty in [10, 20]:
        client.post(
            "/api/congelados",
            json={"producto_congelado_id": prod["id"], "cantidad": qty},
            headers=_auth(token),
        )
    res = client.get("/api/congelados", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_list_stock_filtro_producto(client, db):
    token = _admin_token(client, db)
    prod1 = _create_producto(client, token, "P1")
    prod2 = _create_producto(client, token, "P2")
    client.post("/api/congelados", json={"producto_congelado_id": prod1["id"], "cantidad": 5}, headers=_auth(token))
    client.post("/api/congelados", json={"producto_congelado_id": prod2["id"], "cantidad": 8}, headers=_auth(token))
    res = client.get(f"/api/congelados?producto_id={prod1['id']}", headers=_auth(token))
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["producto_congelado_id"] == prod1["id"]


def test_update_stock_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 10},
        headers=_auth(token),
    ).json()
    res = client.put(
        f"/api/congelados/{entry['id']}",
        json={"cantidad": 25, "notas": "Recontado"},
        headers=_auth(token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["cantidad"] == 25
    assert body["notas"] == "Recontado"


def test_delete_stock_congelado(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 10},
        headers=_auth(token),
    ).json()
    res = client.delete(f"/api/congelados/{entry['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["ok"] is True


# ── Alertas de vencimiento tests ───────────────────────────────────────────────

def test_alertas_vencimiento(client, db):
    """An entry with a past expiry date must appear in the alerts endpoint."""
    token = _admin_token(client, db)
    prod = _create_producto(client, token)

    yesterday = str(date.today() - timedelta(days=1))
    next_month = str(date.today() + timedelta(days=30))

    # Expired entry
    client.post(
        "/api/congelados",
        json={
            "producto_congelado_id": prod["id"],
            "cantidad": 20,
            "fecha_vencimiento": yesterday,
        },
        headers=_auth(token),
    )
    # Entry still valid (30 days out)
    client.post(
        "/api/congelados",
        json={
            "producto_congelado_id": prod["id"],
            "cantidad": 30,
            "fecha_vencimiento": next_month,
        },
        headers=_auth(token),
    )

    res = client.get("/api/congelados/alertas-vencimiento", headers=_auth(token))
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) == 1
    assert alerts[0]["fecha_vencimiento"] == yesterday


def test_alertas_vencimiento_dentro_de_7_dias(client, db):
    """An entry expiring in 3 days must also appear in alerts."""
    token = _admin_token(client, db)
    prod = _create_producto(client, token)

    in_3_days = str(date.today() + timedelta(days=3))

    client.post(
        "/api/congelados",
        json={
            "producto_congelado_id": prod["id"],
            "cantidad": 15,
            "fecha_vencimiento": in_3_days,
        },
        headers=_auth(token),
    )

    res = client.get("/api/congelados/alertas-vencimiento", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_alertas_vencimiento_sin_fecha_no_aparece(client, db):
    """An entry without expiry date must NOT appear in alerts."""
    token = _admin_token(client, db)
    prod = _create_producto(client, token)

    client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 10},
        headers=_auth(token),
    )

    res = client.get("/api/congelados/alertas-vencimiento", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 0
