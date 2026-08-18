"""Production module tests, against the current TareaProduccion/RegistroProduccion
API — the old ProductoProduccion/PlanProduccion/LogProduccion CRUD these tests used
to exercise was removed from the router a while back (the models are still in
models.py but have zero routes), and nobody updated the tests to match. The current
system is: a weekly recurring schedule (TareaProduccion), daily completion records
(RegistroProduccion) that move stock, and a direct /producir endpoint for
unplanned/extra production tied straight to a ProductoCongelado.
"""

from datetime import date

from app.auth import hash_pin
from app.models import (
    Categoria,
    Ingrediente,
    InventarioRegistro,
    LineaReceta,
    ProductoCongelado,
    Receta,
    TareaProduccion,
    User,
)

HOY = date.today()
DOW_HOY = min(HOY.isoweekday(), 6)


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, user.id


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _crear_tarea(client, token, **overrides):
    body = {"dia_semana": 1, "titulo": "Limpieza general", "tipo": "limpieza"}
    body.update(overrides)
    res = client.post("/api/produccion/tareas", json=body, headers=_headers(token))
    assert res.status_code == 201, res.text
    return res.json()


def _producto_con_receta(db, stock_ingrediente=50.0):
    """A terminado product with a one-ingredient recipe, so producing it deducts stock."""
    cat_r = Categoria(nombre="Panes", tipo="receta")
    cat_i = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add_all([cat_r, cat_i])
    db.flush()
    receta = Receta(nombre="Pan de Prueba", categoria_id=cat_r.id, porciones_por_lote=1)
    db.add(receta)
    db.flush()
    ing = Ingrediente(
        nombre="Harina Test", categoria_id=cat_i.id, unidad_compra="kg", unidad_uso="kg",
        precio_compra=100.0, cantidad_compra=1.0,
    )
    db.add(ing)
    db.flush()
    db.add(LineaReceta(receta_id=receta.id, ingrediente_id=ing.id, cantidad=1.0, unidad="kg"))
    db.add(InventarioRegistro(ingrediente_id=ing.id, cantidad=stock_ingrediente, unidad="kg", fecha_registro=HOY))
    prod = ProductoCongelado(nombre="Pan de Prueba", categoria="panes", unidad="u", receta_id=receta.id, nivel="terminado")
    db.add(prod)
    db.commit()
    return prod, receta, ing


def _saldo(db, ing_id):
    return (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
        .cantidad
    )


# ==============================================================
# Tareas — CRUD
# ==============================================================


def test_tareas_crud(client, db):
    token, _ = _setup(client, db)
    tarea = _crear_tarea(client, token, titulo="Apertura obrador", dia_semana=1, hora="07:00")
    tarea_id = tarea["id"]
    assert tarea["titulo"] == "Apertura obrador"
    assert tarea["is_active"] is True

    res = client.get("/api/produccion/tareas", headers=_headers(token))
    assert res.status_code == 200
    assert any(t["id"] == tarea_id for t in res.json())

    res2 = client.get(f"/api/produccion/tareas/{tarea_id}", headers=_headers(token))
    assert res2.status_code == 200
    assert res2.json()["titulo"] == "Apertura obrador"

    res3 = client.put(
        f"/api/produccion/tareas/{tarea_id}",
        json={"titulo": "Apertura y ventilacion"},
        headers=_headers(token),
    )
    assert res3.status_code == 200
    assert res3.json()["titulo"] == "Apertura y ventilacion"

    res4 = client.delete(f"/api/produccion/tareas/{tarea_id}", headers=_headers(token))
    assert res4.status_code == 200
    assert res4.json()["ok"] is True

    res5 = client.get(f"/api/produccion/tareas/{tarea_id}", headers=_headers(token))
    assert res5.status_code == 404


def test_calendario_groups_tareas_by_dia(client, db):
    token, _ = _setup(client, db)
    _crear_tarea(client, token, titulo="Lunes task", dia_semana=1)
    _crear_tarea(client, token, titulo="Viernes task", dia_semana=5)

    res = client.get("/api/produccion/calendario", headers=_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["1"]["nombre"] == "Lunes"
    assert any(t["titulo"] == "Lunes task" for t in data["1"]["tareas"])
    assert any(t["titulo"] == "Viernes task" for t in data["5"]["tareas"])
    assert data["2"]["tareas"] == []


# ==============================================================
# Day view + registro
# ==============================================================


def test_dia_view_shows_todays_tareas(client, db):
    token, _ = _setup(client, db)
    tarea = _crear_tarea(client, token, titulo="Tarea de hoy", dia_semana=DOW_HOY)

    res = client.get(f"/api/produccion/dia?fecha={HOY.isoformat()}", headers=_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["dia_semana"] == DOW_HOY
    entry = next((t for t in data["tareas"] if t["tarea_id"] == tarea["id"]), None)
    assert entry is not None
    assert entry["completada"] is False


def test_dia_view_rejects_bad_date(client, db):
    token, _ = _setup(client, db)
    res = client.get("/api/produccion/dia?fecha=not-a-date", headers=_headers(token))
    assert res.status_code == 400


def test_registro_toggle_completada_without_producto(client, db):
    """A task with no product tied (cleaning, notes) never needs a cantidad."""
    token, _ = _setup(client, db)
    tarea = _crear_tarea(client, token, titulo="Limpiar obrador", dia_semana=DOW_HOY, tipo="limpieza")

    res = client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY.isoformat(), "completada": True},
        headers=_headers(token),
    )
    assert res.status_code == 201
    assert res.json()["completada"] is True
    assert res.json()["movimientos"] == 0

    dia = client.get(f"/api/produccion/dia?fecha={HOY.isoformat()}", headers=_headers(token)).json()
    entry = next(t for t in dia["tareas"] if t["tarea_id"] == tarea["id"])
    assert entry["completada"] is True

    # Un-completing (undo) upserts the same record back to false.
    res2 = client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY.isoformat(), "completada": False},
        headers=_headers(token),
    )
    assert res2.status_code == 201
    assert res2.json()["completada"] is False


