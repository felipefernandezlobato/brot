from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProductoCatalogo
from app.schemas import ProductoCatalogoOut

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])


@router.get("", response_model=list[ProductoCatalogoOut])
def list_catalogo(db: Session = Depends(get_db)):
    return (
        db.query(ProductoCatalogo)
        .filter(ProductoCatalogo.disponible == True)  # noqa: E712
        .order_by(ProductoCatalogo.posicion, ProductoCatalogo.nombre)
        .all()
    )


@router.get("/{item_id}", response_model=ProductoCatalogoOut)
def get_catalogo_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item
