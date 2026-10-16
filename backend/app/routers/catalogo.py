"""Catalogo de productos que ve el cliente en el portal.

**Dejo de ser publico el 2026-10-16.** Respondia sin ninguna credencial, asi
que los precios B2B estaban a la vista de cualquiera con la URL -- lo que
hacia inutil esconder el catalogo al cliente no aprobado, porque el dato
salia igual por esta puerta.

Ahora hacen falta credenciales, y valen dos tipos distintos:
  * empleado (`/entregas` arma las entregas con esta misma lista)
  * cliente del portal YA APROBADO y con el correo verificado

Se aceptan las dos en vez de duplicar el endpoint: es exactamente la misma
lista, lo unico que cambia es quien pregunta.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.auth_cliente import get_cliente_aprobado, get_current_cliente
from app.database import get_db
from app.models import ProductoCatalogo
from app.schemas import ProductoCatalogoOut

router = APIRouter(prefix="/api/catalogo", tags=["catalogo"])

_security = HTTPBearer(auto_error=False)


def _puede_ver_catalogo(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> None:
    """Deja pasar a un empleado o a un cliente aprobado.

    Prueba primero el token de empleado y, si no cuela, el de cliente. Hay
    que llamar a las dependencias a mano porque FastAPI no sabe expresar un
    "cualquiera de estas dos" y usar `Depends` de ambas exigiria las dos.

    El error que se propaga es el del CLIENTE, no el del empleado: quien se
    topa con esto en la practica es un cliente pendiente de aprobacion, y su
    mensaje ("tu cuenta esta pendiente") es el util. Decirle "token de
    empleado invalido" no le sirve de nada.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    try:
        get_current_user(db=db, credentials=credentials)
        return
    except HTTPException:
        pass
    get_cliente_aprobado(cliente=get_current_cliente(db=db, credentials=credentials))


@router.get("", response_model=list[ProductoCatalogoOut])
def list_catalogo(_: None = Depends(_puede_ver_catalogo), db: Session = Depends(get_db)):
    return (
        db.query(ProductoCatalogo)
        .filter(ProductoCatalogo.disponible == True)  # noqa: E712
        .order_by(ProductoCatalogo.posicion, ProductoCatalogo.nombre)
        .all()
    )


@router.get("/{item_id}", response_model=ProductoCatalogoOut)
def get_catalogo_item(
    item_id: int,
    _: None = Depends(_puede_ver_catalogo),
    db: Session = Depends(get_db),
):
    item = db.query(ProductoCatalogo).filter(ProductoCatalogo.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item
