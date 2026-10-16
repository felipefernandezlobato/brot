from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
    VerificarEmail,
)
from app.services.acceso_cliente import (
    avisar_alta_a_brot,
    consumir_token,
    crear_token,
    enviar_email_verificacion,
    enviar_recuperacion,
    enviar_verificacion,
)

router = APIRouter(prefix="/api/auth/cliente", tags=["auth-cliente"])


def normalizar_email(email: str) -> str:
    """Emails are case-insensitive in practice, and phone keyboards capitalise the
    first letter by default. A customer registered as "Lisetteolula@gmail.com"
    could not log in typing "lisetteolula@gmail.com" -- the lookup was an exact
    `==`. Both sides get trimmed and lowercased now; stored emails are written
    normalised so the comparison stays cheap and any future exact match is safe.
    """
    return email.strip().lower()


@router.post("/registro", response_model=TokenResponse, status_code=201)
def registrar(
    data: ClienteRegistro,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Alta propia. Queda pendiente de dos cosas antes de poder pedir:
    que el cliente confirme su correo y que BROT lo apruebe.

    Estuvo cerrada unas horas el 2026-10-16 (solo invitacion) y se reabrio el
    mismo dia: con invitacion, cada cliente nuevo era trabajo manual de
    Felipe. El riesgo que motivo cerrarla -- que cualquiera viera el catalogo
    con precios B2B -- se resuelve ahora en el otro extremo: sin aprobar no
    hay catalogo (ver `cliente_aprobado` en auth_cliente.py).

    Devuelve sesion iniciada a proposito: el cliente entra y ve en que estado
    esta su alta, en vez de registrarse y quedarse mirando un login.
    """
    email = normalizar_email(data.email)
    if db.query(ClienteB2B).filter(func.lower(func.trim(ClienteB2B.email)) == email).first():
        raise HTTPException(status_code=409, detail="Ya hay una cuenta con ese correo")

    cliente = ClienteB2B(
        email=email,
        password_hash=hash_password(data.password),
        nombre=data.nombre.strip(),
        telefono=data.telefono,
        direccion=data.direccion,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        # Las dos puertas quedan cerradas: las abre el cliente (verificando)
        # y Felipe (aprobando), cada uno la suya.
        email_verificado_at=None,
        aprobado_at=None,
    )
    db.add(cliente)
    db.flush()

    # El token se crea YA (necesita la sesion y la fila del cliente), pero el
    # correo se manda despues de responder. Mandarlo dentro dejaba la pantalla
    # en "Creando cuenta..." mientras Gmail contestaba DOS veces, con 20s de
    # margen cada una: el cliente veia el boton colgado y volvia a pulsarlo.
    # Un envio de correo no puede bloquear una pantalla.
    token = crear_token(db, cliente, "verificacion")
    db.commit()

    tareas.add_task(enviar_email_verificacion, cliente.email, cliente.nombre, token)
    tareas.add_task(
        avisar_alta_a_brot,
        cliente.nombre, cliente.email, cliente.telefono, cliente.direccion,
    )
    return {"token": create_cliente_token(cliente.id)}


@router.post("/verificar", status_code=204)
def verificar_email(data: VerificarEmail, db: Session = Depends(get_db)):
    """Canjea el enlace del correo de alta."""
    cliente = consumir_token(db, data.token)
    if not cliente:
        raise HTTPException(
            status_code=400, detail="El enlace no es valido o ya se uso. Pedi uno nuevo."
        )
    if not cliente.email_verificado_at:
        cliente.email_verificado_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


@router.post("/reenviar-verificacion", status_code=202)
def reenviar_verificacion(
    cliente: ClienteB2B = Depends(get_current_cliente),
    db: Session = Depends(get_db),
):
    """Para el cliente que ya entro y se le vencio el enlace de verificacion."""
    if cliente.email_verificado_at:
        return {"ok": True}
    enviado = enviar_verificacion(db, cliente)
    db.commit()
    return {"enviado": enviado}


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
        email_verificado=bool(cliente.email_verificado_at),
        aprobado=bool(cliente.aprobado_at),
        puede_pedir=cliente.puede_pedir,
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
    # 422 y no 401 a proposito: la peticion SI esta autenticada, lo que esta
    # mal es un campo del formulario. Con un 401 el cliente de API del portal
    # borra el token y manda al login, asi que equivocarse al teclear la
    # contrasena actual te echaba de la sesion en vez de avisarte.
    if not cliente.password_hash or not verify_password(data.actual, cliente.password_hash):
        raise HTTPException(status_code=422, detail="La contrasena actual no es correcta")
    cliente.password_hash = hash_password(data.nueva)
    db.commit()
