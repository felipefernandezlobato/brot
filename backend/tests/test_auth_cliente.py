"""Login del portal de clientes.

Hasta el 2026-10-16 estos tests creaban el cliente con
POST /api/auth/cliente/registro. Ese endpoint se cerro (el alta es por
invitacion, ver test_acceso_cliente.py), asi que el alta pasa ahora por
POST /api/clientes-b2b -- que es donde tuvo que mudarse tambien la
normalizacion del email que estos tests protegen.
"""

from app.auth import hash_pin
from app.main import app
from app.models import User
from app.routers import auth_cliente, entregas_b2b

app.include_router(auth_cliente.router)
app.include_router(entregas_b2b.clientes_router)


def _admin(client, db):
    """Idempotente: varias altas en un mismo test comparten el admin."""
    if not db.query(User).filter(User.name == "Admin").first():
        db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
        db.commit()
    return client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]


def _crear(client, db, email, nombre="Juan", telefono=None):
    """Alta por el endpoint real. Devuelve la respuesta tal cual, para que
    quien quiera comprobar un 409 pueda hacerlo."""
    return client.post(
        "/api/clientes-b2b",
        json={"nombre": nombre, "email": email, "telefono": telefono},
        headers={"Authorization": f"Bearer {_admin(client, db)}"},
    )


def _alta(client, db, email, nombre="Juan", password="secreto123", telefono=None):
    """Crea el cliente y le pone contrasena, que es lo que hace el enlace del
    correo. El flujo completo tiene sus propios tests en
    test_acceso_cliente.py; aca solo hace falta alguien con quien entrar."""
    from app.auth_cliente import hash_password
    from app.models import ClienteB2B

    res = _crear(client, db, email, nombre, telefono)
    assert res.status_code == 201, res.text
    obj = db.query(ClienteB2B).filter(ClienteB2B.id == res.json()["id"]).first()
    obj.password_hash = hash_password(password)
    db.commit()
    return res


def test_login_cliente(client, db):
    _alta(client, db, "test@example.com")
    res = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "secreto123"
    })
    assert res.status_code == 200
    assert "token" in res.json()


def test_login_wrong_password(client, db):
    _alta(client, db, "test@example.com")
    res = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "wrong"
    })
    assert res.status_code == 401


def test_cliente_me(client, db):
    _alta(client, db, "test@example.com", nombre="Juan")
    login = client.post("/api/auth/cliente/login", json={
        "email": "test@example.com", "password": "secreto123"
    })
    token = login.json()["token"]
    res = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["nombre"] == "Juan"
    assert res.json()["email"] == "test@example.com"


def test_un_cliente_sin_contrasena_no_entra(client, db):
    """Un cliente de reparto al que nunca se invito existe, pero no tiene
    acceso al portal. Es lo que hace que el alta por invitacion funcione sin
    un campo aparte de "tiene acceso si/no"."""
    _crear(client, db, "sinacceso@test.com", nombre="Sin acceso")
    res = client.post("/api/auth/cliente/login", json={
        "email": "sinacceso@test.com", "password": "loquesea"
    })
    assert res.status_code == 401


# ── Email sin distinguir mayusculas ───────────────────────────────────────────


def test_login_ignora_mayusculas(client, db):
    """El teclado del movil capitaliza la primera letra: un cliente dado de
    alta como Lisetteolula@gmail.com no podia entrar escribiendo
    lisetteolula@..."""
    _alta(client, db, "Lisetteolula@gmail.com", nombre="Lisette")

    for intento in ("lisetteolula@gmail.com", "LISETTEOLULA@GMAIL.COM",
                    "Lisetteolula@Gmail.com", "  lisetteolula@gmail.com  "):
        res = client.post("/api/auth/cliente/login",
                          json={"email": intento, "password": "secreto123"})
        assert res.status_code == 200, f"fallo con {intento!r}: {res.text}"
        assert res.json()["token"]


def test_el_alta_guarda_el_email_normalizado(client, db):
    _alta(client, db, "  Lisetteolula@Gmail.com  ", nombre="Lisette")
    login = client.post("/api/auth/cliente/login", json={
        "email": "lisetteolula@gmail.com", "password": "secreto123"
    })
    me = client.get("/api/auth/cliente/me",
                    headers={"Authorization": f"Bearer {login.json()['token']}"})
    assert me.json()["email"] == "lisetteolula@gmail.com"


def test_no_se_puede_duplicar_cambiando_mayusculas(client, db):
    """Dos filas con el mismo email en distinta caja serian el MISMO login:
    el `.first()` del login elegiria una al azar. La unicidad de la columna no
    lo evita porque en Postgres distingue mayusculas."""
    _alta(client, db, "lisette@gmail.com", nombre="A")
    res = _crear(client, db, "Lisette@Gmail.com", nombre="B")
    assert res.status_code == 409


def test_password_sigue_distinguiendo_mayusculas(client, db):
    """Normalizar el email no debe aflojar la contrasena."""
    _alta(client, db, "test2@example.com", password="Secreto123")
    res = client.post("/api/auth/cliente/login",
                      json={"email": "test2@example.com", "password": "secreto123"})
    assert res.status_code == 401
