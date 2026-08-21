"""Tests for correcting a past manual stock count (PUT /api/inventario/{id}
and PUT /api/congelados/{id}) and having the ledger adjust to match, per
services.stock.ajustar_correccion_conteo."""
from datetime import date

from app.auth import hash_pin
from app.main import app
from app.models import Categoria, Ingrediente, MovimientoStock, User
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


def _carga_inicial(db, tipo_stock, producto_id, cantidad, unidad, fecha) -> int:
    mov = MovimientoStock(
        tipo_stock=tipo_stock, referencia_producto_id=producto_id, cantidad=cantidad,
        unidad=unidad, tipo_movimiento="carga_inicial", referencia_origen="carga_inicial:historico",
        fecha=fecha,
    )
    db.add(mov)
    db.commit()
    return mov.id


def _movimiento_real(db, tipo_stock, producto_id, cantidad, unidad, tipo_movimiento, fecha, ref="registro_produccion:1"):
    db.add(MovimientoStock(
        tipo_stock=tipo_stock, referencia_producto_id=producto_id, cantidad=cantidad,
        unidad=unidad, tipo_movimiento=tipo_movimiento, referencia_origen=ref, fecha=fecha,
    ))
    db.commit()


# ── materia prima ──────────────────────────────────────────────────────────

def test_editar_conteo_corrige_carga_inicial_en_el_lugar(client, db):
    """Replica el caso real (Aceite Girasol): un conteo mal cargado (4kg) ya
    tiene un carga_inicial en el ledger y es el UNICO movimiento -- nunca fue
    un evento real, asi que corregirlo a 3kg edita ese mismo movimiento en
    vez de dejar un +4/-1 colgando para siempre."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]
    carga_id = _carga_inicial(db, "materia_prima", ing_id, 4.0, "kg", date(2026, 8, 13))

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json()["cantidad"] == 3.0

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 3.0
    assert carga.saldo_despues == 3.0
    assert carga.tipo_movimiento == "carga_inicial"  # edited in place, not superseded
    assert db.query(MovimientoStock).filter(MovimientoStock.tipo_movimiento == "correccion_conteo").count() == 0
    assert _ledger_sum(db, "materia_prima", ing_id) == 3.0


def test_editar_conteo_convierte_unidad(client, db):
    """Replica el caso real (Canela): carga_inicial quedo en 4kg por una
    confusion de unidad: el conteo correcto era 220g (=0.22kg). Sigue siendo
    el unico movimiento, asi que tambien se edita en el lugar."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]
    carga_id = _carga_inicial(db, "materia_prima", ing_id, 4.0, "kg", date(2026, 8, 13))

    res = client.put(
        f"/api/inventario/{reg['id']}",
        json={"cantidad": 220, "unidad": "g"},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert res.json()["cantidad"] == 0.22
    assert res.json()["unidad"] == "kg"  # normalized to unidad_uso, not stored as raw "220 g"

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 0.22
    assert _ledger_sum(db, "materia_prima", ing_id) == 0.22


def test_editar_conteo_con_movimiento_real_usa_correccion_aparte(client, db):
    """En cuanto hay un movimiento real (no solo el carga_inicial) en la
    fecha del conteo, corregir NO edita el carga_inicial -- inserta una
    correccion aparte, para no reescribir un evento real."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]
    carga_id = _carga_inicial(db, "materia_prima", ing_id, 4.0, "kg", date(2026, 8, 13))
    _movimiento_real(db, "materia_prima", ing_id, -0.5, "kg", "produccion_consumo", date(2026, 8, 13))

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    assert res.status_code == 200, res.text

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 4.0  # untouched

    correccion = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_movimiento == "correccion_conteo",
        MovimientoStock.referencia_producto_id == ing_id,
    ).first()
    assert correccion.cantidad == -0.5  # 3.0 - (4.0 - 0.5)
    assert _ledger_sum(db, "materia_prima", ing_id) == 3.0


def test_reeditar_con_movimiento_real_no_apila_la_correccion(client, db):
    """Con un movimiento real de por medio (camino de correccion aparte),
    reeditar el mismo registro no debe dejar dos correcciones vivas -- la
    primera se revierte antes de aplicar la segunda."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]
    carga_id = _carga_inicial(db, "materia_prima", ing_id, 4.0, "kg", date(2026, 8, 13))
    _movimiento_real(db, "materia_prima", ing_id, -0.5, "kg", "produccion_consumo", date(2026, 8, 13))

    client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 2.0}, headers=_auth(token))
    assert res.status_code == 200, res.text

    vivos = db.query(MovimientoStock).filter(
        MovimientoStock.referencia_origen == f"correccion_conteo:materia_prima:{reg['id']}",
    ).all()
    assert len(vivos) == 1
    assert _ledger_sum(db, "materia_prima", ing_id) == 2.0
    assert db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first().cantidad == 4.0


