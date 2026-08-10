from app.auth import hash_pin
from app.models import Permission, User


def _login(client, db, role="admin"):
    user = User(name=f"User-{role}", pin_hash=hash_pin("1234"), role=role)
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": f"User-{role}", "pin": "1234"})
    return res.json()["token"]


def test_admin_bypasses_permissions(client, db):
    token = _login(client, db, "admin")
    res = client.get("/api/permisos", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_staff_denied_without_permission(client, db):
    token = _login(client, db, "staff")
    perm = Permission(role="staff", module="ingredientes", action="view", allowed=False)
    db.add(perm)
    db.commit()

    res = client.get("/api/permisos/check/ingredientes/view",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["allowed"] is False


def test_staff_allowed_with_permission(client, db):
    token = _login(client, db, "staff")
    perm = Permission(role="staff", module="ingredientes", action="view", allowed=True)
    db.add(perm)
    db.commit()

    res = client.get("/api/permisos/check/ingredientes/view",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["allowed"] is True


def test_admin_can_update_permissions(client, db):
    token = _login(client, db, "admin")
    perm = Permission(role="staff", module="ingredientes", action="view", allowed=True)
    db.add(perm)
    db.commit()

    res = client.put(f"/api/permisos/{perm.id}",
                     json={"allowed": False},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["allowed"] is False
