from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import LogProduccion, PlanProduccion, ProductoProduccion, User
from app.permissions import require_permission
from app.schemas import (
    LogProduccionCreate,
    LogProduccionOut,
    LogProduccionUpdate,
    PlanProduccionCreate,
    PlanProduccionOut,
    ProductoProduccionCreate,
    ProductoProduccionOut,
    ProductoProduccionUpdate,
)

router = APIRouter(prefix="/api/produccion", tags=["produccion"])


# ==============================================================
# Helpers
# ==============================================================


def _producto_to_out(p: ProductoProduccion) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "categoria": p.categoria,
        "unidad": p.unidad,
        "shelf_life_days": p.shelf_life_days,
        "default_qty": p.default_qty,
        "is_active": p.is_active,
        "position": p.position,
    }


def _plan_to_out(pl: PlanProduccion) -> dict:
    return {
        "id": pl.id,
        "producto_id": pl.producto_id,
        "week_number": pl.week_number,
        "day_of_week": pl.day_of_week,
        "planned_qty": pl.planned_qty,
    }


def _log_to_out(log: LogProduccion) -> dict:
    return {
        "id": log.id,
        "producto_id": log.producto_id,
        "target_date": log.target_date,
        "planned_qty": log.planned_qty,
        "actual_qty": log.actual_qty,
        "duration_minutes_machine": log.duration_minutes_machine,
        "duration_minutes_human": log.duration_minutes_human,
        "is_unplanned": log.is_unplanned,
        "notes": log.notes,
        "recorded_by": log.recorded_by,
        "recorded_at": log.recorded_at,
    }


def _date_to_week_number(d: date) -> int:
    """Map a calendar date to a rotating cycle week (1–4) via ISO week number."""
    return (d.isocalendar().week - 1) % 4 + 1


# ==============================================================
# Products  —  CRUD at /api/produccion/productos
# ==============================================================


@router.get("/productos", response_model=list[ProductoProduccionOut])
def list_productos(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ProductoProduccion)
        .order_by(ProductoProduccion.position, ProductoProduccion.nombre)
        .all()
    )
    return [_producto_to_out(p) for p in rows]


