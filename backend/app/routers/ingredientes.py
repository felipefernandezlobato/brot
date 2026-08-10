from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import HistorialPrecio, Ingrediente, LineaReceta, User
from app.permissions import require_permission
from app.schemas import (
    HistorialPrecioOut,
    IngredienteCreate,
    IngredienteOut,
    IngredienteUpdate,
)
from app.services.costes import costo_por_unidad_uso

router = APIRouter(prefix="/api/ingredientes", tags=["ingredientes"])


def _to_out(ing: Ingrediente) -> dict:
    return {
        "id": ing.id,
        "nombre": ing.nombre,
        "categoria_id": ing.categoria_id,
        "categoria_nombre": ing.categoria_rel.nombre if ing.categoria_rel else "",
        "unidad_compra": ing.unidad_compra,
        "cantidad_compra": ing.cantidad_compra,
        "precio_compra": ing.precio_compra,
        "unidad_uso": ing.unidad_uso,
        "merma_porcentaje": ing.merma_porcentaje,
        "proveedor": ing.proveedor,
        "notas": ing.notas,
        "activo": ing.activo,
        "costo_por_unidad_uso": costo_por_unidad_uso(ing),
        "fecha_actualizacion": ing.fecha_actualizacion,
    }


@router.get("", response_model=list[IngredienteOut])
def list_ingredientes(
    categoria_id: int | None = Query(None),
    buscar: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Ingrediente).options(joinedload(Ingrediente.categoria_rel))
    if categoria_id:
        q = q.filter(Ingrediente.categoria_id == categoria_id)
    if buscar:
        q = q.filter(Ingrediente.nombre.ilike(f"%{buscar}%"))
    return [_to_out(i) for i in q.order_by(Ingrediente.nombre).all()]


@router.get("/{ing_id}", response_model=IngredienteOut)
def get_ingrediente(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).options(
        joinedload(Ingrediente.categoria_rel)
    ).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    return _to_out(ing)


@router.post("", response_model=IngredienteOut, status_code=201)
def create_ingrediente(
    data: IngredienteCreate,
    user: User = require_permission("ingredientes", "create"),
    db: Session = Depends(get_db),
):
    ing = Ingrediente(**data.model_dump())
    db.add(ing)
    db.commit()
    db.refresh(ing)
    db.refresh(ing, ["categoria_rel"])
    return _to_out(ing)


@router.put("/{ing_id}", response_model=IngredienteOut)
def update_ingrediente(
    ing_id: int,
    data: IngredienteUpdate,
    user: User = require_permission("ingredientes", "edit"),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).options(
        joinedload(Ingrediente.categoria_rel)
    ).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    updates = data.model_dump(exclude_unset=True)
    precio_cambio = "precio_compra" in updates and updates["precio_compra"] != ing.precio_compra

    if precio_cambio:
        historial = HistorialPrecio(
            ingrediente_id=ing.id,
            precio_anterior=ing.precio_compra,
            precio_nuevo=updates["precio_compra"],
        )
        db.add(historial)

    for key, val in updates.items():
        setattr(ing, key, val)
    db.commit()
    db.refresh(ing)
    return _to_out(ing)


@router.delete("/{ing_id}")
def delete_ingrediente(
    ing_id: int,
    user: User = require_permission("ingredientes", "delete"),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
    if db.query(LineaReceta).filter(LineaReceta.ingrediente_id == ing_id).count() > 0:
        raise HTTPException(status_code=409, detail="Ingrediente usado en recetas")
    db.delete(ing)
    db.commit()
    return {"ok": True}


@router.get("/{ing_id}/historial", response_model=list[HistorialPrecioOut])
def get_historial(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(HistorialPrecio)
        .filter(HistorialPrecio.ingrediente_id == ing_id)
        .order_by(HistorialPrecio.fecha_cambio.desc())
        .all()
    )
