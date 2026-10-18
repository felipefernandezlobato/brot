"""Que configuracion de correo ve el servidor, de verdad.

Existe por una pregunta concreta y repetible: "puse la variable en Render,
¿quedo bien?". Desde fuera no hay forma de saberlo — si el nombre de la
variable tiene una letra de mas, si la direccion se pego con un espacio al
final, o si el servicio no reinicio y sigue corriendo con la configuracion
vieja, el sintoma es el mismo en los tres casos: no llega ningun correo y no
pasa nada visible. Una captura del panel de Render tampoco lo aclara, porque
muestra lo que esta escrito ahi y no lo que el proceso tiene cargado.

Asi que esto devuelve lo que el proceso ve AHORA, ya parseado por el mismo
codigo que manda los correos (`destinos_panadero()`), no una copia de la
lectura. Si aca aparece la direccion correcta, el aviso va a salir.

**No manda ningun correo.** Es solo lectura, a proposito: un boton de "probar
envio" le mandaria un correo de prueba a una persona real cada vez que alguien
con dudas lo aprieta.

Admin only: dice a quien se le avisa de los pedidos, que es informacion de
configuracion del negocio. Nunca devuelve la contrasena de SMTP ni parte de
ella.
"""

import os

from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.models import User
from app.services.avisos_pedido import destinos_panadero
from app.services.email import app_url, configurado

router = APIRouter(prefix="/api/diagnostico", tags=["diagnostico"])


@router.get("/correo")
def diagnostico_correo(_admin: User = Depends(require_admin)):
    destinos = destinos_panadero()
    return {
        # Si esto es False no sale NINGUN correo, ni el aviso de pedidos ni los
        # de alta y recuperacion de contrasena.
        "smtp_configurado": configurado(),
        "smtp_host": os.getenv("SMTP_HOST") or None,
        "smtp_usuario": os.getenv("SMTP_USER") or None,
        # La contrasena no se devuelve nunca, ni enmascarada: solo si esta.
        "smtp_password_puesta": bool(os.getenv("SMTP_PASSWORD")),
        "email_desde": os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER") or None,
        "app_url": app_url(),
        # Tal como las parsea el codigo que manda el aviso. Si la variable trae
        # un espacio de mas, aca se ve ya limpio -- lo que importa es que la
        # direccion este bien escrita y que la lista no venga vacia.
        "avisos_de_pedido": {
            "variable": "EMAIL_PANADERO",
            "configurada": bool(destinos),
            "destinos": destinos,
            "estado": (
                "Se avisa a " + ", ".join(destinos) if destinos
                else "Sin configurar: no se avisa a nadie de los pedidos nuevos"
            ),
        },
    }
