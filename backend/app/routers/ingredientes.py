from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from sqlalchemy import func

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    HistorialPrecio,
    Ingrediente,
    InventarioRegistro,
    LineaReceta,
    MovimientoStock,
    PrecioProveedor,
    Proveedor,
    Receta,
    User,
)
from app.permissions import require_permission
from app.schemas import (
    HistorialPrecioOut,
    IngredienteCreate,
    IngredienteOut,
    IngredienteUpdate,
)
from app.services.costes import costo_por_unidad_uso
from app.services.produccion_registro import movimiento_no_revertido, nombre_origen_movimiento
from app.services.stock import saldo_despues_por_movimiento

router = APIRouter(prefix="/api/ingredientes", tags=["ingredientes"])


def _to_out(ing: Ingrediente, db: Session | None = None) -> dict:
    num_recetas = 0
    if db:
        num_recetas = db.query(LineaReceta).filter(LineaReceta.ingrediente_id == ing.id).count()
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
        "num_recetas": num_recetas,
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
    return [_to_out(i, db) for i in q.order_by(Ingrediente.nombre).all()]


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
    return _to_out(ing, db)


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
    return _to_out(ing, db)


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
    return _to_out(ing, db)


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
    db.query(InventarioRegistro).filter(InventarioRegistro.ingrediente_id == ing_id).delete()
    db.query(PrecioProveedor).filter(PrecioProveedor.ingrediente_id == ing_id).delete()
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


@router.delete("/{ing_id}/historial/{historial_id}")
def delete_historial(
    ing_id: int,
    historial_id: int,
    user: User = require_permission("ingredientes", "delete"),
    db: Session = Depends(get_db),
):
    h = db.query(HistorialPrecio).filter(
        HistorialPrecio.id == historial_id,
        HistorialPrecio.ingrediente_id == ing_id,
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Historial no encontrado")
    db.delete(h)
    db.commit()
    return {"ok": True}


@router.get("/{ing_id}/recetas")
def get_recetas_usando(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lineas = (
        db.query(LineaReceta)
        .filter(LineaReceta.ingrediente_id == ing_id)
        .all()
    )
    receta_ids = {l.receta_id for l in lineas}
    recetas = db.query(Receta).filter(Receta.id.in_(receta_ids)).all() if receta_ids else []

    from app.services.costes import costo_receta
    result = []
    for r in recetas:
        total, porcion = costo_receta(r, db)
        multi = r.precio_venta / porcion if r.precio_venta and porcion > 0 else None
        result.append({
            "id": r.id,
            "nombre": r.nombre,
            "categoria": r.categoria_rel.nombre if r.categoria_rel else "",
            "precio_venta": r.precio_venta,
            "costo_porcion": round(porcion, 2),
            "multi": round(multi, 2) if multi else None,
        })
    return result


@router.get("/{ing_id}/precios-proveedores")
def get_precios_proveedores(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    precios = (
        db.query(PrecioProveedor)
        .join(Proveedor, Proveedor.id == PrecioProveedor.proveedor_id)
        .filter(PrecioProveedor.ingrediente_id == ing_id)
        .all()
    )
    return [
        {
            "id": p.id,
            "proveedor_id": p.proveedor_id,
            "proveedor_nombre": p.proveedor_rel.nombre if p.proveedor_rel else "",
            "precio": p.precio,
            "unidad": p.unidad,
            "fecha": str(p.fecha),
        }
        for p in precios
    ]


@router.get("/{ing_id}/stock")
def get_stock_ingrediente(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    latest = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
    )
    return {
        "stock_actual": latest.cantidad if latest else 0,
        "unidad": latest.unidad if latest else "",
        "fecha_ultimo_conteo": str(latest.fecha_registro) if latest else None,
    }


@router.get("/{ing_id}/movimientos")
def get_movimientos_ingrediente(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ing = db.query(Ingrediente).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    movs = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.tipo_stock == "materia_prima",
            MovimientoStock.referencia_producto_id == ing_id,
            movimiento_no_revertido(),
        )
        .order_by(MovimientoStock.fecha.desc(), MovimientoStock.id.desc())
        .limit(30)
        .all()
    )

    saldos_vivos = saldo_despues_por_movimiento(db, "materia_prima", ing_id)
    return [
        {
            "id": m.id,
            "tipo_movimiento": m.tipo_movimiento,
            "cantidad": m.cantidad,
            "unidad": m.unidad,
            "fecha": m.fecha,
            "referencia_origen": m.referencia_origen,
            "nombre_origen": nombre_origen_movimiento(db, m),
            "saldo_despues": saldos_vivos.get(m.id, m.saldo_despues),
        }
        for m in movs
    ]
