"""Production module tests, against the current TareaProduccion/RegistroProduccion
API — the old ProductoProduccion/PlanProduccion/LogProduccion CRUD these tests used
to exercise was removed from the router a while back (the models are still in
models.py but have zero routes), and nobody updated the tests to match. The current
system is: a weekly recurring schedule (TareaProduccion), daily completion records
(RegistroProduccion) that move stock, and a direct /producir endpoint for
unplanned/extra production tied straight to a ProductoCongelado.
"""

from datetime import date, timedelta

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

# El plan del domingo esta vacio a proposito (el obrador trabaja Lun-Sab), y
# ninguna tarea puede tener dia_semana=7. Asi que un test que crea una tarea
# del plan y espera verla "hoy" tiene que trabajar sobre un dia laborable, o
# los domingos falla por el calendario y no por un fallo real.
# Esto vale para los dos endpoints: `/dia` devuelve el domingo vacio y
# `/analytics` lo lista solo si hubo algo cargado.
HOY_LABORAL = HOY if HOY.isoweekday() <= 6 else HOY - timedelta(days=1)
DOW_LABORAL = HOY_LABORAL.isoweekday()

# Un domingo de verdad, para los tests que prueban justamente el domingo.
DOMINGO = HOY + timedelta(days=7 - HOY.isoweekday())


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
    tarea = _crear_tarea(client, token, titulo="Tarea de hoy", dia_semana=DOW_LABORAL)

    res = client.get(f"/api/produccion/dia?fecha={HOY_LABORAL.isoformat()}", headers=_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["dia_semana"] == DOW_LABORAL
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
    tarea = _crear_tarea(client, token, titulo="Limpiar obrador", dia_semana=DOW_LABORAL, tipo="limpieza")

    res = client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY_LABORAL.isoformat(), "completada": True},
        headers=_headers(token),
    )
    assert res.status_code == 201
    assert res.json()["completada"] is True
    assert res.json()["movimientos"] == 0

    dia = client.get(f"/api/produccion/dia?fecha={HOY_LABORAL.isoformat()}", headers=_headers(token)).json()
    entry = next(t for t in dia["tareas"] if t["tarea_id"] == tarea["id"])
    assert entry["completada"] is True

    # Un-completing (undo) upserts the same record back to false.
    res2 = client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY_LABORAL.isoformat(), "completada": False},
        headers=_headers(token),
    )
    assert res2.status_code == 201
    assert res2.json()["completada"] is False


def test_registro_requires_cantidad_when_tarea_has_producto(client, db):
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)
    tarea = _crear_tarea(client, token, titulo="Hornear Pan de Prueba", dia_semana=DOW_LABORAL, receta_id=receta.id)
    # producto_congelado_id isn't settable via TareaProduccionCreate (real schedules
    # seed it directly), so wire it up the same way here.
    t_row = db.query(TareaProduccion).filter(TareaProduccion.id == tarea["id"]).first()
    t_row.producto_congelado_id = prod.id
    db.commit()

    # Fecha HOY y no HOY_LABORAL: esta prueba no lee `/dia`, asi que el dia de
    # la semana no le importa, y el conteo base del ingrediente que arma
    # `_producto_con_receta` esta fechado HOY. Deducir en una fecha ANTERIOR a
    # ese conteo no mueve el saldo que lee `_saldo`, porque
    # `get_saldo_materia_prima` se queda con la fila de `fecha_registro` mas
    # alta (ver CLAUDE.md, "Two parallel ways to read materia prima stock").
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


def test_registro_extra_tarea_requires_duracion(client, db):
    """A non-production extra (Limpieza, LLEVAR PEDIDO...) has no cantidad to
    produce, so duracion is what's required instead of cantidad_real."""
    token, _ = _setup(client, db)
    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "titulo": "Limpieza"},
        headers=_headers(token),
    )
    assert res.status_code == 422


def test_registro_extra_tarea_sin_producto(client, db):
    token, _ = _setup(client, db)
    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "titulo": "Limpieza", "duracion_real": 30},
        headers=_headers(token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["titulo_extra"] == "Limpieza"
    assert data["cantidad_real"] is None
    assert data["duracion_real"] == 30

    dia = client.get(f"/api/produccion/dia?fecha={HOY.isoformat()}", headers=_headers(token)).json()
    extra = next(e for e in dia["extras"] if e["titulo"] == "Limpieza")
    assert extra["cantidad_real"] is None


def test_registro_extra_neither_receta_nor_titulo_rejected(client, db):
    token, _ = _setup(client, db)
    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "duracion_real": 30},
        headers=_headers(token),
    )
    assert res.status_code == 422


