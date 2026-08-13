from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_cliente import create_cliente_token, get_current_cliente, hash_password, verify_password
from app.database import get_db
from app.models import ClienteB2B
from app.schemas import ClienteLogin, ClienteOut, ClienteRegistro, TokenResponse

router = APIRouter(prefix="/api/auth/cliente", tags=["auth-cliente"])


@router.post("/registro", response_model=TokenResponse, status_code=201)
def registrar(data: ClienteRegistro, db: Session = Depends(get_db)):
    existing = db.query(ClienteB2B).filter(ClienteB2B.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ya registrado")
    cliente = ClienteB2B(
        email=data.email,
        password_hash=hash_password(data.password),
        nombre=data.nombre,
        telefono=data.telefono,
        direccion=data.direccion,
        created_at=datetime.now(timezone.utc),
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return {"token": create_cliente_token(cliente.id)}


@router.post("/login", response_model=TokenResponse)
def login(data: ClienteLogin, db: Session = Depends(get_db)):
    cliente = (
        db.query(ClienteB2B)
        .filter(
            ClienteB2B.email == data.email,
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
