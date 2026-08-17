from datetime import date

from app.main import app
from app.routers.inventario import router

app.include_router(router)

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, MovimientoStock, User


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