def test_update_registro_extra_tarea_requires_duracion(client, db):
    token, _ = _setup(client, db)
    created = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "titulo": "Limpieza", "duracion_real": 30},
        headers=_headers(token),
    ).json()

    res = client.put(
        f"/api/produccion/registro/{created['id']}",
        json={"duracion_real": None},
        headers=_headers(token),
    )
    assert res.status_code == 422

    res2 = client.put(
        f"/api/produccion/registro/{created['id']}",
        json={"duracion_real": 45, "notas": "se extendio"},
        headers=_headers(token),
    )
    assert res2.status_code == 200
    assert res2.json()["duracion_real"] == 45
    assert res2.json()["cantidad_real"] is None


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
    tarea = _crear_tarea(client, token, titulo="Tarea analitica", dia_semana=DOW_LABORAL, tipo="produccion")
    client.post(
        "/api/produccion/registro",
        json={"tarea_id": tarea["id"], "fecha": HOY_LABORAL.isoformat(), "completada": True},
        headers=_headers(token),
    )

    res = client.get(
        f"/api/produccion/analytics?desde={HOY_LABORAL.isoformat()}&hasta={HOY_LABORAL.isoformat()}",
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


def test_analytics_surfaces_extras_on_days_with_no_plan(client, db):
    """A day with zero scheduled TareaProduccion (e.g. an extra-only product
    like Pizza/Pan Lomo) used to be missing from por_dia entirely, making it
    look like nothing happened. It should now show up with its extra count
    and logged minutes, without a misleading 0/0 completion ratio.
    """
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)

    client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 5.0, "fecha": HOY_LABORAL.isoformat(), "duracion_real": 45},
        headers=_headers(token),
    )

    res = client.get(
        f"/api/produccion/analytics?desde={HOY_LABORAL.isoformat()}&hasta={HOY_LABORAL.isoformat()}",
        headers=_headers(token),
    )
    assert res.status_code == 200
    data = res.json()
    dia = next((d for d in data["por_dia"] if d["fecha"] == HOY_LABORAL.isoformat()), None)
    assert dia is not None
    assert dia["planificadas"] == 0
    assert dia["porcentaje"] is None
    assert dia["extra_count"] == 1
    assert dia["minutos_totales"] == 45


# ==============================================================
# El domingo: sin plan, pero se puede cargar lo que se produzca
# ==============================================================


def test_el_domingo_no_trae_plan(client, db):
    """Antes `/dia` colapsaba el domingo al sabado (`if dow > 6: dow = 6`), asi
    que un domingo la pantalla mostraba las 11 tareas del sabado: nadie
    trabajaba y el plan decia que habia 11 cosas pendientes."""
    token, _ = _setup(client, db)
    _crear_tarea(client, token, titulo="Tarea del sabado", dia_semana=6)

    res = client.get(f"/api/produccion/dia?fecha={DOMINGO.isoformat()}", headers=_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["tareas"] == []
    # Y se llama domingo, no sabado.
    assert data["dia_semana"] == 7
    assert data["dia_nombre"] == "Domingo"


def test_un_domingo_se_puede_cargar_produccion(client, db):
    """El plan vacio no puede significar "no se puede registrar nada": si un
    domingo se produce, hay que poder anotarlo."""
    token, _ = _setup(client, db)
    cat = Categoria(nombre="Panes", tipo="receta")
    db.add(cat)
    db.flush()
    receta = Receta(nombre="Pan del domingo", categoria_id=cat.id, porciones_por_lote=1)
    db.add(receta)
    db.commit()

    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": DOMINGO.isoformat(), "receta_id": receta.id, "cantidad_real": 8.0},
        headers=_headers(token),
    )
    assert res.status_code == 201, res.text

    dia = client.get(
        f"/api/produccion/dia?fecha={DOMINGO.isoformat()}", headers=_headers(token)
    ).json()
    assert dia["tareas"] == []  # sigue sin plan
    assert len(dia["extras"]) == 1
    assert dia["extras"][0]["titulo"] == "Pan del domingo"
    assert dia["extras"][0]["cantidad_real"] == 8.0


def test_no_se_puede_planificar_una_tarea_en_domingo(client, db):
    """Mientras el domingo se colapsaba al sabado, una tarea con dia_semana=7
    era invisible y daba igual. Ahora el domingo se consulta tal cual, asi que
    sin este tope se podria poblar el plan del domingo sin querer."""
    token, _ = _setup(client, db)
    res = client.post(
        "/api/produccion/tareas",
        json={"dia_semana": 7, "titulo": "Amasar el domingo", "tipo": "produccion"},
        headers=_headers(token),
    )
    assert res.status_code == 422

    creada = _crear_tarea(client, token, titulo="Valida", dia_semana=6)
    res2 = client.put(
        f"/api/produccion/tareas/{creada['id']}",
        json={"dia_semana": 7},
        headers=_headers(token),
    )
    assert res2.status_code == 422


def test_analytics_muestra_un_domingo_con_produccion(client, db):
    """Cargar produccion un domingo y que el informe no la cuente seria media
    funcionalidad. `all_dates` salteaba los domingos; la guarda
    `day_planned > 0 or dia_registros` ya alcanza para no listar los vacios."""
    token, _ = _setup(client, db)
    prod, receta, ing = _producto_con_receta(db)

    client.post(
        "/api/produccion/producir",
        json={"producto_id": prod.id, "cantidad_producida": 3.0,
              "fecha": DOMINGO.isoformat(), "duracion_real": 90},
        headers=_headers(token),
    )

    res = client.get(
        f"/api/produccion/analytics?desde={DOMINGO.isoformat()}&hasta={DOMINGO.isoformat()}",
        headers=_headers(token),
    )
    assert res.status_code == 200
    dias = res.json()["por_dia"]
    dia = next((d for d in dias if d["fecha"] == DOMINGO.isoformat()), None)
    assert dia is not None, "el domingo trabajado tiene que salir en el informe"
    assert dia["dia_nombre"] == "Domingo"
    assert dia["planificadas"] == 0
    assert dia["porcentaje"] is None  # 0/0 no es 0%
    assert dia["extra_count"] == 1
    assert dia["minutos_totales"] == 90


def test_analytics_no_lista_un_domingo_vacio(client, db):
    """Incluir los domingos en el recorrido no puede llenar el informe de filas
    de domingos en los que no paso nada."""
    token, _ = _setup(client, db)
    res = client.get(
        f"/api/produccion/analytics?desde={DOMINGO.isoformat()}&hasta={DOMINGO.isoformat()}",
        headers=_headers(token),
    )
    assert res.status_code == 200
    assert res.json()["por_dia"] == []
