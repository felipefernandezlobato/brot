from app.main import app
from app.routers.auth_cliente import router

app.include_router(router)


def test_register_cliente(client):
    res = client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com",
        "password": "secreto123",
        "nombre": "Juan",
        "telefono": "+5491155551234",
    })
    assert res.status_code == 201
    assert res.json()["email"] == "test@example.com"
    assert "password" not in res.json()


def test_register_duplicate_email(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "abc", "nombre": "A"
    })
    res = client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "def", "nombre": "B"
    })
    assert res.status_code == 409


def test_login_cliente(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "secreto123", "nombre": "Juan"
    })
    res = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "secreto123"
    })
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "secreto123", "nombre": "Juan"
    })
    res = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "wrong"
    })
    assert res.status_code == 401


def test_cliente_me(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "test@example.com", "password": "secreto123", "nombre": "Juan"
    })
    login = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "secreto123"
    })
    token = login.json()["token"]
    res = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["nombre"] == "Juan"
