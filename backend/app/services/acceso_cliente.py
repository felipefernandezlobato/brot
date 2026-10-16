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
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ClienteB2B, TokenAccesoCliente
from app.services.email import app_url, enviar_email

# El alta da margen para que Felipe avise al cliente; el reset es corto a
# proposito, que es el caso en el que un enlace filtrado hace mas dano.
DURACION = {"alta": timedelta(hours=48), "reset": timedelta(hours=1)}


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
