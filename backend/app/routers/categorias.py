from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Categoria, Ingrediente, Receta, User
from app.permissions import require_permission
from app.schemas import CategoriaCreate, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/api/categorias", tags=["categorias"])


@router.get("", response_model=list[CategoriaOut])
def list_categorias(
    tipo: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Categoria)
    if tipo:
        q = q.filter(Categoria.tipo == tipo)
    return q.order_by(Categoria.orden, Categoria.nombre).all()


@router.post("", response_model=CategoriaOut, status_code=201)
def create_categoria(
    data: CategoriaCreate,
    user: User = require_permission("categorias", "create"),
    db: Session = Depends(get_db),
):
    cat = Categoria(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{cat_id}", response_model=CategoriaOut)
def update_categoria(
    cat_id: int,
    data: CategoriaUpdate,
    user: User = require_permission("categorias", "edit"),
    db: Session = Depends(get_db),
):
    cat = db.query(Categoria).filter(Categoria.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(cat, key, val)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{cat_id}")
def delete_categoria(
    cat_id: int,
    user: User = require_permission("categorias", "delete"),
    db: Session = Depends(get_db),
):
    cat = db.query(Categoria).filter(Categoria.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    if db.query(Ingrediente).filter(Ingrediente.categoria_id == cat_id).count() > 0:
        raise HTTPException(status_code=409, detail="Categoría tiene ingredientes asociados")
    if db.query(Receta).filter(Receta.categoria_id == cat_id).count() > 0:
        raise HTTPException(status_code=409, detail="Categoría tiene recetas asociadas")
    db.delete(cat)
    db.commit()
    return {"ok": True}
