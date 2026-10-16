"""Envio de correo por SMTP.

Unico lugar del sistema que manda emails. Se configura por variables de
entorno; el repo es publico, asi que nada de esto puede ir escrito en codigo:

    SMTP_HOST       smtp.gmail.com
    SMTP_PORT       587
    SMTP_USER       brotlapanaderia@gmail.com
    SMTP_PASSWORD   la contrasena de aplicacion de Google (NO la del correo)
    EMAIL_FROM      "BROT La Panaderia <brotlapanaderia@gmail.com>"  (opcional)
    APP_URL         https://brot-bruteam.vercel.app  (para armar los enlaces)

**Sin configurar, no falla: no envia y devuelve False.** Es deliberado. En
local y en los tests no hay SMTP, y un alta de cliente no puede reventar con
un 500 por eso. Quien llame decide que hacer con el False; lo que NO debe
hacer es tragarselo en silencio de cara al usuario -- si la invitacion no
sale, Felipe tiene que enterarse en la pantalla, no descubrirlo cuando el
cliente le diga que nunca le llego.

Gmail aguanta ~500 envios diarios, de sobra para invitaciones y
recuperaciones de contrasena de un puñado de clientes B2B.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def configurado() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def app_url() -> str:
    return (os.getenv("APP_URL") or "https://brot-bruteam.vercel.app").rstrip("/")


def enviar_email(destino: str, asunto: str, cuerpo: str) -> bool:
    """Devuelve True si el correo salio. Nunca lanza: un fallo de SMTP no debe
    tumbar la peticion que lo origino."""
    if not configurado():
        logger.warning("SMTP sin configurar: no se envio '%s' a %s", asunto, destino)
        return False

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = os.getenv("EMAIL_FROM") or os.environ["SMTP_USER"]
    msg["To"] = destino
    msg.set_content(cuerpo)

    try:
        host = os.environ["SMTP_HOST"]
        puerto = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, puerto, timeout=20) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
        return True
    except Exception as e:
        # Sin `exc_info=True` a proposito: un traceback con locals podria
        # arrastrar la contrasena a los logs de Render. Pero el TIPO y el
        # mensaje de la excepcion si hacen falta -- sin ellos, un fallo de
        # envio es indistinguible de otro y no hay por donde empezar
        # (paso el 2026-10-16: no llegaba ningun correo y el log solo decia
        # "fallo"). smtplib pone el motivo en el mensaje, no las credenciales.
        logger.error(
            "Fallo el envio de '%s' a %s -- %s: %s",
            asunto, destino, type(e).__name__, str(e)[:300],
        )
        return False
