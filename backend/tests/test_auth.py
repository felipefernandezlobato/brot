from app.models import User
from app.auth import hash_pin


def test_login_success(client, db):
    user = User(name="Test", pin_hash=hash_pin("1234"), role="admin")
    db.add(user)
    db.commit()

    res = client.post("/api/auth/login", json={"name": "Test", "pin": "1234"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_pin(client, db):
    user = User(name="Test", pin_hash=hash_pin("1234"), role="admin")
    db.add(user)
    db.commit()

    res = client.post("/api/auth/login", json={"name": "Test", "pin": "0000"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={"name": "Ghost", "pin": "1234"})
    assert res.status_code == 401


def test_me_with_token(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()

    login = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    token = login.json()["token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["name"] == "Admin"
    assert res.json()["role"] == "admin"


def test_me_without_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_users_list_public(client, db):
    user = User(name="Ana", pin_hash=hash_pin("1111"), role="staff")
    db.add(user)
    db.commit()

    res = client.get("/api/auth/users")
    assert res.status_code == 200
    users = res.json()
    assert len(users) == 1
    assert users[0]["name"] == "Ana"
    assert "pin_hash" not in users[0]