@router.get("/productos/{producto_id}", response_model=ProductoProduccionOut)
def get_producto(
    producto_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(ProductoProduccion).filter(ProductoProduccion.id == producto_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _producto_to_out(p)


@router.post("/productos", response_model=ProductoProduccionOut, status_code=201)
def create_producto(
    data: ProductoProduccionCreate,
    user: User = require_permission("produccion", "create"),
    db: Session = Depends(get_db),
):
    p = ProductoProduccion(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _producto_to_out(p)


@router.put("/productos/{producto_id}", response_model=ProductoProduccionOut)
def update_producto(
    producto_id: int,
    data: ProductoProduccionUpdate,
    user: User = require_permission("produccion", "edit"),
    db: Session = Depends(get_db),
):
    p = db.query(ProductoProduccion).filter(ProductoProduccion.id == producto_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(p, key, val)
    db.commit()
    db.refresh(p)
    return _producto_to_out(p)


@router.delete("/productos/{producto_id}")
def delete_producto(
    producto_id: int,
    user: User = require_permission("produccion", "delete"),
    db: Session = Depends(get_db),
):
    p = db.query(ProductoProduccion).filter(ProductoProduccion.id == producto_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ==============================================================
# Plan  —  4-week rotating schedule
# ==============================================================


@router.get("/plan", response_model=list[PlanProduccionOut])
def get_plan(
    week_number: Optional[int] = Query(None),
    day_of_week: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(PlanProduccion)
    if week_number is not None:
        q = q.filter(PlanProduccion.week_number == week_number)
    if day_of_week is not None:
        q = q.filter(PlanProduccion.day_of_week == day_of_week)
    rows = q.order_by(PlanProduccion.week_number, PlanProduccion.day_of_week).all()
    return [_plan_to_out(pl) for pl in rows]


@router.post("/plan", response_model=PlanProduccionOut, status_code=201)
def create_or_update_plan(
    data: PlanProduccionCreate,
    user: User = require_permission("produccion", "create"),
    db: Session = Depends(get_db),
):
    """Upsert a plan entry — unique on (producto_id, week_number, day_of_week)."""
    existing = (
        db.query(PlanProduccion)
        .filter(
            PlanProduccion.producto_id == data.producto_id,
            PlanProduccion.week_number == data.week_number,
            PlanProduccion.day_of_week == data.day_of_week,
        )
        .first()
    )
    if existing:
        existing.planned_qty = data.planned_qty
        db.commit()
        db.refresh(existing)
        return _plan_to_out(existing)

    p = db.query(ProductoProduccion).filter(ProductoProduccion.id == data.producto_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    pl = PlanProduccion(**data.model_dump())
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return _plan_to_out(pl)


# ==============================================================
# Log  —  actual production records
# ==============================================================


@router.get("/log", response_model=list[LogProduccionOut])
def get_log(
    fecha: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(LogProduccion)
    if fecha:
        q = q.filter(LogProduccion.target_date == fecha)
    return [_log_to_out(log) for log in q.order_by(LogProduccion.target_date).all()]


@router.post("/log", status_code=201)
def create_log(
    data: LogProduccionCreate | list[LogProduccionCreate],
    user: User = require_permission("produccion", "create"),
    db: Session = Depends(get_db),
):
    items = data if isinstance(data, list) else [data]
    results = []
    for item in items:
        if item.actual_qty is None and item.duration_minutes_machine is None and item.duration_minutes_human is None:
            continue
        existing = (
            db.query(LogProduccion)
            .filter(
                LogProduccion.producto_id == item.producto_id,
                LogProduccion.target_date == item.target_date,
            )
            .first()
        )
        if existing:
            for field, val in item.model_dump(exclude_unset=True).items():
                if field not in ("producto_id", "target_date"):
                    setattr(existing, field, val)
            results.append(existing)
        else:
            p = db.query(ProductoProduccion).filter(ProductoProduccion.id == item.producto_id).first()
            if not p:
                continue
            log = LogProduccion(**item.model_dump())
            log.recorded_by = user.id
            db.add(log)
            results.append(log)
    db.commit()
    for r in results:
        db.refresh(r)
    if isinstance(data, list):
        return [_log_to_out(r) for r in results]
    return _log_to_out(results[0]) if results else {"ok": True}


@router.put("/log/{log_id}", response_model=LogProduccionOut)
def update_log(
    log_id: int,
    data: LogProduccionUpdate,
    user: User = require_permission("produccion", "edit"),
    db: Session = Depends(get_db),
):
    log = db.query(LogProduccion).filter(LogProduccion.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(log, key, val)
    db.commit()
    db.refresh(log)
    return _log_to_out(log)


# ==============================================================
# Calendar  —  planned + actual for a date range
# ==============================================================


@router.get("/calendario")
def get_calendario(
    fecha_desde: str = Query(..., description="Start date YYYY-MM-DD"),
    fecha_hasta: str = Query(..., description="End date YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        d_desde = date.fromisoformat(fecha_desde)
        d_hasta = date.fromisoformat(fecha_hasta)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")

    if d_desde > d_hasta:
        raise HTTPException(
            status_code=400,
            detail="fecha_desde debe ser anterior o igual a fecha_hasta",
        )

    # Build list of dates in range
    all_dates: list[date] = []
    cur = d_desde
    while cur <= d_hasta:
        all_dates.append(cur)
        cur += timedelta(days=1)

    date_strs = [d.isoformat() for d in all_dates]

    # Fetch all logs for the range in one query
    logs = (
        db.query(LogProduccion)
        .filter(LogProduccion.target_date.in_(date_strs))
        .all()
    )
    # Index by (target_date, producto_id) for planned entries
    log_index: dict[tuple[str, int], LogProduccion] = {}
    # Separate set of (target_date, producto_id) for unplanned logs
    unplanned: list[LogProduccion] = []
    for log in logs:
        if log.is_unplanned:
            unplanned.append(log)
        else:
            log_index[(log.target_date, log.producto_id)] = log

    result = []

    for d in all_dates:
        week_num = _date_to_week_number(d)
        dow = d.weekday()  # 0 = Monday … 6 = Sunday
        date_str = d.isoformat()

        # Planned entries for this cycle slot
        plan_entries = (
            db.query(PlanProduccion)
            .filter(
                PlanProduccion.week_number == week_num,
                PlanProduccion.day_of_week == dow,
            )
            .all()
        )

        seen_product_ids: set[int] = set()
        for plan in plan_entries:
            log = log_index.get((date_str, plan.producto_id))
            result.append(
                {
                    "fecha": date_str,
                    "week_number": week_num,
                    "day_of_week": dow,
                    "producto_id": plan.producto_id,
                    "planned_qty": plan.planned_qty,
                    "actual_qty": log.actual_qty if log else None,
                    "log_id": log.id if log else None,
                    "duration_minutes_machine": log.duration_minutes_machine if log else None,
                    "duration_minutes_human": log.duration_minutes_human if log else None,
                    "is_unplanned": False,
                }
            )
            seen_product_ids.add(plan.producto_id)

        # Unplanned logs for this date
        for log in unplanned:
            if log.target_date == date_str and log.producto_id not in seen_product_ids:
                result.append(
                    {
                        "fecha": date_str,
                        "week_number": week_num,
                        "day_of_week": dow,
                        "producto_id": log.producto_id,
                        "planned_qty": None,
                        "actual_qty": log.actual_qty,
                        "log_id": log.id,
                        "duration_minutes_machine": log.duration_minutes_machine,
                        "duration_minutes_human": log.duration_minutes_human,
                        "is_unplanned": True,
                    }
                )

    return result
