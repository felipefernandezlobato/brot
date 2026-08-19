from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Ingrediente, MermaRegistro, ProductoCongelado, User
from app.permissions import require_permission
from app.schemas import MermaRegistroCreate, MermaRegistroOut, MermaRegistroUpdate
from app.services.costes import costo_por_unidad_uso
from app.services.stock import (
    deducir_congelado_fifo,
    deducir_materia_prima,
    revertir_consumos,
)

router = APIRouter(prefix="/api/mermas", tags=["mermas"])

MOTIVOS_VALIDOS = {"caducado", "dañado", "produccion", "otro"}


def _apply_date_filters(q, fecha_desde: Optional[date], fecha_hasta: Optional[date]):
    if fecha_desde:
        q = q.filter(MermaRegistro.fecha >= fecha_desde)
    if fecha_hasta:
        q = q.filter(MermaRegistro.fecha <= fecha_hasta)
    return q


# ── Analysis endpoint must be declared before /{id} ──────────────────────────


@router.get("/analisis")
def analisis_mermas(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns:
      - coste_total_global: sum of all waste costs
      - total_registros: count of waste records
      - por_motivo: list of {motivo, count, coste_total}
      - top_items: top 10 items by waste cost (ingrediente_id or nombre_libre)
    """
    q = db.query(MermaRegistro)
    q = _apply_date_filters(q, fecha_desde, fecha_hasta)
    registros = q.all()

    coste_total_global = sum(r.coste_total for r in registros)
    total_registros = len(registros)

    # Breakdown by motivo
    motivo_map: dict[str, dict] = {}
    for r in registros:
        entry = motivo_map.setdefault(r.motivo, {"motivo": r.motivo, "count": 0, "coste_total": 0.0})
        entry["count"] += 1
        entry["coste_total"] += r.coste_total
    por_motivo = sorted(motivo_map.values(), key=lambda x: x["coste_total"], reverse=True)

    # Top 10 wasted items by cost
    item_map: dict[str, dict] = {}
    for r in registros:
        if r.ingrediente_id:
            key = f"ingrediente:{r.ingrediente_id}"
            ing = db.get(Ingrediente, r.ingrediente_id)
            label = ing.nombre if ing else f"Ingrediente #{r.ingrediente_id}"
        elif r.nombre_libre:
            key = f"libre:{r.nombre_libre}"
            label = r.nombre_libre
        elif r.receta_id:
            key = f"receta:{r.receta_id}"
            label = f"Receta #{r.receta_id}"
        else:
            key = "desconocido"
            label = "Desconocido"

        entry = item_map.setdefault(key, {"nombre": label, "coste_total": 0.0, "count": 0})
        entry["coste_total"] += r.coste_total
        entry["count"] += 1

    top_items = sorted(item_map.values(), key=lambda x: x["coste_total"], reverse=True)[:10]

    return {
        "coste_total_global": round(coste_total_global, 4),
        "total_registros": total_registros,
        "por_motivo": por_motivo,
        "top_items": top_items,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[MermaRegistroOut])
def list_mermas(
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    motivo: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MermaRegistro)
    q = _apply_date_filters(q, fecha_desde, fecha_hasta)
    if motivo:
        q = q.filter(MermaRegistro.motivo == motivo)
    return q.order_by(MermaRegistro.fecha.desc(), MermaRegistro.registered_at.desc()).all()


@router.get("/{merma_id}", response_model=MermaRegistroOut)
def get_merma(
    merma_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    merma = db.get(MermaRegistro, merma_id)
    if not merma:
        raise HTTPException(status_code=404, detail="Merma no encontrada")
    return merma


@router.post("", response_model=MermaRegistroOut, status_code=201)
def create_merma(
    data: MermaRegistroCreate,
    user: User = require_permission("mermas", "create"),
    db: Session = Depends(get_db),
):
    if data.motivo not in MOTIVOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Motivo inválido. Debe ser uno de: {', '.join(sorted(MOTIVOS_VALIDOS))}",
        )

    dump = data.model_dump()

    # Auto-calculate costs when an ingredient is linked
    if data.ingrediente_id:
        ing = db.get(Ingrediente, data.ingrediente_id)
        if not ing:
            raise HTTPException(status_code=404, detail="Ingrediente no encontrado")
        cpu = costo_por_unidad_uso(ing)
        dump["coste_unitario"] = cpu
        dump["coste_total"] = round(cpu * data.cantidad, 4)

    dump.setdefault("fecha", date.today())
    dump["registered_by"] = user.id

    merma = MermaRegistro(**dump)
    db.add(merma)
    db.flush()

    _aplicar_stock_merma(db, merma, user.id)

    db.commit()
    db.refresh(merma)
    return merma


def _ref_merma(merma: MermaRegistro) -> str:
    return f"merma:{merma.id}"


def _aplicar_stock_merma(db: Session, merma: MermaRegistro, user_id: int) -> None:
    """Deduct what this waste record says was lost, dated to the record itself."""
    ref = _ref_merma(merma)
    if merma.ingrediente_id:
        ing = db.get(Ingrediente, merma.ingrediente_id)
        if ing:
            deducir_materia_prima(
                db, merma.ingrediente_id, merma.cantidad,
                ing.unidad_uso, ref, user_id, fecha=merma.fecha,
                tipo_movimiento="merma",
            )
    elif merma.receta_id:
        prod_cong = db.query(ProductoCongelado).filter(
            ProductoCongelado.receta_id == merma.receta_id
        ).first()
        if prod_cong:
            deducir_congelado_fifo(
                db, prod_cong.id, merma.cantidad, ref, user_id, fecha=merma.fecha,
                tipo_movimiento="merma",
            )


@router.put("/{merma_id}", response_model=MermaRegistroOut)
def update_merma(
    merma_id: int,
    data: MermaRegistroUpdate,
    user: User = require_permission("mermas", "edit"),
    db: Session = Depends(get_db),
):
    merma = db.get(MermaRegistro, merma_id)
    if not merma:
        raise HTTPException(status_code=404, detail="Merma no encontrada")

    updates = data.model_dump(exclude_unset=True)

    if "motivo" in updates and updates["motivo"] not in MOTIVOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Motivo inválido. Debe ser uno de: {', '.join(sorted(MOTIVOS_VALIDOS))}",
        )

    # Anything that changes what was consumed means the old deduction is wrong.
    afecta_stock = {"cantidad", "ingrediente_id", "receta_id", "fecha"} & updates.keys()
    if afecta_stock:
        revertir_consumos(db, _ref_merma(merma), user.id, fecha=merma.fecha)

    for key, val in updates.items():
        setattr(merma, key, val)

    # Recalculate coste_total if cantidad or coste_unitario changed
    cantidad_changed = "cantidad" in updates
    cpu_changed = "coste_unitario" in updates
    if cantidad_changed or cpu_changed:
        merma.coste_total = round(merma.coste_unitario * merma.cantidad, 4)

    if afecta_stock:
        _aplicar_stock_merma(db, merma, user.id)

    db.commit()
    db.refresh(merma)
    return merma


@router.delete("/{merma_id}")
def delete_merma(
    merma_id: int,
    user: User = require_permission("mermas", "delete"),
    db: Session = Depends(get_db),
):
    merma = db.get(MermaRegistro, merma_id)
    if not merma:
        raise HTTPException(status_code=404, detail="Merma no encontrada")

    # The waste did not happen after all — put the stock back.
    revertidos = revertir_consumos(db, _ref_merma(merma), user.id, fecha=merma.fecha)

    db.delete(merma)
    db.commit()
    return {"ok": True, "movimientos_revertidos": revertidos}
