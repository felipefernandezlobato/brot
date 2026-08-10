from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, verify_pin
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    return [{"id": u.id, "name": u.name} for u in users]


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.name, User.is_active == True).first()  # noqa: E712
    if not user or not verify_pin(data.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"token": create_token(user.id, user.role)}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "role": user.role}
