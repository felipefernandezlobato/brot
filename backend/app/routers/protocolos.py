from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import ProtocoloCompletion, ProtocoloTemplate, User
from app.schemas import (
    ProtocoloCompletionOut,
    ProtocoloTemplateCreate,
    ProtocoloTemplateOut,
    ProtocoloTemplateUpdate,
)

router = APIRouter(prefix="/api/protocolos", tags=["protocolos"])


# ── Request bodies ─────────────────────────────────────────────────────────────

class CompletarRequest(BaseModel):
    template_id: int
    target_date: str
    target_period: Optional[str] = None


class RevisionRequest(BaseModel):
    is_satisfactory: bool
    review_note: Optional[str] = None


# ── Private helpers ────────────────────────────────────────────────────────────

def _template_dict(t: ProtocoloTemplate) -> dict:
    return {
        "id": t.id,
        "checklist_type": t.checklist_type,
        "section": t.section,
        "task_name": t.task_name,
        "position": t.position,
        "day_of_week": t.day_of_week,
        "day_of_month": t.day_of_month,
        "shift": t.shift,
        "is_active": t.is_active,
    }


def _completion_dict(c: ProtocoloCompletion) -> dict:
    return {
        "id": c.id,
        "template_id": c.template_id,
        "completed_by": c.completed_by,
        "completed_at": c.completed_at,
        "target_date": c.target_date,
        "target_period": c.target_period,
        "is_satisfactory": c.is_satisfactory,
        "review_note": c.review_note,
        "reviewed_by": c.reviewed_by,
        "reviewed_at": c.reviewed_at,
    }


def _item(t: ProtocoloTemplate, c: Optional[ProtocoloCompletion]) -> dict:
    return {"template": _template_dict(t), "completion": _completion_dict(c) if c else None}


def _find_by_date(db: Session, template_id: int, target_date: str) -> Optional[ProtocoloCompletion]:
    return db.query(ProtocoloCompletion).filter(
        ProtocoloCompletion.template_id == template_id,
        ProtocoloCompletion.target_date == target_date,
    ).first()


def _find_by_period(db: Session, template_id: int, target_period: str) -> Optional[ProtocoloCompletion]:
    return db.query(ProtocoloCompletion).filter(
        ProtocoloCompletion.template_id == template_id,
        ProtocoloCompletion.target_period == target_period,
    ).first()


# ── Templates CRUD (admin) ─────────────────────────────────────────────────────

@router.get("/templates", response_model=list[ProtocoloTemplateOut])
def list_templates(
    checklist_type: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ProtocoloTemplate)
    if checklist_type:
        q = q.filter(ProtocoloTemplate.checklist_type == checklist_type)
    return q.order_by(ProtocoloTemplate.checklist_type, ProtocoloTemplate.position).all()


