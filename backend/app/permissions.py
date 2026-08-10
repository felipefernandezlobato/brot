from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Permission, User

MODULES = [
    "ingredientes", "categorias", "recetas", "stock", "congelados",
    "mermas", "produccion", "pedidos_proveedores", "pedidos_clientes",
    "entregas_proveedor", "entregas_b2b", "protocolos", "temperaturas",
    "competencia", "equipo", "permisos", "importar", "backup",
]

ACTIONS = ["view", "create", "edit", "delete"]


def check_permission(db: Session, role: str, module: str, action: str) -> bool:
    if role == "admin":
        return True
    perm = db.query(Permission).filter(
        Permission.role == role,
        Permission.module == module,
        Permission.action == action,
    ).first()
    if not perm:
        return False
    return perm.allowed


def require_permission(module: str, action: str):
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not check_permission(db, user.role, module, action):
            raise HTTPException(
                status_code=403,
                detail=f"Sin permiso: {module}/{action}",
            )
        return user
    return Depends(dependency)


def seed_default_permissions(db: Session):
    if db.query(Permission).count() > 0:
        return
    for module in MODULES:
        for action in ACTIONS:
            perm = Permission(role="staff", module=module, action=action, allowed=True)
            db.add(perm)
    db.commit()
