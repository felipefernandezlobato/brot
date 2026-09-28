from datetime import date, timedelta

from app.main import app
from app.routers.inventario import router

app.include_router(router)

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, InventarioRegistro, MovimientoStock, User
from app.services.stock import (
    deducir_materia_prima,
    get_saldo_materia_prima,
    get_saldos_materia_prima,
)


def _setup(client, db):
    """Create an admin user + one active ingredient; return (token, ing_id)."""
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina 000",
        categoria_id=cat.id,
        unidad_compra="kg",
        cantidad_compra=25,
        precio_compra=5000,
        unidad_uso="g",
    )
    db.add(ing)
    db.commit()
    token = client.post(
        "/api/auth/login", json={"name": "Admin", "pin": "0000"}
    ).json()["token"]
    return token, ing.id


def test_create_inventario_record(client, db):
    token, ing_id = _setup(client, db)
    res = client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 5.0, "unidad": "kg"}],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert len(body) == 1
    assert body[0]["ingrediente_id"] == ing_id
    assert body[0]["cantidad"] == 5.0
    assert body[0]["unidad"] == "kg"
    assert body[0]["id"] is not None


def test_list_inventario(client, db):
    token, ing_id = _setup(client, db)

    # Seed one record
    client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 3.0, "unidad": "kg"}],
        headers={"Authorization": f"Bearer {token}"},
    )

    # List all
    res = client.get("/api/inventario", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()) == 1

    # Filter by matching ingrediente_id
    res2 = client.get(
        f"/api/inventario?ingrediente_id={ing_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200
    assert len(res2.json()) == 1

    # Filter by non-existent ingrediente_id
    res3 = client.get(
        "/api/inventario?ingrediente_id=9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res3.status_code == 200
    assert len(res3.json()) == 0


def test_get_stock_actual(client, db):
    token, ing_id = _setup(client, db)

    # First snapshot
    client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 5.0, "unidad": "kg"}],
        headers={"Authorization": f"Bearer {token}"},
    )
    # Second (more recent) snapshot
    client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 2.5, "unidad": "kg"}],
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/api/inventario/actual", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    # Only one entry per ingredient (the latest)
    assert len(body) == 1
    assert body[0]["ingrediente_id"] == ing_id
    assert body[0]["cantidad"] == 2.5


def test_batch_create_inventario(client, db):
    token, ing_id = _setup(client, db)

    # Add a second ingredient to the same db session
    cat2 = Categoria(nombre="Grasas", tipo="ingrediente")
    db.add(cat2)
    db.flush()
    ing2 = Ingrediente(
        nombre="Manteca",
        categoria_id=cat2.id,
        unidad_compra="kg",
        cantidad_compra=1,
        precio_compra=1000,
        unidad_uso="g",
    )
    db.add(ing2)
    db.commit()

    res = client.post(
        "/api/inventario",
        json=[
            {"ingrediente_id": ing_id, "cantidad": 10.0, "unidad": "kg"},
            {"ingrediente_id": ing2.id, "cantidad": 0.5, "unidad": "kg"},
        ],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert len(body) == 2
    ing_ids = {r["ingrediente_id"] for r in body}
    assert ing_id in ing_ids
    assert ing2.id in ing_ids


def test_calculado_devuelve_saldo_acumulado_por_ingrediente(client, db):
    token, ing_id = _setup(client, db)

    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id, cantidad=-2.5,
        unidad="kg", tipo_movimiento="produccion_consumo", fecha=date(2026, 8, 14),
    ))
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id, cantidad=10.0,
        unidad="kg", tipo_movimiento="recepcion", fecha=date(2026, 8, 15),
    ))
    db.commit()

    res = client.get("/api/inventario/calculado", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    ingredientes = {i["ingrediente_id"]: i["historial"] for i in res.json()["ingredientes"]}
    assert ingredientes[ing_id] == [
        {"fecha": "2026-08-14", "cantidad": -2.5},
        {"fecha": "2026-08-15", "cantidad": 7.5},
    ]


def test_calculado_sin_movimientos_no_aparece(client, db):
    """An ingredient counted only manually has no ledger entries -- absent
    from the response, not a zero/error."""
    token, ing_id = _setup(client, db)
    client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 5.0, "unidad": "kg"}],
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/api/inventario/calculado", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    ids = [i["ingrediente_id"] for i in res.json()["ingredientes"]]
    assert ing_id not in ids


