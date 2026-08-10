from datetime import date

from app.auth import hash_pin
from app.main import app
from app.models import User
from app.routers.produccion import router

app.include_router(router)


# ==============================================================
# Helpers
# ==============================================================


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, user.id


def _create_producto(client, token, nombre="Pan de campo", categoria="panes", unidad="u"):
    res = client.post(
        "/api/produccion/productos",
        json={"nombre": nombre, "categoria": categoria, "unidad": unidad, "shelf_life_days": 3},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    return res.json()


# ==============================================================
# Tests
# ==============================================================


def test_create_producto_produccion(client, db):
    token, _ = _setup(client, db)

    res = client.post(
        "/api/produccion/productos",
        json={
            "nombre": "Pan de campo",
            "categoria": "panes",
            "unidad": "u",
            "shelf_life_days": 3,
            "default_qty": 20.0,
            "position": 1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["nombre"] == "Pan de campo"
    assert data["categoria"] == "panes"
    assert data["unidad"] == "u"
    assert data["shelf_life_days"] == 3
    assert data["default_qty"] == 20.0
    assert "id" in data

    # Verify GET list
    res2 = client.get("/api/produccion/productos", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert len(res2.json()) == 1

    # Verify GET by id
    prod_id = data["id"]
    res3 = client.get(f"/api/produccion/productos/{prod_id}", headers={"Authorization": f"Bearer {token}"})
    assert res3.status_code == 200
    assert res3.json()["nombre"] == "Pan de campo"

    # Update
    res4 = client.put(
        f"/api/produccion/productos/{prod_id}",
        json={"default_qty": 25.0, "is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res4.status_code == 200
    assert res4.json()["default_qty"] == 25.0
    assert res4.json()["is_active"] is False

    # Delete
    res5 = client.delete(f"/api/produccion/productos/{prod_id}", headers={"Authorization": f"Bearer {token}"})
    assert res5.status_code == 200
    assert res5.json()["ok"] is True


def test_create_plan_entry(client, db):
    token, _ = _setup(client, db)
    prod = _create_producto(client, token, nombre="Croissant", categoria="bollería")
    prod_id = prod["id"]

    # Create plan entry — week 1, Monday (day_of_week=0)
    res = client.post(
        "/api/produccion/plan",
        json={"producto_id": prod_id, "week_number": 1, "day_of_week": 0, "planned_qty": 50.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["producto_id"] == prod_id
    assert data["week_number"] == 1
    assert data["day_of_week"] == 0
    assert data["planned_qty"] == 50.0

    # GET plan filtered by week and day
    res2 = client.get(
        "/api/produccion/plan?week_number=1&day_of_week=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200
    assert len(res2.json()) == 1
    assert res2.json()[0]["planned_qty"] == 50.0

    # POST again (same key) should upsert, not error
    res3 = client.post(
        "/api/produccion/plan",
        json={"producto_id": prod_id, "week_number": 1, "day_of_week": 0, "planned_qty": 75.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res3.status_code == 201
    assert res3.json()["planned_qty"] == 75.0

    # Only one entry should exist
    res4 = client.get(
        "/api/produccion/plan?week_number=1&day_of_week=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(res4.json()) == 1


def test_log_production(client, db):
    token, user_id = _setup(client, db)
    prod = _create_producto(client, token, nombre="Baguette")
    prod_id = prod["id"]

    fecha = date.today().isoformat()

    # Create log entry
    res = client.post(
        "/api/produccion/log",
        json={
            "producto_id": prod_id,
            "target_date": fecha,
            "actual_qty": 30.0,
            "duration_minutes_machine": 45,
            "duration_minutes_human": 60,
            "recorded_by": user_id,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["producto_id"] == prod_id
    assert data["actual_qty"] == 30.0
    assert data["duration_minutes_machine"] == 45
    assert data["duration_minutes_human"] == 60
    log_id = data["id"]

    # GET log for today
    res2 = client.get(
        f"/api/produccion/log?fecha={fecha}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 200
    assert len(res2.json()) == 1
    assert res2.json()[0]["id"] == log_id

    # PUT — update log entry
    res3 = client.put(
        f"/api/produccion/log/{log_id}",
        json={"actual_qty": 35.0, "notes": "Lote adicional"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res3.status_code == 200
    assert res3.json()["actual_qty"] == 35.0
    assert res3.json()["notes"] == "Lote adicional"

    # Duplicate log for same product+date should return 409
    res4 = client.post(
        "/api/produccion/log",
        json={"producto_id": prod_id, "target_date": fecha, "actual_qty": 5.0, "recorded_by": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res4.status_code == 409


def test_calendario_view(client, db):
    token, user_id = _setup(client, db)
    prod = _create_producto(client, token, nombre="Focaccia")
    prod_id = prod["id"]

    today = date.today()
    week_num = (today.isocalendar().week - 1) % 4 + 1
    dow = today.weekday()

    # Create a plan entry matching today's cycle slot
    client.post(
        "/api/produccion/plan",
        json={"producto_id": prod_id, "week_number": week_num, "day_of_week": dow, "planned_qty": 40.0},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Log actual production for today
    client.post(
        "/api/produccion/log",
        json={"producto_id": prod_id, "target_date": today.isoformat(), "actual_qty": 38.0, "recorded_by": user_id},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Query the calendar for today only
    res = client.get(
        f"/api/produccion/calendario?fecha_desde={today.isoformat()}&fecha_hasta={today.isoformat()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

    entry = next((e for e in data if e["producto_id"] == prod_id), None)
    assert entry is not None, "Calendar entry for producto not found"
    assert entry["planned_qty"] == 40.0
    assert entry["actual_qty"] == 38.0
    assert entry["fecha"] == today.isoformat()
    assert entry["week_number"] == week_num
    assert entry["day_of_week"] == dow

    # Invalid date range should return 400
    res2 = client.get(
        "/api/produccion/calendario?fecha_desde=2024-01-10&fecha_hasta=2024-01-05",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 400
