from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.secretos import get_secret_key
from app.models import User

SECRET_KEY = get_secret_key()
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    return bcrypt.checkpw(pin.encode(), hashed.encode())


def create_token(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

    # Los dos tipos de token se firman con la MISMA clave, asi que uno de
    # cliente decodifica aqui perfectamente: solo le falta `user_id`. Con un
    # `payload["user_id"]` directo eso era un KeyError, o sea un 500 en
    # cualquier endpoint de empleado al que llegara un token de cliente.
    # Salio a la luz al aceptar ambas credenciales en /api/catalogo.
    user_id = payload.get("user_id")
    if user_id is None or payload.get("type") == "cliente":
        raise HTTPException(status_code=401, detail="Token de tipo incorrecto")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador")
    return user
