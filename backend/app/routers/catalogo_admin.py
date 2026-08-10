from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import ProductoCatalogo, User
from app.schemas import ProductoCatalogoCreate, ProductoCatalogoOut, ProductoCatalogoUpdate

router = APIRouter(prefix="/api/admin/catalogo", tags=["catalogo-admin"])


@router.get("", response_model=list[ProductoCatalogoOut])
def list_all(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return (
        db.query(ProductoCatalogo)
        .order_by(ProductoCatalogo.posicion, ProductoCatalogo.nombre)
        .all()
    )


@router.post("", response_model=ProductoCatalogoOut, status_code=201)
def create_producto(
    data: ProductoCatalogoCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    producto = ProductoCatalogo(**data.model_dump())
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.get("/{item_id}", response_model=ProductoCatalogoOut)
def get_producto(
    item_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item


@router.put("/{item_id}", response_model=ProductoCatalogoOut)
def update_producto(
    item_id: int,
    data: ProductoCatalogoUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(item, key, val)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_producto(
    item_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.delete(item)
    db.commit()
    return {"ok": True}
