from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Ingrediente, LineaReceta, Receta, User
from app.permissions import require_permission
from app.schemas import RecetaCreate, RecetaOut, RecetaUpdate, LineaRecetaOut
from app.services.costes import costo_linea, costo_receta

router = APIRouter(prefix="/api/recetas", tags=["recetas"])


def _linea_out(linea: LineaReceta, db: Session) -> dict:
    nombre = ""
    if linea.ingrediente_rel:
        nombre = linea.ingrediente_rel.nombre
    elif linea.subreceta_rel:
        nombre = linea.subreceta_rel.nombre
    return {
        "id": linea.id,
        "ingrediente_id": linea.ingrediente_id,
        "subreceta_id": linea.subreceta_id,
        "cantidad": linea.cantidad,
        "unidad": linea.unidad,
        "nombre": nombre,
        "costo_linea": costo_linea(linea, db),
    }


def _to_out(receta: Receta, db: Session) -> dict:
    total, por_porcion = costo_receta(receta, db)
    margen = None
    multi = None
    if receta.precio_venta and receta.precio_venta > 0 and por_porcion > 0:
        margen = (receta.precio_venta - por_porcion) / receta.precio_venta * 100
        multi = receta.precio_venta / por_porcion

    return {
        "id": receta.id,
        "nombre": receta.nombre,
        "categoria_id": receta.categoria_id,
        "categoria_nombre": receta.categoria_rel.nombre if receta.categoria_rel else "",
        "porciones_por_lote": receta.porciones_por_lote,
        "precio_venta": receta.precio_venta,
        "es_subreceta": receta.es_subreceta,
        "unidad_rendimiento": receta.unidad_rendimiento,
        "notas": receta.notas,
        "costo_total": total,
        "costo_por_porcion": por_porcion,
        "margen": round(margen, 2) if margen is not None else None,
        "multi": round(multi, 2) if multi is not None else None,
        "lineas": [_linea_out(l, db) for l in receta.lineas],
    }


@router.get("", response_model=list[RecetaOut])
def list_recetas(
    categoria_id: int | None = Query(None),
    es_subreceta: bool | None = Query(None),
    buscar: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.ingrediente_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.subreceta_rel),
    )
    if categoria_id:
        q = q.filter(Receta.categoria_id == categoria_id)
    if es_subreceta is not None:
        q = q.filter(Receta.es_subreceta == es_subreceta)
    if buscar:
        q = q.filter(Receta.nombre.ilike(f"%{buscar}%"))
    recetas = q.order_by(Receta.nombre).all()
    return [_to_out(r, db) for r in recetas]


@router.get("/{rec_id}", response_model=RecetaOut)
def get_receta(rec_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    receta = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.ingrediente_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.subreceta_rel),
    ).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return _to_out(receta, db)


@router.post("", response_model=RecetaOut, status_code=201)
def create_receta(
    data: RecetaCreate,
    user: User = require_permission("recetas", "create"),
    db: Session = Depends(get_db),
):
    receta = Receta(
        nombre=data.nombre,
        categoria_id=data.categoria_id,
        porciones_por_lote=data.porciones_por_lote,
        precio_venta=data.precio_venta,
        es_subreceta=data.es_subreceta,
        unidad_rendimiento=data.unidad_rendimiento,
        notas=data.notas,
    )
    db.add(receta)
    db.flush()

    for l in data.lineas:
        linea = LineaReceta(
            receta_id=receta.id,
            ingrediente_id=l.ingrediente_id,
            subreceta_id=l.subreceta_id,
            cantidad=l.cantidad,
            unidad=l.unidad,
        )
        db.add(linea)

    db.commit()
    db.refresh(receta, ["lineas", "categoria_rel"])
    for linea in receta.lineas:
        db.refresh(linea, ["ingrediente_rel", "subreceta_rel"])
    return _to_out(receta, db)


@router.put("/{rec_id}", response_model=RecetaOut)
def update_receta(
    rec_id: int,
    data: RecetaUpdate,
    user: User = require_permission("recetas", "edit"),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas),
    ).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    updates = data.model_dump(exclude_unset=True)
    lineas_data = updates.pop("lineas", None)

    for key, val in updates.items():
        setattr(receta, key, val)

    if lineas_data is not None:
        for old_line in receta.lineas:
            db.delete(old_line)
        db.flush()
        for l in lineas_data:
            linea = LineaReceta(
                receta_id=receta.id,
                ingrediente_id=l.get("ingrediente_id"),
                subreceta_id=l.get("subreceta_id"),
                cantidad=l["cantidad"],
                unidad=l["unidad"],
            )
            db.add(linea)

    db.commit()
    db.refresh(receta, ["lineas", "categoria_rel"])
    for linea in receta.lineas:
        db.refresh(linea, ["ingrediente_rel", "subreceta_rel"])
    return _to_out(receta, db)


@router.delete("/{rec_id}")
def delete_receta(
    rec_id: int,
    user: User = require_permission("recetas", "delete"),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    if db.query(LineaReceta).filter(LineaReceta.subreceta_id == rec_id).count() > 0:
        raise HTTPException(status_code=409, detail="Receta usada como subreceta")
    db.delete(receta)
    db.commit()
    return {"ok": True}