def _con_consumo_backdateado(db, ing_id):
    """A 100 g count, then a 28/09-dated consumption, then a 25/09-dated one
    saved after it -- the production shape that breaks the stored chain."""
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=100.0, unidad="g",
        fecha_registro=date(2026, 9, 24),
    ))
    db.commit()
    deducir_materia_prima(db, ing_id, 10, "g", "registro_produccion:1", fecha=date(2026, 9, 28))
    # Backdated: saved later, but dated before the row above.
    deducir_materia_prima(db, ing_id, 20, "g", "registro_produccion:2", fecha=date(2026, 9, 25))
    db.commit()


def test_saldos_materia_prima_ve_el_consumo_backdateado(client, db):
    """A production logged for an earlier date AFTER a later-dated one already
    exists never becomes the tip of the InventarioRegistro chain, so the stored
    total silently misses it (found 2026-09-28 on six ingredients). The
    ledger-backed read has no such ordering dependency and must still see it.
    """
    _token, ing_id = _setup(client, db)
    _con_consumo_backdateado(db, ing_id)

    # The write-path read is stale by exactly the backdated consumption.
    assert get_saldo_materia_prima(db, ing_id) == 90.0
    assert get_saldos_materia_prima(db, [ing_id])[ing_id] == 70.0


def test_alertas_marca_stock_negativo(client, db):
    """Negative stock is a real signal here (something never got recorded), so
    it must alert -- the old `cantidad == 0` check only ever fired on exactly
    zero, so a negative balance was reported as the milder sin_registro (or,
    with a stored row present, not at all)."""
    token, ing_id = _setup(client, db)
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id,
        cantidad=-5.0, unidad="g", tipo_movimiento="produccion_consumo",
        fecha=date(2026, 9, 25),
    ))
    db.commit()

    res = client.get("/api/inventario/alertas", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["ingrediente_id"] == ing_id
    assert body[0]["alerta"] == "sin_stock"
    assert body[0]["cantidad"] == -5.0


def test_alertas_sin_registro_cuando_no_hay_nada(client, db):
    """No ledger movement and no count at all stays sin_registro, not sin_stock."""
    token, ing_id = _setup(client, db)

    res = client.get("/api/inventario/alertas", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["ingrediente_id"] == ing_id
    assert body[0]["alerta"] == "sin_registro"
    assert body[0]["cantidad"] is None


def test_alertas_usa_el_conteo_cuando_no_hay_ledger(client, db):
    """An ingredient counted but never produced with has no ledger points at
    all; it falls back to its last count, so a positive one is not an alert."""
    token, ing_id = _setup(client, db)
    client.post(
        "/api/inventario",
        json=[{"ingrediente_id": ing_id, "cantidad": 5.0, "unidad": "kg"}],
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get("/api/inventario/alertas", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []


def test_recomendacion_usa_el_saldo_del_ledger(client, db):
    """The stock the par level gets compared against is the ledger balance,
    not the stale (high) stored total."""
    token, ing_id = _setup(client, db)
    _con_consumo_backdateado(db, ing_id)

    res = client.get("/api/inventario/recomendacion", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    items = [i for g in res.json()["por_proveedor"] for i in g["items"]]
    item = next(i for i in items if i["ingrediente_id"] == ing_id)
    assert item["stock_actual"] == 70.0


def test_conteo_de_hoy_manda_sobre_el_ledger(client, db):
    """A count taken TODAY has to be what these views report.

    historial_movimientos_acumulado only re-anchors from the day AFTER a count
    (on the count's own date it keeps the pre-count trajectory, so the gap is
    visible in the historial pivot). Reading its last point raw made a count
    entered today invisible until tomorrow -- and count-then-order is the
    normal workflow, so every suggestion on count day would be computed
    against the numbers the count just replaced.
    """
    token, ing_id = _setup(client, db)
    hoy = date.today()
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id,
        cantidad=-10.0, unidad="g", tipo_movimiento="produccion_consumo",
        fecha=hoy - timedelta(days=3),
    ))
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=50.0, unidad="g", fecha_registro=hoy,
    ))
    db.commit()

    assert get_saldos_materia_prima(db, [ing_id])[ing_id] == 50.0

    # ...so a recount to a healthy level clears the alert the same day.
    res = client.get("/api/inventario/alertas", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == []
