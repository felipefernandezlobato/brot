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
    # Registration logs the customer straight in — no separate login step needed.
    token = res.json()["token"]
    assert token

    me = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["nombre"] == "Juan"
    assert me.json()["email"] == "test@example.com"


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


# ── Email sin distinguir mayusculas ───────────────────────────────────────────


def test_login_ignora_mayusculas(client):
    """El teclado del movil capitaliza la primera letra: un cliente registrado
    como Lisetteolula@gmail.com no podia entrar escribiendo lisetteolula@..."""
    client.post("/api/auth/cliente/registro", json={
        "email": "Lisetteolula@gmail.com", "password": "secreto123", "nombre": "Lisette"
    })

    for intento in ("lisetteolula@gmail.com", "LISETTEOLULA@GMAIL.COM",
                    "Lisetteolula@Gmail.com", "  lisetteolula@gmail.com  "):
        res = client.post("/api/auth/cliente/login",
                          json={"email": intento, "password": "secreto123"})
        assert res.status_code == 200, f"fallo con {intento!r}: {res.text}"
        assert res.json()["token"]


def test_registro_guarda_el_email_normalizado(client):
    res = client.post("/api/auth/cliente/registro", json={
        "email": "  Lisetteolula@Gmail.com  ", "password": "secreto123", "nombre": "Lisette"
    })
    assert res.status_code == 201
    token = res.json()["token"]
    me = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "lisetteolula@gmail.com"


def test_no_se_puede_duplicar_cambiando_mayusculas(client):
    client.post("/api/auth/cliente/registro", json={
        "email": "lisette@gmail.com", "password": "abc", "nombre": "A"
    })
    res = client.post("/api/auth/cliente/registro", json={
        "email": "Lisette@Gmail.com", "password": "def", "nombre": "B"
    })
    assert res.status_code == 409


def test_password_sigue_distinguiendo_mayusculas(client):
    """Normalizar el email no debe aflojar la contrasena."""
    client.post("/api/auth/cliente/registro", json={
        "email": "test2@example.com", "password": "Secreto123", "nombre": "A"
    })
    res = client.post("/api/auth/cliente/login",
                      json={"email": "test2@example.com", "password": "secreto123"})
    assert res.status_code == 401