def test_reeditar_colapsa_correccion_vieja_de_vuelta_al_carga_inicial(client, db):
    """Un registro que ya tenia una correccion aparte de una edicion previa
    (por ejemplo de antes de este cambio de diseno) se debe reabsorber al
    reeditarlo, volviendo al camino de edicion directa -- no debe quedar
    apilada para siempre solo porque alguna vez existio."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]
    carga_id = _carga_inicial(db, "materia_prima", ing_id, 4.0, "kg", date(2026, 8, 13))
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id, cantidad=-1.0,
        unidad="kg", tipo_movimiento="correccion_conteo",
        referencia_origen=f"correccion_conteo:materia_prima:{reg['id']}", fecha=date(2026, 8, 13),
    ))
    db.commit()

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 0.22}, headers=_auth(token))
    assert res.status_code == 200, res.text

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 0.22
    vivos = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_movimiento == "correccion_conteo",
        MovimientoStock.referencia_producto_id == ing_id,
        MovimientoStock.referencia_origen == f"correccion_conteo:materia_prima:{reg['id']}",
    ).all()
    assert vivos == []  # the old one was reverted (retagged to :rev), nothing live remains
    assert _ledger_sum(db, "materia_prima", ing_id) == 0.22


def test_editar_conteo_sin_baseline_previo_actua_como_carga_inicial(client, db):
    """Un item que nunca tuvo carga_inicial ni movimientos: corregir su
    unico conteo manual debe fijar el ledger en el valor corregido, igual
    que si scripts/reconciliar_ledger_materia_prima.py lo hubiera hecho."""
    token = _admin_token(client, db)
    ing_id = _create_ingrediente(db, unidad_uso="kg")

    reg = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 4.0, "unidad": "kg", "fecha_registro": "2026-08-13"}],
        headers=_auth(token),
    ).json()[0]

    res = client.put(f"/api/inventario/{reg['id']}", json={"cantidad": 3.0}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert _ledger_sum(db, "materia_prima", ing_id) == 3.0


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
    """POST sigue sin escribir ledger -- solo PUT (correccion) lo hace."""
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


def test_editar_lote_congelado_corrige_carga_inicial_en_el_lugar(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50, "fecha_entrada": "2026-08-13"},
        headers=_auth(token),
    ).json()
    carga_id = _carga_inicial(db, "congelado", prod["id"], 50.0, "u", date(2026, 8, 13))

    res = client.put(f"/api/congelados/{entry['id']}", json={"cantidad": 30}, headers=_auth(token))
    assert res.status_code == 200, res.text

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 30.0
    assert db.query(MovimientoStock).filter(MovimientoStock.tipo_movimiento == "correccion_conteo").count() == 0
    assert _ledger_sum(db, "congelado", prod["id"]) == 30.0


def test_editar_lote_congelado_con_movimiento_real_usa_correccion_aparte(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50, "fecha_entrada": "2026-08-13"},
        headers=_auth(token),
    ).json()
    carga_id = _carga_inicial(db, "congelado", prod["id"], 50.0, "u", date(2026, 8, 13))
    _movimiento_real(db, "congelado", prod["id"], -5.0, "u", "entrega_b2b", date(2026, 8, 13))

    res = client.put(f"/api/congelados/{entry['id']}", json={"cantidad": 30}, headers=_auth(token))
    assert res.status_code == 200, res.text

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 50.0  # untouched -- a real entrega happened that day

    correccion = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_movimiento == "correccion_conteo",
        MovimientoStock.referencia_producto_id == prod["id"],
    ).first()
    assert correccion.cantidad == -15.0  # 30 - (50 - 5)
    assert _ledger_sum(db, "congelado", prod["id"]) == 30.0


def test_editar_lote_de_produccion_da_409(client, db):
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50},
        headers=_auth(token),
    ).json()

    from app.models import StockCongelado
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


def test_editar_lote_congelado_notas_no_ledger_no_afecta(client, db):
    """Cambiar solo `notas` (no cantidad/fecha) no debe tocar el ledger."""
    token = _admin_token(client, db)
    prod = _create_producto_congelado(client, token)

    entry = client.post(
        "/api/congelados",
        json={"producto_congelado_id": prod["id"], "cantidad": 50},
        headers=_auth(token),
    ).json()

    res = client.put(f"/api/congelados/{entry['id']}", json={"notas": "Recontado"}, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert _ledger_sum(db, "congelado", prod["id"]) == 0.0
