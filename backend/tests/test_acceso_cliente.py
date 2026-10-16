"""Alta por invitacion y recuperacion de contrasena del portal de clientes.

El alta abierta se cerro el 2026-10-16: ahora Felipe da de alta al cliente y
le llega un correo con un enlace de un solo uso para poner su contrasena. El
mismo mecanismo sirve para "olvide mi contrasena".

Los tests no mandan correo de verdad -- SMTP no esta configurado en el
entorno de test, asi que `enviar_email` devuelve False sin tocar la red -- y
leen el token de la base, que es lo unico que el correo llevaria.
"""

from datetime import datetime, timedelta, timezone

from app.auth import hash_pin
from app.auth_cliente import hash_password
from app.main import app
from app.models import ClienteB2B, Permission, TokenAccesoCliente, User
from app.routers import auth_cliente, entregas_b2b

app.include_router(auth_cliente.router)
app.include_router(entregas_b2b.clientes_router)


def _admin(client, db):
    db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
    db.commit()
    return client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]


def _cliente(db, email="olula@test.com", nombre="Olula", password=None, activo=True):
    c = ClienteB2B(
        nombre=nombre,
        email=email,
        is_active=activo,
        password_hash=hash_password(password) if password else None,
    )
    db.add(c)
    db.commit()
    return c


def _token_de(db, cliente_id):
    """El token en claro solo existe en el correo; en la base esta su hash.
    Los tests lo recuperan parcheando la generacion."""
    fila = (
        db.query(TokenAccesoCliente)
        .filter(TokenAccesoCliente.cliente_b2b_id == cliente_id)
        .order_by(TokenAccesoCliente.id.desc())
        .first()
    )
    return fila


# ---------------------------------------------------------------- alta


