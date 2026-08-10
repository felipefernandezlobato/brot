from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import PrecioCompetencia, Receta, User
from app.permissions import require_permission
from app.schemas import PrecioCompetenciaCreate, PrecioCompetenciaOut

router = APIRouter(prefix="/api/competencia", tags=["competencia"])


# NOTE: /comparar must be declared before /{precio_id} so the literal segment
# takes precedence.
@router.get("/comparar")
def comparar_competencia(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Each recipe with its PVP + all competitor prices side by side."""
    recetas = db.query(Receta).order_by(Receta.nombre).all()
    precios = db.query(PrecioCompetencia).all()

    mapa: dict[int, list] = defaultdict(list)
    for p in precios:
        mapa[p.receta_id].append(p)

    result = []
    for receta in recetas:
        competidores = [
            {
                "id": p.id,
                "competidor_nombre": p.competidor_nombre,
                "precio": p.precio,
                "fecha_registro": p.fecha_registro,
                "notas": p.notas,
            }
            for p in mapa.get(receta.id, [])
        ]
        result.append(
            {
                "receta_id": receta.id,
                "receta_nombre": receta.nombre,
                "pvp": receta.precio_venta,
                "competidores": competidores,
            }
        )
    return result


@router.get("", response_model=list[PrecioCompetenciaOut])
def list_competencia(
    receta_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(PrecioCompetencia)
    if receta_id:
        q = q.filter(PrecioCompetencia.receta_id == receta_id)
    return q.order_by(
        PrecioCompetencia.receta_id, PrecioCompetencia.competidor_nombre
    ).all()


@router.post("", response_model=PrecioCompetenciaOut, status_code=201)
def create_competencia(
    data: PrecioCompetenciaCreate,
    user: User = require_permission("competencia", "create"),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).filter(Receta.id == data.receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    obj = PrecioCompetencia(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{precio_id}", response_model=PrecioCompetenciaOut)
def update_competencia(
    precio_id: int,
    data: PrecioCompetenciaCreate,
    user: User = require_permission("competencia", "edit"),
    db: Session = Depends(get_db),
):
    obj = db.query(PrecioCompetencia).filter(PrecioCompetencia.id == precio_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Precio competencia no encontrado")
    for key, val in data.model_dump().items():
        setattr(obj, key, val)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{precio_id}")
def delete_competencia(
    precio_id: int,
    user: User = require_permission("competencia", "delete"),
    db: Session = Depends(get_db),
):
    obj = db.query(PrecioCompetencia).filter(PrecioCompetencia.id == precio_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Precio competencia no encontrado")
    db.delete(obj)
    db.commit()
    return {"ok": True}
