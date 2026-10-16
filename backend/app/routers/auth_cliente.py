from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth_cliente import create_cliente_token, get_current_cliente, hash_password, verify_password
from app.database import get_db
from app.models import ClienteB2B
from app.schemas import (
    CambiarPassword,
    ClienteLogin,
    ClienteOut,
    ClienteRegistro,
    EstablecerPassword,
    RecuperarPassword,
    TokenResponse,
)
from app.services.acceso_cliente import consumir_token, enviar_recuperacion

router = APIRouter(prefix="/api/auth/cliente", tags=["auth-cliente"])


def normalizar_email(email: str) -> str:
    """Emails are case-insensitive in practice, and phone keyboards capitalise the
    first letter by default. A customer registered as "Lisetteolula@gmail.com"
    could not log in typing "lisetteolula@gmail.com" -- the lookup was an exact
    `==`. Both sides get trimmed and lowercased now; stored emails are written
    normalised so the comparison stays cheap and any future exact match is safe.
    """
    return email.strip().lower()


@router.post("/registro", status_code=410)
def registrar(data: ClienteRegistro, db: Session = Depends(get_db)):
    """Cerrado desde el 2026-10-16: el alta es por invitacion.

    Permitia que cualquiera con el enlace se creara una cuenta y viera el
    catalogo con los precios B2B. Los clientes son conocidos y pocos, asi que
    ahora los da de alta Felipe desde el panel y al cliente le llega un correo
    para poner su contrasena (POST /api/clientes-b2b/{id}/invitar).

    Se deja la ruta devolviendo 410 en vez de borrarla para que un frontend
    viejo o un enlace guardado reciba un mensaje claro y no un 404 confuso.
    """
    raise HTTPException(
        status_code=410,
        detail="El registro es por invitacion. Pedinos acceso y te llega un correo.",
    )


@router.post("/login", response_model=TokenResponse)
def login(data: ClienteLogin, db: Session = Depends(get_db)):
    cliente = (
        db.query(ClienteB2B)
        .filter(
            func.lower(func.trim(ClienteB2B.email)) == normalizar_email(data.email),
            ClienteB2B.is_active == True,
            ClienteB2B.password_hash.isnot(None),
        )
        .first()
    )
    if not cliente or not verify_password(data.password, cliente.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"token": create_cliente_token(cliente.id)}


@router.get("/me", response_model=ClienteOut)
def me(cliente: ClienteB2B = Depends(get_current_cliente)):
    return ClienteOut(
        id=cliente.id,
        email=cliente.email or "",
        nombre=cliente.nombre,
        telefono=cliente.telefono,
        direccion=cliente.direccion,
    )


@router.post("/recuperar", status_code=202)
def recuperar(data: RecuperarPassword, db: Session = Depends(get_db)):
    """Manda el enlace de recuperacion. Siempre responde lo mismo.

    Exista el correo o no, este o desactivado, tenga contrasena o no: la
    respuesta es identica. Si distinguiera, cualquiera podria averiguar
    quienes son los clientes de BROT probando direcciones.
    """
    cliente = (
        db.query(ClienteB2B)
        .filter(
            func.lower(func.trim(ClienteB2B.email)) == normalizar_email(data.email),
            ClienteB2B.is_active == True,
        )
        .first()
    )
    if cliente and cliente.email:
        enviar_recuperacion(db, cliente)
        db.commit()
    return {"ok": True}


@router.post("/establecer", response_model=TokenResponse)
def establecer_password(data: EstablecerPassword, db: Session = Depends(get_db)):
    """Canjea el token del correo por una contrasena nueva.

    Sirve igual para el alta y para la recuperacion. Devuelve un token de
    sesion para que el cliente entre directo sin volver a escribir el correo.
    """
    cliente = consumir_token(db, data.token)
    if not cliente:
        raise HTTPException(
            status_code=400,
            detail="El enlace no es valido o ya se uso. Pedi uno nuevo.",
        )
    cliente.password_hash = hash_password(data.password)
    db.commit()
    return {"token": create_cliente_token(cliente.id)}


@router.post("/cambiar-password", status_code=204)
def cambiar_password(
    data: CambiarPassword,
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    """Cambio desde dentro del portal, con la contrasena actual.

    Pedir la actual importa aunque ya este logueado: si alguien deja la sesion
    abierta en un movil, sin esto cualquiera que lo agarre le cambia la
    contrasena y lo deja fuera de su propia cuenta.
    """
    if not cliente.password_hash or not verify_password(data.actual, cliente.password_hash):
        raise HTTPException(status_code=401, detail="La contrasena actual no es correcta")
    cliente.password_hash = hash_password(data.nueva)
    db.commit()