@router.post("/templates", response_model=ProtocoloTemplateOut, status_code=201)
def create_template(
    data: ProtocoloTemplateCreate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tmpl = ProtocoloTemplate(**data.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.get("/templates/{tmpl_id}", response_model=ProtocoloTemplateOut)
def get_template(
    tmpl_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tmpl = db.query(ProtocoloTemplate).filter(ProtocoloTemplate.id == tmpl_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    return tmpl


@router.put("/templates/{tmpl_id}", response_model=ProtocoloTemplateOut)
def update_template(
    tmpl_id: int,
    data: ProtocoloTemplateUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tmpl = db.query(ProtocoloTemplate).filter(ProtocoloTemplate.id == tmpl_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(tmpl, key, val)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.delete("/templates/{tmpl_id}")
def delete_template(
    tmpl_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tmpl = db.query(ProtocoloTemplate).filter(ProtocoloTemplate.id == tmpl_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template no encontrado")
    db.delete(tmpl)
    db.commit()
    return {"ok": True}


# ── Today's checklist ──────────────────────────────────────────────────────────

@router.get("/hoy")
def get_hoy(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today_str = date.today().isoformat()
    templates = (
        db.query(ProtocoloTemplate)
        .filter(
            ProtocoloTemplate.checklist_type == "diario",
            ProtocoloTemplate.is_active == True,  # noqa: E712
        )
        .order_by(ProtocoloTemplate.position)
        .all()
    )

    apertura: list[dict] = []
    cierre: list[dict] = []
    for tmpl in templates:
        completion = _find_by_date(db, tmpl.id, today_str)
        entry = _item(tmpl, completion)
        if tmpl.shift == "cierre":
            cierre.append(entry)
        else:
            apertura.append(entry)

    return {"fecha": today_str, "apertura": apertura, "cierre": cierre}


# ── Weekly checklist ───────────────────────────────────────────────────────────

@router.get("/semanal")
def get_semanal(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    iso = today.isocalendar()
    target_period = f"{iso.year}-W{iso.week:02d}"

    templates = (
        db.query(ProtocoloTemplate)
        .filter(
            ProtocoloTemplate.checklist_type == "semanal",
            ProtocoloTemplate.is_active == True,  # noqa: E712
        )
        .order_by(ProtocoloTemplate.position)
        .all()
    )

    items = [_item(t, _find_by_period(db, t.id, target_period)) for t in templates]
    return {"period": target_period, "items": items}


# ── Monthly checklist ──────────────────────────────────────────────────────────

@router.get("/mensual")
def get_mensual(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    target_period = today.strftime("%Y-%m")

    templates = (
        db.query(ProtocoloTemplate)
        .filter(
            ProtocoloTemplate.checklist_type == "mensual",
            ProtocoloTemplate.is_active == True,  # noqa: E712
        )
        .order_by(ProtocoloTemplate.position)
        .all()
    )

    items = [_item(t, _find_by_period(db, t.id, target_period)) for t in templates]
    return {"period": target_period, "items": items}


# ── Mark task done ─────────────────────────────────────────────────────────────

@router.post("/completar", response_model=ProtocoloCompletionOut, status_code=201)
def completar_task(
    data: CompletarRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tmpl = db.query(ProtocoloTemplate).filter(ProtocoloTemplate.id == data.template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template no encontrado")

    if _find_by_date(db, data.template_id, data.target_date):
        raise HTTPException(status_code=409, detail="Tarea ya completada para esta fecha")

    completion = ProtocoloCompletion(
        template_id=data.template_id,
        completed_by=user.id,
        target_date=data.target_date,
        target_period=data.target_period,
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)
    return completion


# ── Undo completion ────────────────────────────────────────────────────────────

@router.delete("/completar/{completion_id}")
def undo_completion(
    completion_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    completion = db.query(ProtocoloCompletion).filter(
        ProtocoloCompletion.id == completion_id
    ).first()
    if not completion:
        raise HTTPException(status_code=404, detail="Completación no encontrada")

    if user.role != "admin":
        if completion.completed_by != user.id:
            raise HTTPException(status_code=403, detail="No puedes deshacer la tarea de otro usuario")
        elapsed = datetime.utcnow() - completion.completed_at
        if elapsed > timedelta(hours=1):
            raise HTTPException(
                status_code=403,
                detail="Solo se puede deshacer dentro de la primera hora",
            )

    db.delete(completion)
    db.commit()
    return {"ok": True}


# ── Admin review ───────────────────────────────────────────────────────────────

@router.put("/completar/{completion_id}/revision", response_model=ProtocoloCompletionOut)
def review_completion(
    completion_id: int,
    data: RevisionRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    completion = db.query(ProtocoloCompletion).filter(
        ProtocoloCompletion.id == completion_id
    ).first()
    if not completion:
        raise HTTPException(status_code=404, detail="Completación no encontrada")

    completion.is_satisfactory = data.is_satisfactory
    completion.review_note = data.review_note
    completion.reviewed_by = user.id
    completion.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(completion)
    return completion


# ── History ────────────────────────────────────────────────────────────────────

@router.get("/historial", response_model=list[ProtocoloCompletionOut])
def get_historial(
    mode: str = Query("day", description="day | week | month"),
    period: str = Query(..., description="Reference date YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ref_date = date.fromisoformat(period)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato inválido — use YYYY-MM-DD")

    q = db.query(ProtocoloCompletion)

    if mode == "day":
        q = q.filter(ProtocoloCompletion.target_date == period)
    elif mode == "week":
        iso = ref_date.isocalendar()
        tp = f"{iso.year}-W{iso.week:02d}"
        q = q.filter(ProtocoloCompletion.target_period == tp)
    elif mode == "month":
        tp = ref_date.strftime("%Y-%m")
        q = q.filter(ProtocoloCompletion.target_period == tp)
    else:
        raise HTTPException(status_code=422, detail="mode debe ser day, week o month")

    return q.order_by(ProtocoloCompletion.completed_at.desc()).all()
