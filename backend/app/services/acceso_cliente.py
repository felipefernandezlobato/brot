"""Alta por invitacion y recuperacion de contrasena de los clientes del portal.

Un solo mecanismo para las dos cosas: un token de un solo uso que viaja en un
enlace por correo. El alta y el "olvide mi contrasena" solo se diferencian en
el texto del mail y en cuanto dura el enlace.

**La verificacion del email sale gratis de aqui.** No hace falta un paso
aparte de "confirma tu correo": si el cliente llega a usar el enlace, es
porque el correo existe y es suyo. Dos mecanismos para lo mismo serian uno de
mas.

El cliente del portal es `ClienteB2B`, el mismo registro con el que se le
reparte -- ver el comentario en models.py donde vivia el viejo `Cliente`.
`password_hash` es nullable y el login filtra `isnot(None)`, asi que un
cliente de reparto al que nunca se invito simplemente no tiene acceso.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ClienteB2B, TokenAccesoCliente
from app.services.email import app_url, enviar_email

# El alta da margen para que Felipe avise al cliente; el reset es corto a
# proposito, que es el caso en el que un enlace filtrado hace mas dano.
DURACION = {
    "alta": timedelta(hours=48),
    "reset": timedelta(hours=1),
    # Mas largo que el alta: el cliente acaba de registrarse y puede mirar el
    # correo al dia siguiente. Si se le vence, la pantalla de "cuenta
    # pendiente" tiene un boton para reenviarlo.
    "verificacion": timedelta(days=7),
}


def _hash(token: str) -> str:
    """sha256 basta: el token es aleatorio de 256 bits, no una contrasena que
    alguien pueda adivinar por fuerza bruta o diccionario. bcrypt aqui solo
    aportaria lentitud."""
    return hashlib.sha256(token.encode()).hexdigest()


def crear_token(db: Session, cliente: ClienteB2B, tipo: str) -> str:
    """Genera el token, guarda su hash y devuelve el token en claro.

    Es la unica vez que existe en claro: de aqui va al correo y se olvida.
    Invalida los tokens anteriores del mismo tipo que siguieran vivos, para
    que pedir un enlace nuevo deje muerto el viejo.
    """
    ahora = datetime.now(timezone.utc)
    vivos = (
        db.query(TokenAccesoCliente)
        .filter(
            TokenAccesoCliente.cliente_b2b_id == cliente.id,
            TokenAccesoCliente.tipo == tipo,
            TokenAccesoCliente.usado_at.is_(None),
        )
        .all()
    )
    for t in vivos:
        t.usado_at = ahora

    token = secrets.token_urlsafe(32)
    db.add(TokenAccesoCliente(
        cliente_b2b_id=cliente.id,
        token_hash=_hash(token),
        tipo=tipo,
        expira_at=ahora.replace(tzinfo=None) + DURACION[tipo],
        created_at=ahora.replace(tzinfo=None),
    ))
    db.flush()
    return token


def consumir_token(db: Session, token: str) -> Optional[ClienteB2B]:
    """Valida y marca el token como usado. None si no sirve.

    Un unico `None` para todos los motivos -- inexistente, ya usado, caducado,
    cliente desactivado -- a proposito: la pantalla no debe ayudar a distinguir
    entre "este enlace no existe" y "este enlace ya se uso".
    """
    fila = (
        db.query(TokenAccesoCliente)
        .filter(TokenAccesoCliente.token_hash == _hash(token))
        .first()
    )
    if not fila or fila.usado_at is not None:
        return None
    if fila.expira_at < datetime.now(timezone.utc).replace(tzinfo=None):
        return None
    cliente = db.query(ClienteB2B).filter(ClienteB2B.id == fila.cliente_b2b_id).first()
    if not cliente or not cliente.is_active:
        return None

    fila.usado_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    return cliente


def _enlace(token: str) -> str:
    return f"{app_url()}/cliente/establecer?token={token}"


def enviar_invitacion(db: Session, cliente: ClienteB2B) -> bool:
    token = crear_token(db, cliente, "alta")
    return enviar_email(
        cliente.email,
        "Tu acceso al portal de BROT",
        f"""Hola {cliente.nombre},

Te damos acceso al portal de pedidos de BROT La Panaderia. Entra en este
enlace y elegi tu contrasena:

