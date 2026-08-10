from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Permission, User
from app.permissions import check_permission
from app.schemas import PermissionOut, PermissionUpdate

router = APIRouter(prefix="/api/permisos", tags=["permisos"])


@router.get("", response_model=list[PermissionOut])
def list_permissions(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(Permission).order_by(Permission.module, Permission.action).all()


@router.get("/check/{module}/{action}")
def check(module: str, action: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed = check_permission(db, user.role, module, action)
    return {"module": module, "action": action, "allowed": allowed}


@router.get("/mi-rol")
def my_permissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == "admin":
        return {"role": "admin", "all_allowed": True}
    perms = db.query(Permission).filter(Permission.role == user.role).all()
    return {
        "role": user.role,
        "permissions": {f"{p.module}.{p.action}": p.allowed for p in perms},
    }


@router.put("/{permission_id}", response_model=PermissionOut)
def update_permission(
    permission_id: int,
    data: PermissionUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    perm = db.query(Permission).filter(Permission.id == permission_id).first()
    if not perm:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
    perm.allowed = data.allowed
    db.commit()
    db.refresh(perm)
    return perm
