"""`GET /api/diagnostico/correo` — que configuracion de correo ve el servidor.

Lo que importa de este endpoint es que diga la VERDAD sobre lo que el proceso
tiene cargado: existe justamente para distinguir "la variable esta mal puesta"
de "el correo se manda y no llega", que desde fuera se ven igual. Si informara
de mas o de menos no serviria para nada.
"""

from app.main import app
from app.auth import hash_pin
from app.models import User


def _login(client, db, role="admin"):
    user = User(name=f"User-{role}", pin_hash=hash_pin("1234"), role=role)
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": f"User-{role}", "pin": "1234"})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _pedir(client, token):
    return client.get("/api/diagnostico/correo", headers={"Authorization": f"Bearer {token}"})


def test_dice_a_quien_se_avisa_de_los_pedidos(client, db, monkeypatch):
    monkeypatch.setenv("EMAIL_PANADERO", "panadero@example.com")
    token = _login(client, db)

    avisos = _pedir(client, token).json()["avisos_de_pedido"]
    assert avisos["configurada"] is True
    assert avisos["destinos"] == ["panadero@example.com"]
    assert "panadero@example.com" in avisos["estado"]


def test_muestra_los_destinos_ya_limpios(client, db, monkeypatch):
    """Un espacio de mas al pegar la direccion en Render es justo uno de los
    errores que este endpoint tiene que poder descartar, asi que informa lo que
    `destinos_panadero()` parsea y no el texto crudo de la variable."""
    monkeypatch.setenv("EMAIL_PANADERO", "  uno@example.com ,dos@example.com  ")
    token = _login(client, db)

    assert _pedir(client, token).json()["avisos_de_pedido"]["destinos"] == [
        "uno@example.com", "dos@example.com",
    ]


def test_sin_configurar_lo_dice_claro(client, db, monkeypatch):
    monkeypatch.delenv("EMAIL_PANADERO", raising=False)
    token = _login(client, db)

    avisos = _pedir(client, token).json()["avisos_de_pedido"]
    assert avisos["configurada"] is False
    assert avisos["destinos"] == []
    assert "Sin configurar" in avisos["estado"]
    # Y nombra la variable que hay que poner, que es la mitad de la respuesta.
    assert avisos["variable"] == "EMAIL_PANADERO"


def test_nunca_devuelve_la_contrasena_de_smtp(client, db, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "brot@example.com")
    token = _login(client, db)

    res = _pedir(client, token)
    crudo = res.text
    assert "abcd" not in crudo and "mnop" not in crudo
    # Solo si esta puesta, nunca su valor ni un trozo.
    assert res.json()["smtp_password_puesta"] is True
    assert res.json()["smtp_configurado"] is True


def test_solo_admin(client, db):
    """Dice a quien se le avisa de los pedidos: es configuracion del negocio."""
    assert _pedir(client, _login(client, db, "staff")).status_code == 403
    assert client.get("/api/diagnostico/correo").status_code == 401