def test_invitar_crea_un_token_de_alta(client, db, monkeypatch):
    capturado = {}
    monkeypatch.setattr(
        "app.services.acceso_cliente.enviar_email",
        lambda destino, asunto, cuerpo: capturado.update(destino=destino, cuerpo=cuerpo) or True,
    )
    tok = _admin(client, db)
    c = _cliente(db)

    res = client.post(f"/api/clientes-b2b/{c.id}/invitar", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 200, res.text
    assert res.json() == {"enviado": True, "email": "olula@test.com"}

    fila = _token_de(db, c.id)
    assert fila is not None and fila.tipo == "alta" and fila.usado_at is None
    # El enlace del correo lleva el token en claro; la base solo su hash.
    assert "/cliente/establecer?token=" in capturado["cuerpo"]
    assert fila.token_hash not in capturado["cuerpo"]


def test_invitar_sin_email_no_se_puede(client, db):
    tok = _admin(client, db)
    c = _cliente(db, email=None)
    res = client.post(f"/api/clientes-b2b/{c.id}/invitar", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 422


def test_invitar_avisa_cuando_el_correo_no_sale(client, db, monkeypatch):
    """Sin SMTP configurado el alta no revienta, pero tiene que decir que no
    se envio -- si no, Felipe cree que el cliente recibio algo."""
    monkeypatch.setattr("app.services.acceso_cliente.enviar_email", lambda *a: False)
    tok = _admin(client, db)
    c = _cliente(db)
    res = client.post(f"/api/clientes-b2b/{c.id}/invitar", headers={"Authorization": f"Bearer {tok}"})
    assert res.status_code == 200
    assert res.json()["enviado"] is False


# ---------------------------------------------------- canje del token


def _invitar_y_sacar_token(client, db, monkeypatch, cliente):
    enlaces = []
    monkeypatch.setattr(
        "app.services.acceso_cliente.enviar_email",
        lambda destino, asunto, cuerpo: enlaces.append(cuerpo) or True,
    )
    tok = _admin(client, db)
    client.post(f"/api/clientes-b2b/{cliente.id}/invitar", headers={"Authorization": f"Bearer {tok}"})
    cuerpo = enlaces[-1]
    return cuerpo.split("token=")[1].split()[0]


def test_establecer_password_y_entrar(client, db, monkeypatch):
    c = _cliente(db)
    token = _invitar_y_sacar_token(client, db, monkeypatch, c)

    res = client.post("/api/auth/cliente/establecer", json={"token": token, "password": "miclave123"})
    assert res.status_code == 200, res.text
    assert res.json()["token"]  # entra directo, sin volver a escribir el correo

    login = client.post("/api/auth/cliente/login", json={"email": c.email, "password": "miclave123"})
    assert login.status_code == 200


def test_el_token_es_de_un_solo_uso(client, db, monkeypatch):
    c = _cliente(db)
    token = _invitar_y_sacar_token(client, db, monkeypatch, c)
    assert client.post("/api/auth/cliente/establecer", json={"token": token, "password": "clave12345"}).status_code == 200
    segundo = client.post("/api/auth/cliente/establecer", json={"token": token, "password": "otraclave99"})
    assert segundo.status_code == 400


def test_un_token_vencido_no_sirve(client, db, monkeypatch):
    c = _cliente(db)
    token = _invitar_y_sacar_token(client, db, monkeypatch, c)
    fila = _token_de(db, c.id)
    fila.expira_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db.commit()

    res = client.post("/api/auth/cliente/establecer", json={"token": token, "password": "clave12345"})
    assert res.status_code == 400


def test_pedir_otro_enlace_mata_el_anterior(client, db, monkeypatch):
    c = _cliente(db)
    primero = _invitar_y_sacar_token(client, db, monkeypatch, c)
    segundo = _invitar_y_sacar_token(client, db, monkeypatch, c)
    assert primero != segundo
    assert client.post("/api/auth/cliente/establecer", json={"token": primero, "password": "clave12345"}).status_code == 400
    assert client.post("/api/auth/cliente/establecer", json={"token": segundo, "password": "clave12345"}).status_code == 200


def test_password_corta_se_rechaza(client, db, monkeypatch):
    c = _cliente(db)
    token = _invitar_y_sacar_token(client, db, monkeypatch, c)
    assert client.post("/api/auth/cliente/establecer", json={"token": token, "password": "corta"}).status_code == 422


# ------------------------------------------------------- recuperacion


def test_recuperar_no_revela_si_el_correo_existe(client, db, monkeypatch):
    """La respuesta tiene que ser identica exista o no, o cualquiera puede
    averiguar quienes son los clientes de BROT probando direcciones."""
    monkeypatch.setattr("app.services.acceso_cliente.enviar_email", lambda *a: True)
    _cliente(db, email="existe@test.com")

    a = client.post("/api/auth/cliente/recuperar", json={"email": "existe@test.com"})
    b = client.post("/api/auth/cliente/recuperar", json={"email": "noexiste@test.com"})
    assert a.status_code == b.status_code == 202
    assert a.json() == b.json()
    # pero solo se creo token para el que existe
    assert db.query(TokenAccesoCliente).count() == 1


def test_recuperar_y_cambiar(client, db, monkeypatch):
    cuerpos = []
    monkeypatch.setattr(
        "app.services.acceso_cliente.enviar_email",
        lambda destino, asunto, cuerpo: cuerpos.append(cuerpo) or True,
    )
    c = _cliente(db, password="vieja12345")
    client.post("/api/auth/cliente/recuperar", json={"email": c.email})
    token = cuerpos[-1].split("token=")[1].split()[0]

    assert client.post("/api/auth/cliente/establecer", json={"token": token, "password": "nueva12345"}).status_code == 200
    assert client.post("/api/auth/cliente/login", json={"email": c.email, "password": "nueva12345"}).status_code == 200
    assert client.post("/api/auth/cliente/login", json={"email": c.email, "password": "vieja12345"}).status_code == 401


def test_un_cliente_desactivado_no_recibe_enlace(client, db, monkeypatch):
    monkeypatch.setattr("app.services.acceso_cliente.enviar_email", lambda *a: True)
    _cliente(db, email="baja@test.com", activo=False)
    res = client.post("/api/auth/cliente/recuperar", json={"email": "baja@test.com"})
    assert res.status_code == 202
    assert db.query(TokenAccesoCliente).count() == 0


# --------------------------------------------- cambio desde el portal


def test_cambiar_password_desde_dentro(client, db):
    c = _cliente(db, password="actual12345")
    tok = client.post("/api/auth/cliente/login", json={"email": c.email, "password": "actual12345"}).json()["token"]

    res = client.post(
        "/api/auth/cliente/cambiar-password",
        json={"actual": "actual12345", "nueva": "flamante123"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert res.status_code == 204
    assert client.post("/api/auth/cliente/login", json={"email": c.email, "password": "flamante123"}).status_code == 200


def test_cambiar_password_exige_la_actual(client, db):
    """Una sesion abierta en un movil ajeno no debe bastar para dejar al
    cliente fuera de su propia cuenta."""
    c = _cliente(db, password="actual12345")
    tok = client.post("/api/auth/cliente/login", json={"email": c.email, "password": "actual12345"}).json()["token"]

    res = client.post(
        "/api/auth/cliente/cambiar-password",
        json={"actual": "me-la-invento", "nueva": "flamante123"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    # 422 y no 401: la sesion es valida, lo que falla es el campo. Con un 401
    # el cliente de API del portal lo echaria al login por teclear mal.
    assert res.status_code == 422
    assert client.post("/api/auth/cliente/login", json={"email": c.email, "password": "actual12345"}).status_code == 200


def test_cambiar_password_requiere_sesion(client, db):
    assert client.post(
        "/api/auth/cliente/cambiar-password", json={"actual": "x", "nueva": "flamante123"}
    ).status_code in (401, 403)


# ------------------------------------------------- alta propia + aprobacion


def _registrarse(client, monkeypatch, email="nuevo@test.com", nombre="Panaderia Nueva"):
    """Devuelve (token de sesion, lista de cuerpos de correo enviados)."""
    correos = []
    monkeypatch.setattr(
        "app.services.acceso_cliente.enviar_email",
        lambda destino, asunto, cuerpo: correos.append((destino, asunto, cuerpo)) or True,
    )
    res = client.post("/api/auth/cliente/registro", json={
        "email": email, "password": "miclave123", "nombre": nombre,
        "telefono": "+54 9 260 400 0846", "direccion": "San Martin 100",
    })
    assert res.status_code == 201, res.text
    return res.json()["token"], correos


def test_registrarse_deja_la_cuenta_pendiente(client, db, monkeypatch):
    tok, correos = _registrarse(client, monkeypatch)
    c = db.query(ClienteB2B).filter(ClienteB2B.email == "nuevo@test.com").first()
    assert c is not None
    assert c.email_verificado_at is None
    assert c.aprobado_at is None
    assert c.telefono and c.direccion  # el alta recoge sus datos, no los pone Felipe

    me = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["email_verificado"] is False
    assert me["aprobado"] is False
    assert me["puede_pedir"] is False


def test_el_alta_avisa_al_cliente_y_a_brot(client, db, monkeypatch, ):
    monkeypatch.setenv("SMTP_USER", "brotlapanaderia@gmail.com")
    _tok, correos = _registrarse(client, monkeypatch)
    destinos = [d for d, _a, _c in correos]
    assert "nuevo@test.com" in destinos, "el cliente tiene que recibir su enlace"
    assert "brotlapanaderia@gmail.com" in destinos, "BROT tiene que enterarse de que hay alguien esperando"


def test_el_email_se_normaliza_tambien_en_el_alta_propia(client, db, monkeypatch):
    _registrarse(client, monkeypatch, email="  Nuevo@Test.com  ")
    c = db.query(ClienteB2B).first()
    assert c.email == "nuevo@test.com"


def test_no_se_puede_registrar_dos_veces_el_mismo_correo(client, db, monkeypatch):
    _registrarse(client, monkeypatch, email="repe@test.com")
    monkeypatch.setattr("app.services.acceso_cliente.enviar_email", lambda *a: True)
    res = client.post("/api/auth/cliente/registro", json={
        "email": "REPE@test.com", "password": "otraclave1", "nombre": "Impostor",
    })
    assert res.status_code == 409


def test_un_pendiente_no_puede_pedir(client, db, monkeypatch):
    tok, _ = _registrarse(client, monkeypatch)
    res = client.post(
        "/api/cliente/pedidos",
        json={"fecha_entrega": "2026-10-21", "lineas": [{"producto_id": 1, "cantidad": 1}]},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert res.status_code == 403


def test_verificar_el_correo_no_alcanza_para_pedir(client, db, monkeypatch):
    """Son dos puertas distintas: verificar es cosa del cliente, aprobar es
    cosa de BROT."""
    tok, correos = _registrarse(client, monkeypatch)
    enlace = [c for _d, _a, c in correos if "verificar?token=" in c][0]
    token = enlace.split("verificar?token=")[1].split()[0]

    assert client.post("/api/auth/cliente/verificar", json={"token": token}).status_code == 204
    me = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["email_verificado"] is True
    assert me["puede_pedir"] is False  # falta la aprobacion


def test_no_se_puede_aprobar_a_quien_no_verifico(client, db, monkeypatch):
    """Aprobar un correo que no existe da acceso a una cuenta irrecuperable."""
    _registrarse(client, monkeypatch)
    c = db.query(ClienteB2B).first()
    admin = _admin(client, db)
    res = client.post(f"/api/clientes-b2b/{c.id}/aprobar", headers={"Authorization": f"Bearer {admin}"})
    assert res.status_code == 409


def test_el_circuito_completo(client, db, monkeypatch):
    tok, correos = _registrarse(client, monkeypatch)
    token = [c for _d, _a, c in correos if "verificar?token=" in c][0].split("verificar?token=")[1].split()[0]
    client.post("/api/auth/cliente/verificar", json={"token": token})

    c = db.query(ClienteB2B).first()
    admin = _admin(client, db)
    monkeypatch.setattr("app.routers.entregas_b2b.enviar_email", lambda *a: True)
    res = client.post(f"/api/clientes-b2b/{c.id}/aprobar", headers={"Authorization": f"Bearer {admin}"})
    assert res.status_code == 200 and res.json()["aprobado"] is True

    me = client.get("/api/auth/cliente/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["puede_pedir"] is True
    assert client.get("/api/catalogo", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_rechazar_desactiva_sin_borrar(client, db, monkeypatch):
    """Borrarlo dejaria el correo libre para que un tercero se registre con el."""
    _registrarse(client, monkeypatch)
    c = db.query(ClienteB2B).first()
    admin = _admin(client, db)
    assert client.post(f"/api/clientes-b2b/{c.id}/rechazar",
                       headers={"Authorization": f"Bearer {admin}"}).status_code == 200
    db.refresh(c)
    assert c.is_active is False
    assert db.query(ClienteB2B).filter(ClienteB2B.email == c.email).first() is not None


def test_un_cliente_que_crea_felipe_nace_aprobado(client, db):
    """Darlo de alta el mismo ya es aprobarlo: no tiene sentido que tenga que
    aprobar a alguien que acaba de escribir con sus propias manos."""
    admin = _admin(client, db)
    res = client.post("/api/clientes-b2b", json={"nombre": "A mano", "email": "amano@test.com"},
                      headers={"Authorization": f"Bearer {admin}"})
    assert res.status_code == 201
    assert res.json()["aprobado"] is True
    assert res.json()["email_verificado"] is True
