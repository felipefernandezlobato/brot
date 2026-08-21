"""Tests for the /api/congelados router (Module 6 — Frozen Stock)."""
from datetime import date, timedelta

from app.auth import hash_pin
from app.main import app
from app.models import MovimientoStock, StockCongelado, User
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

    entry = db.query(StockCongelado).filter(StockCongelado.id == body["id"]).one()
    assert entry.cantidad_original == 50


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

    updated = db.query(StockCongelado).filter(StockCongelado.id == entry["id"]).one()
    assert updated.cantidad_original == 25


def test_update_stock_congelado_sin_tocar_cantidad_no_toca_cantidad_original(client, db):
    """Editar solo notas/fecha no debe pisar cantidad_original con nada."""
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 10},
        headers=_auth(token),
    ).json()

    res = client.put(
        f"/api/congelados/{entry['id']}",
        json={"notas": "Solo una nota"},
        headers=_auth(token),
    )
    assert res.status_code == 200

    updated = db.query(StockCongelado).filter(StockCongelado.id == entry["id"]).one()
    assert updated.cantidad_original == 10


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


# ── Calculado (ledger) tests ───────────────────────────────────────────────────

def test_calculado_devuelve_saldo_acumulado_por_producto(client, db):
    token = _admin_token(client, db)
    prod = _create_producto(client, token)

    db.add(MovimientoStock(
        tipo_stock="congelado", referencia_producto_id=prod["id"], cantidad=1.5,
        unidad="u", tipo_movimiento="produccion_salida", fecha=date(2026, 8, 14),
    ))
    db.add(MovimientoStock(
        tipo_stock="congelado", referencia_producto_id=prod["id"], cantidad=-1.3333,
        unidad="u", tipo_movimiento="produccion_consumo", fecha=date(2026, 8, 15),
    ))
    db.commit()

    res = client.get("/api/congelados/calculado", headers=_auth(token))
    assert res.status_code == 200
    productos = {p["producto_congelado_id"]: p["historial"] for p in res.json()["productos"]}
    assert productos[prod["id"]] == [
        {"fecha": "2026-08-14", "cantidad": 1.5},
        {"fecha": "2026-08-15", "cantidad": 0.17},
    ]


def test_calculado_sin_movimientos_no_aparece(client, db):
    """A manually-counted-only product has no ledger entries -- absent from
    the response, not a zero/error. The frontend falls back to raw-only."""
    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50},
        headers=_auth(token),
    )

    res = client.get("/api/congelados/calculado", headers=_auth(token))
    assert res.status_code == 200
    ids = [p["producto_congelado_id"] for p in res.json()["productos"]]
    assert prod["id"] not in ids


def test_calculado_fecha_desde_conserva_saldo_de_apertura(client, db):
    """Trimming to fecha_desde keeps the last point before it as an opening
    balance, so a cell right at the start of the range still resolves."""
    token = _admin_token(client, db)
    prod = _create_producto(client, token)

    for fecha, cantidad in [(date(2026, 8, 1), 10.0), (date(2026, 8, 10), -3.0), (date(2026, 8, 20), 2.0)]:
        db.add(MovimientoStock(
            tipo_stock="congelado", referencia_producto_id=prod["id"], cantidad=cantidad,
            unidad="u", tipo_movimiento="produccion_salida", fecha=fecha,
        ))
    db.commit()

    res = client.get(
        "/api/congelados/calculado?fecha_desde=2026-08-15", headers=_auth(token)
    )
    assert res.status_code == 200
    historial = next(p["historial"] for p in res.json()["productos"] if p["producto_congelado_id"] == prod["id"])
    assert historial == [
        {"fecha": "2026-08-10", "cantidad": 7.0},   # opening balance carried in
        {"fecha": "2026-08-20", "cantidad": 9.0},
    ]


def test_sincronizar_ledger_usa_cantidad_original_no_la_consumida(client, db):
    """Regression: found in production against Barra Negra Cocinado's
    2026-08-13 lot. A real entrega had already consumed the lot to 0 by the
    time this endpoint was called, and it re-anchored the carga_inicial from
    12 down to 0 to match the (by-then-consumed) `cantidad` -- destroying the
    original count a real, later, legitimate sale should never have been
    able to touch. Must use `cantidad_original`, unaffected by that draw."""
    from app.services.stock import deducir_congelado_fifo

    token = _admin_token(client, db)
    prod = _create_producto(client, token)
    fecha = date(2026, 8, 13)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 12, "fecha_entrada": str(fecha)},
        headers=_auth(token),
    ).json()
    db.add(MovimientoStock(
        tipo_stock="congelado", referencia_producto_id=prod["id"], cantidad=12.0,
        unidad="u", tipo_movimiento="carga_inicial", referencia_origen="carga_inicial:historico",
        saldo_despues=12.0, fecha=fecha,
    ))
    db.commit()

    deducir_congelado_fifo(db, prod["id"], 12.0, "entrega_b2b:1:Cliente", fecha=date(2026, 8, 19))
    db.commit()

    res = client.post(f"/api/congelados/{entry['id']}/sincronizar-ledger", headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json()["ajustado"] is True

    carga = (
        db.query(MovimientoStock)
        .filter(MovimientoStock.tipo_stock == "congelado", MovimientoStock.tipo_movimiento == "carga_inicial")
        .one()
    )
    assert carga.cantidad == 12.0