{_enlace(token)}

El enlace vale 48 horas. Si se te vence, pedinos uno nuevo y listo.

Despues vas a poder entrar en {app_url()}/cliente con tu correo
({cliente.email}) y la contrasena que elijas, ver el catalogo con tus precios
y hacer tus pedidos.

BROT La Panaderia
""",
    )


def enviar_recuperacion(db: Session, cliente: ClienteB2B) -> bool:
    token = crear_token(db, cliente, "reset")
    return enviar_email(
        cliente.email,
        "Recuperar tu contrasena de BROT",
        f"""Hola {cliente.nombre},

Pediste cambiar la contrasena de tu acceso al portal de BROT. Entra aca para
elegir una nueva:

{_enlace(token)}

El enlace vale 1 hora y se puede usar una sola vez.

Si no fuiste vos, ignora este correo: tu contrasena actual sigue funcionando y
nadie ha entrado en tu cuenta.

BROT La Panaderia
""",
    )


def enviar_email_verificacion(email: str, nombre: str, token: str) -> bool:
    """Solo el envio, sin tocar la base.

    Las tareas en segundo plano corren DESPUES de que la peticion termino y
    `get_db` cerro la sesion, asi que no pueden recibirla: usarla alli da un
    error de sesion cerrada. El token se crea en el endpoint, que si la
    tiene, y aqui solo llega el texto.
    """
    return enviar_email(
        email,
        "Confirma tu correo - BROT",
        f"""Hola {nombre},

Gracias por registrarte en el portal de pedidos de BROT La Panaderia.
Confirma que este correo es tuyo entrando aca:

{app_url()}/cliente/verificar?token={token}

Despues de confirmarlo revisamos tu alta y te avisamos en cuanto puedas
empezar a pedir.

El enlace vale 7 dias.

BROT La Panaderia
""",
    )


def enviar_verificacion(db: Session, cliente: ClienteB2B) -> bool:
    """Confirma que el correo del alta existe y es suyo.

    Con el registro abierto el email deja de estar verificado por
    construccion -- cuando el alta era por invitacion, usar el enlace ya lo
    demostraba. Ahora cualquiera puede teclear una direccion con una errata, y
    Felipe se encontraria aprobando a alguien que nunca va a recibir nada, ni
    siquiera para recuperar su contrasena.
    """
    return enviar_email_verificacion(
        cliente.email, cliente.nombre, crear_token(db, cliente, "verificacion")
    )


def avisar_alta_a_brot(nombre: str, email: str, telefono=None, direccion=None) -> bool:
    """Le avisa a BROT que hay alguien esperando aprobacion.

    Sin esto, un cliente que se registra un viernes puede quedarse esperando
    hasta que alguien entre al panel por casualidad. El contador de la
    pantalla ayuda, pero solo si alguien la mira.
    """
    destino = os.getenv("SMTP_USER")
    if not destino:
        return False
    return enviar_email(
        destino,
        f"Nuevo cliente en el portal: {nombre}",
        f"""Se registro un cliente nuevo y esta esperando tu aprobacion.

  Nombre:    {nombre}
  Correo:    {email}
  Telefono:  {telefono or "-"}
  Direccion: {direccion or "-"}

Hasta que lo apruebes no ve el catalogo ni puede pedir.

Aprobalo o rechazalo en {app_url()}/entregas/clientes
""",
    )


def avisar_password_cambiada(email: str, nombre: str) -> bool:
    """Avisa al cliente de que su contrasena acaba de cambiar.

    No bloquea nada -- quien la cambia ya sabia la anterior, asi que exigirle
    ademas confirmar por correo molestaria mucho para lo poco que anade. Lo
    que si aporta es enterarse: si el cambio no fue cosa suya, se entera en el
    momento en vez de descubrirlo el dia que no pueda entrar.
    """
    return enviar_email(
        email,
        "Tu contrasena de BROT ha cambiado",
        f"""Hola {nombre},

Te avisamos de que la contrasena de tu cuenta del portal acaba de cambiar.

Si fuiste vos, no tenes que hacer nada.

Si NO fuiste vos, entra cuanto antes en {app_url()}/cliente/recuperar para
recuperar tu cuenta, y avisanos.

BROT La Panaderia
""",
    )
