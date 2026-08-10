from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Frigorifico, LecturaTemperatura, User
from app.schemas import FrigorificoCreate, FrigorificoOut, FrigorificoUpdate, LecturaTemperaturaOut

router = APIRouter(prefix="/api/temperaturas", tags=["temperaturas"])

VALID_SHIFTS = {"apertura", "cierre"}


# ── Request body ───────────────────────────────────────────────────────────────

class LecturaItem(BaseModel):
    frigorifico_id: int
    value: float


# ── Fridges CRUD (admin) ───────────────────────────────────────────────────────

@router.get("/frigorificos", response_model=list[FrigorificoOut])
def list_frigorificos(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Frigorifico)
        .filter(Frigorifico.is_active == True)  # noqa: E712
        .order_by(Frigorifico.position, Frigorifico.nombre)
        .all()
    )


@router.post("/frigorificos", response_model=FrigorificoOut, status_code=201)
def create_frigorifico(
    data: FrigorificoCreate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    frig = Frigorifico(**data.model_dump())
    db.add(frig)
    db.commit()
    db.refresh(frig)
    return frig


@router.get("/frigorificos/{frig_id}", response_model=FrigorificoOut)
def get_frigorifico(
    frig_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    frig = db.query(Frigorifico).filter(Frigorifico.id == frig_id).first()
    if not frig:
        raise HTTPException(status_code=404, detail="Frigorífico no encontrado")
    return frig


@router.put("/frigorificos/{frig_id}", response_model=FrigorificoOut)
def update_frigorifico(
    frig_id: int,
    data: FrigorificoUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    frig = db.query(Frigorifico).filter(Frigorifico.id == frig_id).first()
    if not frig:
        raise HTTPException(status_code=404, detail="Frigorífico no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(frig, key, val)
    db.commit()
    db.refresh(frig)
    return frig


@router.delete("/frigorificos/{frig_id}")
def delete_frigorifico(
    frig_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    frig = db.query(Frigorifico).filter(Frigorifico.id == frig_id).first()
    if not frig:
        raise HTTPException(status_code=404, detail="Frigorífico no encontrado")
    frig.is_active = False
    db.commit()
    return {"ok": True}


# ── Temperature history ────────────────────────────────────────────────────────
# Declared BEFORE /{shift} so the static path wins for GET requests.

@router.get("/historial", response_model=list[LecturaTemperaturaOut])
def get_historial(
    frigorifico_id: Optional[int] = Query(None),
    dias: int = Query(30, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cutoff = (date.today() - timedelta(days=dias)).isoformat()
    q = db.query(LecturaTemperatura).filter(LecturaTemperatura.target_date >= cutoff)
    if frigorifico_id:
        q = q.filter(LecturaTemperatura.frigorifico_id == frigorifico_id)
    return q.order_by(LecturaTemperatura.target_date.desc(), LecturaTemperatura.shift).all()


# ── Batch record temperatures for a shift ─────────────────────────────────────

@router.post("/{shift}", response_model=list[LecturaTemperaturaOut], status_code=201)
def record_temperatures(
    shift: str,
    lecturas: list[LecturaItem],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if shift not in VALID_SHIFTS:
        raise HTTPException(status_code=422, detail="shift debe ser 'apertura' o 'cierre'")

    today_str = date.today().isoformat()
    results: list[LecturaTemperatura] = []

    for item in lecturas:
        frig = db.query(Frigorifico).filter(
            Frigorifico.id == item.frigorifico_id,
            Frigorifico.is_active == True,  # noqa: E712
        ).first()
        if not frig:
            raise HTTPException(
                status_code=404,
                detail=f"Frigorífico {item.frigorifico_id} no encontrado",
            )

        is_alert = item.value > frig.max_temp

        existing = db.query(LecturaTemperatura).filter(
            LecturaTemperatura.frigorifico_id == item.frigorifico_id,
            LecturaTemperatura.target_date == today_str,
            LecturaTemperatura.shift == shift,
        ).first()

        if existing:
            existing.value = item.value
            existing.is_alert = is_alert
            existing.recorded_by = user.id
            results.append(existing)
        else:
            lectura = LecturaTemperatura(
                frigorifico_id=item.frigorifico_id,
                recorded_by=user.id,
                target_date=today_str,
                shift=shift,
                value=item.value,
                is_alert=is_alert,
            )
            db.add(lectura)
            results.append(lectura)

    db.commit()
    for r in results:
        db.refresh(r)

    return results
