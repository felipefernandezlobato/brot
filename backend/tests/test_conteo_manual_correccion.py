"""Tests for correcting a past manual stock count (PUT /api/inventario/{id}
and PUT /api/congelados/{id}). This is a plain record correction: it does
NOT touch MovimientoStock -- editing a count and adjusting the calculated
ledger are deliberately kept as two separate actions. See
services/stock.py's ajustar_correccion_conteo (tested directly in
test_ajustar_correccion_conteo.py) for the ledger-side primitive this
endpoint intentionally does not call."""
from datetime import date

from app.auth import hash_pin
from app.main import app
from app.models import Categoria, Ingrediente, MovimientoStock, StockCongelado, User
from app.routers.congelados import router as congelados_router
from app.routers.inventario import router as inventario_router

app.include_router(inventario_router)
app.include_router(congelados_router)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _admin_token(client, db) -> str:
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    return client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]


def _create_ingrediente(db, nombre="Aceite Girasol", unidad_uso="kg") -> int:
    cat = Categoria(nombre=f"Cat-{nombre}", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre=nombre, categoria_id=cat.id, unidad_compra="litro",
        cantidad_compra=5, precio_compra=1000, unidad_uso=unidad_uso,
    )
    db.add(ing)
    db.commit()
    return ing.id


def _ledger_sum(db, tipo_stock, producto_id) -> float:
    movs = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == tipo_stock,
        MovimientoStock.referencia_producto_id == producto_id,
    ).all()
    return round(sum(m.cantidad for m in movs), 6)


# ── materia prima ──────────────────────────────────────────────────────────

def test_editar_conteo_corrige_el_registro(client, db):
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json()["cantidad"] == 3.0


def test_editar_conteo_no_toca_el_ledger(client, db):
    """El caso que motivo el rediseno: corregir un registro no debe crear,
    editar ni tocar ningun MovimientoStock, aunque el ledger ya tenga
    actividad para ese ingrediente."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id, cantidad=4.0,
        unidad="kg", tipo_movimiento="carga_inicial", referencia_origen="carga_inicial:historico",
        fecha=date(2026, 8, 13),
    ))
    db.commit()
    ledger_antes = _ledger_sum(db, "materia_prima", ing_id)
    movimientos_antes = db.query(MovimientoStock).count()

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    assert res.status_code == 200, res.text

    assert _ledger_sum(db, "materia_prima", ing_id) == ledger_antes  # unchanged
    assert db.query(MovimientoStock).count() == movimientos_antes  # no new rows


def test_editar_conteo_convierte_unidad(client, db):
    """Replica el caso real (Canela): el registro guardado en kg debe poder
    corregirse entrando el valor en gramos, normalizando de vuelta a kg."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]

    res = client.put(
        f"/api/inventario/{reg['id']}",
        json={"cantidad": 220, "unidad": "g"},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["cantidad"] == 0.22
    assert res.json()["unidad"] == "kg"  # normalized to unidad_uso, not stored as raw "220 g"


def test_editar_registro_automatico_da_409(client, db):
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{
            "ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg",
            "notas": "Consumo automatico: registro_produccion:1",
        }],
        headers=_auth(token),
    ).json()[0]

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    assert res.status_code == 409


def test_editar_conteo_unidad_incompatible_da_422(client, db):
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg"}],
        headers=_auth(token),
    ).json()[0]

    res = client.put(f"/api/inventario/{reg['id']}", json={"unidad": "litro"}, headers=_auth(token))
    assert res.status_code == 422


def test_editar_conteo_no_permite_reasignar_ingrediente(client, db):
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, "Aceite Girasol", unidad_uso="kg")
    otro_id = _create_ingrediente(db, "Aceite Oliva", unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg"}],
        headers=_auth(token),
    ).json()[0]

    res = client.put(
        f"/api/inventario/{reg['id']}",
        json={"ingrediente_id": otro_id},
        headers=_auth(token),
    )
    assert res.status_code == 422


def test_crear_conteo_nuevo_no_toca_ledger(client, db):
    """POST tampoco escribe ledger -- crear y corregir un conteo son
    ambos, siempre, correcciones/registros puros."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg"}],
        headers=_auth(token),
    )
    assert _ledger_sum(db, "materia_prima", ing_id) == 0.0


# ── congelado ──────────────────────────────────────────────────────────────

def _create_producto_congelado(client, token, nombre="Croissant Congelado") -> dict:
    res = client.post(
        "/api/congelados/productos",
        json={"nombre": nombre, "categoria": "bolleria", "unidad": "u"},
        headers=_auth(token),
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_editar_lote_congelado_corrige_el_registro(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50, "fecha_entrada": "2026-08-13"},
        headers=_auth(token),
    ).json()

    res = client.put(f"/api/congelados/{entry['id']}", json={"cantidad": 30}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json()["cantidad"] == 30


def test_editar_lote_congelado_no_toca_el_ledger(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50, "fecha_entrada": "2026-08-13"},
        headers=_auth(token),
    ).json()
    db.add(MovimientoStock(
        tipo_stock="congelado", referencia_producto_id=prod["id"], cantidad=50.0,
        unidad="u", tipo_movimiento="carga_inicial", referencia_origen="carga_inicial:historico",
        fecha=date(2026, 8, 13),
    ))
    db.commit()
    ledger_antes = _ledger_sum(db, "congelado", prod["id"])

    res = client.put(f"/api/congelados/{entry['id']}", json={"cantidad": 30}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert _ledger_sum(db, "congelado", prod["id"]) == ledger_antes


def test_editar_lote_de_produccion_da_409(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50},
        headers=_auth(token),
    ).json()

    lote = db.query(StockCongelado).filter(StockCongelado.id == entry["id"]).first()
    lote.registro_produccion_id = 999
    db.commit()

    res = client.put(f"/api/congelados/{entry['id']}", json={"cantidad": 30}, headers=_auth(token))
    assert res.status_code == 409


def test_editar_lote_automatico_da_409(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50, "notas": "Produccion: registro_produccion:1"},
        headers=_auth(token),
    ).json()

    res = client.put(f"/api/congelados/{entry['id']}", json={"cantidad": 30}, headers=_auth(token))
    assert res.status_code == 409


def test_editar_lote_congelado_notas_no_afecta_guardas(client, db):
    """Cambiar solo `notas` (no cantidad/fecha) no dispara las guardas de
    lote-de-produccion / registro-automatico, aunque el lote las tenga."""
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50},
        headers=_auth(token),
    ).json()

    res = client.put(f"/api/congelados/{entry['id']}", json={"notas": "Recontado"}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json()["notas"] == "Recontado"
