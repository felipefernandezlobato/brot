from datetime import date

from app.auth import hash_pin
from app.main import app
from app.models import User
from app.routers.temperaturas import router

app.include_router(router)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _admin_token(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    return res.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_frigorifico(client, token, nombre="Nevera 1", max_temp=5.0):
    return client.post("/api/temperaturas/frigorificos", json={
        "nombre": nombre,
        "tipo": "frigorifico",
        "max_temp": max_temp,
        "position": 0,
        "is_active": True,
    }, headers=_auth(token))


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_create_frigorifico(client, db):
    token = _admin_token(client, db)
    res = _make_frigorifico(client, token)
    assert res.status_code == 201
    body = res.json()
    assert body["nombre"] == "Nevera 1"
    assert body["max_temp"] == 5.0
    assert body["is_active"] is True


def test_list_frigorificos(client, db):
    token = _admin_token(client, db)
    _make_frigorifico(client, token, nombre="A")
    _make_frigorifico(client, token, nombre="B")
    res = client.get("/api/temperaturas/frigorificos", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_update_frigorifico(client, db):
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token).json()
    res = client.put(f"/api/temperaturas/frigorificos/{frig['id']}",
                     json={"max_temp": 3.0},
                     headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["max_temp"] == 3.0


def test_delete_frigorifico(client, db):
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token).json()
    res = client.delete(f"/api/temperaturas/frigorificos/{frig['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["ok"] is True
    # Should no longer appear in list (soft-deleted)
    list_res = client.get("/api/temperaturas/frigorificos", headers=_auth(token))
    assert all(f["id"] != frig["id"] for f in list_res.json())


def test_record_temperature(client, db):
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token, max_temp=5.0).json()

    res = client.post("/api/temperaturas/apertura",
                      json=[{"frigorifico_id": frig["id"], "value": 4.0}],
                      headers=_auth(token))
    assert res.status_code == 201
    readings = res.json()
    assert len(readings) == 1
    assert readings[0]["frigorifico_id"] == frig["id"]
    assert readings[0]["value"] == 4.0
    assert readings[0]["shift"] == "apertura"
    assert readings[0]["target_date"] == date.today().isoformat()
    assert readings[0]["is_alert"] is False


def test_temperature_alert(client, db):
    """Temperature above max_temp should trigger is_alert=True."""
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token, max_temp=5.0).json()

    res = client.post("/api/temperaturas/cierre",
                      json=[{"frigorifico_id": frig["id"], "value": 8.5}],
                      headers=_auth(token))
    assert res.status_code == 201
    reading = res.json()[0]
    assert reading["value"] == 8.5
    assert reading["is_alert"] is True


def test_temperature_no_alert_at_limit(client, db):
    """Temperature exactly at max_temp should NOT trigger alert."""
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token, max_temp=5.0).json()

    res = client.post("/api/temperaturas/apertura",
                      json=[{"frigorifico_id": frig["id"], "value": 5.0}],
                      headers=_auth(token))
    assert res.status_code == 201
    assert res.json()[0]["is_alert"] is False


def test_temperature_batch_multiple_fridges(client, db):
    token = _admin_token(client, db)
    f1 = _make_frigorifico(client, token, nombre="F1", max_temp=5.0).json()
    f2 = _make_frigorifico(client, token, nombre="F2", max_temp=3.0).json()

    res = client.post("/api/temperaturas/apertura",
                      json=[
                          {"frigorifico_id": f1["id"], "value": 4.0},
                          {"frigorifico_id": f2["id"], "value": 4.0},
                      ],
                      headers=_auth(token))
    assert res.status_code == 201
    readings = res.json()
    assert len(readings) == 2
    by_frig = {r["frigorifico_id"]: r for r in readings}
    assert by_frig[f1["id"]]["is_alert"] is False   # 4.0 <= 5.0
    assert by_frig[f2["id"]]["is_alert"] is True     # 4.0 > 3.0


def test_temperature_upsert_same_shift(client, db):
    """Recording a second time for the same fridge+date+shift updates the reading."""
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token, max_temp=5.0).json()

    client.post("/api/temperaturas/apertura",
                json=[{"frigorifico_id": frig["id"], "value": 4.0}],
                headers=_auth(token))

    res = client.post("/api/temperaturas/apertura",
                      json=[{"frigorifico_id": frig["id"], "value": 2.5}],
                      headers=_auth(token))
    assert res.status_code == 201
    assert res.json()[0]["value"] == 2.5


def test_temperature_historial(client, db):
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token).json()

    client.post("/api/temperaturas/apertura",
                json=[{"frigorifico_id": frig["id"], "value": 4.0}],
                headers=_auth(token))

    res = client.get(f"/api/temperaturas/historial?frigorifico_id={frig['id']}",
                     headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["frigorifico_id"] == frig["id"]


def test_invalid_shift(client, db):
    token = _admin_token(client, db)
    frig = _make_frigorifico(client, token).json()
    res = client.post("/api/temperaturas/turno_noche",
                      json=[{"frigorifico_id": frig["id"], "value": 4.0}],
                      headers=_auth(token))
    assert res.status_code == 422
