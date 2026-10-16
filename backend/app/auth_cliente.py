from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.secretos import get_secret_key
from app.models import ClienteB2B

SECRET_KEY = get_secret_key()
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_cliente_token(cliente_id: int) -> str:
    payload = {
        "cliente_id": cliente_id,
        "type": "cliente",
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_cliente(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> ClienteB2B:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    if payload.get("type") != "cliente":
        raise HTTPException(status_code=401, detail="Token de tipo incorrecto")

    cliente = db.query(ClienteB2B).filter(ClienteB2B.id == payload["cliente_id"]).first()
    if not cliente or not cliente.is_active:
        raise HTTPException(status_code=401, detail="Cliente no encontrado")
    return cliente


def get_cliente_aprobado(
    cliente: ClienteB2B = Depends(get_current_cliente),
) -> ClienteB2B:
    """Como get_current_cliente pero ademas exige el alta completa.

    Va en todo lo que enseñe precios o mueva un pedido. Deja fuera a
    `/me` y a la verificacion, que son justo lo que un cliente pendiente
    necesita poder usar.

    403 y no 401: la sesion es valida y no hay que echarlo al login -- el
    cliente de API del portal redirige en 401 y lo sacaria de una pantalla
    que tiene derecho a ver.
    """
    if not cliente.email_verificado_at:
        raise HTTPException(
            status_code=403,
            detail="Confirma tu correo para poder pedir. Te enviamos un enlace al registrarte.",
        )
    if not cliente.aprobado_at:
        raise HTTPException(
            status_code=403,
            detail="Tu cuenta esta pendiente de aprobacion. Te avisamos en cuanto este lista.",
        )
    return cliente
