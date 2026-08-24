from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, hash_pin, require_admin, verify_pin
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    return [{"id": u.id, "name": u.name} for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if not data.pin.isdigit() or len(data.pin) != 4:
        raise HTTPException(status_code=400, detail="El PIN debe tener exactamente 4 dígitos")
    if data.role not in ("admin", "staff"):
        raise HTTPException(status_code=400, detail="Rol inválido")

    existing = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    if any(u.name.strip().lower() == name.lower() for u in existing):
        raise HTTPException(status_code=400, detail="Ya existe un usuario activo con ese nombre")

    user = User(name=name, pin_hash=hash_pin(data.pin), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "role": user.role}


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.name, User.is_active == True).first()  # noqa: E712
    if not user or not verify_pin(data.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"token": create_token(user.id, user.role)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "role": user.role}