def test_registro_requires_cantidad_when_tarea_has_producto(client, db):
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)
    tarea = _crear_tarea(client, token, titulo="Hornear Pan de Prueba", dia_semana=DOW_HOY, receta_id=receta.id)
    # producto_congelado_id isn't settable via TareaProduccionCreate (real schedules
    # seed it directly), so wire it up the same way here.
    t_row = db.query(TareaProduccion).filter(TareaProduccion.id == tarea["id"]).first()
    t_row.producto_congelado_id = prod.id
    db.commit()

    res = client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY.isoformat(), "completada": True},
        headers=_headers(token),
    )
    assert res.status_code == 422

    res2 = client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY.isoformat(), "completada": True, "cantidad_real": 10.0},
        headers=_headers(token),
    )
    assert res2.status_code == 201
    data = res2.json()
    assert data["cantidad_real"] == 10.0
    assert data["stock_aplicado"] is True
    assert data["movimientos"] >= 1
    assert _saldo(db, ing.id) == 40.0  # 50 - 10 * 1kg


# ==============================================================
# Extra (unplanned) production
# ==============================================================


def test_registro_extra_requires_cantidad(client, db):
    token, _ = _setup(client, db)
    cat = Categoria(nombre="Panes", tipo="receta")
    db.add(cat)
    db.flush()
    receta = Receta(nombre="Receta X", categoria_id=cat.id, porciones_por_lote=1)
    db.add(receta)
    db.commit()

    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "receta_id": receta.id},
        headers=_headers(token),
    )
    assert res.status_code == 422


def test_registro_extra_appears_in_dia_view(client, db):
    token, _ = _setup(client, db)
    cat = Categoria(nombre="Panes", tipo="receta")
    db.add(cat)
    db.flush()
    receta = Receta(nombre="Receta Suelta", categoria_id=cat.id, porciones_por_lote=1)
    db.add(receta)
    db.commit()

    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "receta_id": receta.id, "cantidad_real": 5.0},
        headers=_headers(token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["titulo_extra"] == "Receta Suelta"
    assert data["tarea_id"] is None

    dia = client.get(f"/api/produccion/dia?fecha={HOY.isoformat()}", headers=_headers(token)).json()
    assert any(e["titulo"] == "Receta Suelta" for e in dia["extras"])


def test_update_registro_extra_recomputes_stock(client, db):
    """PUT /registro/{id} corrects an extra in place — revert old effects, apply new ones."""
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)

    created = client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 5.0},
        headers=_headers(token),
    ).json()
    registro_id = created["registro_id"]
    assert _saldo(db, ing.id) == 45.0  # 50 - 5 * 1kg

    res = client.put(
        f"/api/produccion/registro/{registro_id}",
        json={"cantidad_real": 8.0},
        headers=_headers(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["cantidad_real"] == 8.0
    assert _saldo(db, ing.id) == 42.0  # 50 - 8, not 50 - 5 - 8


def test_update_registro_requires_positive_cantidad(client, db):
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)
    created = client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 5.0},
        headers=_headers(token),
    ).json()

    res = client.put(
        f"/api/produccion/registro/{created['registro_id']}",
        json={"cantidad_real": 0},
        headers=_headers(token),
    )
    assert res.status_code == 422


# ==============================================================
# Direct production (/producir) + delete reverses stock
# ==============================================================


def test_producir_deducts_ingredient_stock(client, db):
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)

    res = client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 5.0},
        headers=_headers(token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["ok"] is True
    assert data["producto"] == "Pan de Prueba"
    assert _saldo(db, ing.id) == 45.0  # 50 - 5 * 1kg


def test_producir_requires_positive_cantidad(client, db):
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)
    res = client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 0},
        headers=_headers(token),
    )
    assert res.status_code == 422


def test_delete_registro_reverses_stock(client, db):
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)

    res = client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 5.0},
        headers=_headers(token),
    )
    registro_id = res.json()["registro_id"]
    assert _saldo(db, ing.id) == 45.0

    res2 = client.delete(f"/api/produccion/registro/{registro_id}", headers=_headers(token))
    assert res2.status_code == 200
    assert res2.json()["ok"] is True
    assert _saldo(db, ing.id) == 50.0


# ==============================================================
# Analytics
# ==============================================================


def test_analytics_reports_completion_rate(client, db):
    token, _ = _setup(client, db)
    tarea = _crear_tarea(client, token, titulo="Tarea analitica", dia_semana=DOW_HOY, tipo="produccion")
    client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY.isoformat(), "completada": True},
        headers=_headers(token),
    )

    res = client.get(
        f"/api/produccion/analytics?desde={HOY.isoformat()}&hasta={HOY.isoformat()}",
        headers=_headers(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["resumen"]["total_planificadas"] >= 1
    assert data["resumen"]["total_completadas"] >= 1
    tarea_stat = next((t for t in data["por_tarea"] if t["tarea_id"] == tarea["id"]), None)
    assert tarea_stat is not None
    assert tarea_stat["veces_completada"] == 1


def test_analytics_rejects_bad_date_range(client, db):
    token, _ = _setup(client, db)
    res = client.get("/api/produccion/analytics?desde=not-a-date&hasta=2024-01-05", headers=_headers(token))
    assert res.status_code == 400
