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
    except Exception:
        # Sin exc_info completo en el log: un traceback de smtplib puede incluir
        # la linea de login y no queremos la contrasena en los logs de Render.
        logger.error("Fallo el envio de '%s' a %s", asunto, destino)
        return False
