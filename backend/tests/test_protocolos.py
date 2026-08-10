from datetime import date

from app.auth import hash_pin
from app.main import app
from app.models import User
from app.routers.protocolos import router

app.include_router(router)


# ── Fixtures / helpers ─────────────────────────────────────────────────────────

def _admin_token(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    return res.json()["token"]


def _staff_token(client, db):
    user = User(name="Staff", pin_hash=hash_pin("1111"), role="staff")
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": "Staff", "pin": "1111"})
    return res.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_template(client, token, checklist_type="diario", shift="apertura", task_name="Limpiar"):
    return client.post("/api/protocolos/templates", json={
        "checklist_type": checklist_type,
        "section": "Apertura",
        "task_name": task_name,
        "position": 0,
        "shift": shift,
    }, headers=_auth(token))


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_create_template(client, db):
    token = _admin_token(client, db)
    res = _make_template(client, token)
    assert res.status_code == 201
    body = res.json()
    assert body["checklist_type"] == "diario"
    assert body["task_name"] == "Limpiar"
    assert body["shift"] == "apertura"
    assert body["is_active"] is True


def test_list_templates(client, db):
    token = _admin_token(client, db)
    _make_template(client, token, task_name="Tarea A")
    _make_template(client, token, checklist_type="semanal", shift=None, task_name="Tarea B")
    res = client.get("/api/protocolos/templates", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_update_template(client, db):
    token = _admin_token(client, db)
    created = _make_template(client, token).json()
    res = client.put(f"/api/protocolos/templates/{created['id']}",
                     json={"task_name": "Nuevo nombre"},
                     headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["task_name"] == "Nuevo nombre"


def test_delete_template(client, db):
    token = _admin_token(client, db)
    created = _make_template(client, token).json()
    res = client.delete(f"/api/protocolos/templates/{created['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_get_hoy_splits_by_shift(client, db):
    token = _admin_token(client, db)
    _make_template(client, token, shift="apertura", task_name="Abrir caja")
    _make_template(client, token, shift="cierre", task_name="Cerrar caja")

    res = client.get("/api/protocolos/hoy", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert "fecha" in body
    assert body["fecha"] == date.today().isoformat()
    assert len(body["apertura"]) == 1
    assert len(body["cierre"]) == 1
    assert body["apertura"][0]["template"]["task_name"] == "Abrir caja"
    assert body["cierre"][0]["template"]["task_name"] == "Cerrar caja"
    # Completions start as null
    assert body["apertura"][0]["completion"] is None


def test_get_hoy_shows_completion(client, db):
    token = _admin_token(client, db)
    tmpl = _make_template(client, token, shift="apertura", task_name="Tarea").json()
    today = date.today().isoformat()

    client.post("/api/protocolos/completar", json={
        "template_id": tmpl["id"],
        "target_date": today,
    }, headers=_auth(token))

    res = client.get("/api/protocolos/hoy", headers=_auth(token))
    assert res.json()["apertura"][0]["completion"] is not None


def test_get_semanal(client, db):
    token = _admin_token(client, db)
    _make_template(client, token, checklist_type="semanal", shift=None, task_name="Limpieza semanal")
    res = client.get("/api/protocolos/semanal", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert "period" in body
    assert body["period"].startswith("20")  # year prefix
    assert len(body["items"]) == 1
    assert body["items"][0]["completion"] is None


def test_get_mensual(client, db):
    token = _admin_token(client, db)
    _make_template(client, token, checklist_type="mensual", shift=None, task_name="Calibración mensual")
    res = client.get("/api/protocolos/mensual", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert "period" in body
    assert len(body["items"]) == 1


def test_completar_task(client, db):
    token = _admin_token(client, db)
    tmpl = _make_template(client, token).json()
    today = date.today().isoformat()

    res = client.post("/api/protocolos/completar", json={
        "template_id": tmpl["id"],
        "target_date": today,
    }, headers=_auth(token))

    assert res.status_code == 201
    body = res.json()
    assert body["template_id"] == tmpl["id"]
    assert body["target_date"] == today
    assert body["is_satisfactory"] is True


def test_completar_duplicate_409(client, db):
    token = _admin_token(client, db)
    tmpl = _make_template(client, token).json()
    today = date.today().isoformat()
    payload = {"template_id": tmpl["id"], "target_date": today}

    first = client.post("/api/protocolos/completar", json=payload, headers=_auth(token))
    assert first.status_code == 201

    second = client.post("/api/protocolos/completar", json=payload, headers=_auth(token))
    assert second.status_code == 409


def test_undo_completion_admin_anytime(client, db):
    token = _admin_token(client, db)
    tmpl = _make_template(client, token).json()
    today = date.today().isoformat()

    completion = client.post("/api/protocolos/completar", json={
        "template_id": tmpl["id"],
        "target_date": today,
    }, headers=_auth(token)).json()

    res = client.delete(f"/api/protocolos/completar/{completion['id']}", headers=_auth(token))
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_undo_completion_staff_own_recent(client, db):
    """Staff can undo their own completion within the 1-hour window."""
    admin_token = _admin_token(client, db)
    staff_token = _staff_token(client, db)

    tmpl = _make_template(client, admin_token).json()
    today = date.today().isoformat()

    completion = client.post("/api/protocolos/completar", json={
        "template_id": tmpl["id"],
        "target_date": today,
    }, headers=_auth(staff_token)).json()

    res = client.delete(f"/api/protocolos/completar/{completion['id']}", headers=_auth(staff_token))
    assert res.status_code == 200


def test_review_completion(client, db):
    token = _admin_token(client, db)
    tmpl = _make_template(client, token).json()
    today = date.today().isoformat()

    completion = client.post("/api/protocolos/completar", json={
        "template_id": tmpl["id"],
        "target_date": today,
    }, headers=_auth(token)).json()

    res = client.put(f"/api/protocolos/completar/{completion['id']}/revision",
                     json={"is_satisfactory": False, "review_note": "Falta repaso"},
                     headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert body["is_satisfactory"] is False
    assert body["review_note"] == "Falta repaso"
    assert body["reviewed_by"] is not None


def test_historial_day(client, db):
    token = _admin_token(client, db)
    tmpl = _make_template(client, token).json()
    today = date.today().isoformat()

    client.post("/api/protocolos/completar", json={
        "template_id": tmpl["id"],
        "target_date": today,
    }, headers=_auth(token))

    res = client.get(f"/api/protocolos/historial?mode=day&period={today}", headers=_auth(token))
    assert res.status_code == 200
    assert len(res.json()) == 1
