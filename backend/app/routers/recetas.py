from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from sqlalchemy import func

from app.models import Ingrediente, LineaReceta, MovimientoStock, ProductoCongelado, Receta, StockCongelado, User
from app.permissions import require_permission
from app.schemas import RecetaCreate, RecetaOut, RecetaUpdate, LineaRecetaOut
from app.services.costes import costo_linea, costo_receta
from app.services.produccion_registro import describir_referencia, movimiento_no_revertido
from app.services.stock import historial_congelado_acumulado

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


@router.get("/{rec_id}/completo")
def get_receta_completo(
    rec_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unified view: recipe + product + stock + flow — everything in one call."""
    receta = db.query(Receta).options(
        joinedload(Receta.categoria_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.ingrediente_rel),
        joinedload(Receta.lineas).joinedload(LineaReceta.subreceta_rel),
    ).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    receta_out = _to_out(receta, db)

    # Find linked ProductoCongelado (prefer masa > semi > crudo > terminado)
    prods_linked = db.query(ProductoCongelado).filter(ProductoCongelado.receta_id == rec_id).all()
    if receta.es_subreceta:
        nivel_order = {"masa": 0, "semi": 1, "crudo": 2, "terminado": 3}
    else:
        nivel_order = {"terminado": 0, "crudo": 1, "semi": 2, "masa": 3}
    prods_linked.sort(key=lambda p: nivel_order.get(p.nivel, 9))
    prod = prods_linked[0] if prods_linked else None

    producto = None
    stock_actual = 0
    stock_history = []
    movimientos = []
    ancestors = []
    padre = None
    hijos = []

    if prod:
        # Cumulative stock history from MovimientoStock (shows both production AND consumption)
        stock_history = historial_congelado_acumulado(db, producto_ids=[prod.id]).get(prod.id, [])

        # Stock actual: from movements if available (last point == sum of all
        # movement cantidades), fallback to StockCongelado sum
        if stock_history:
            stock_actual = stock_history[-1]["cantidad"]
        else:
            stock_actual = (
                db.query(func.coalesce(func.sum(StockCongelado.cantidad), 0))
                .filter(StockCongelado.producto_congelado_id == prod.id, StockCongelado.is_active.is_(True))
                .scalar()
            ) or 0

        movimientos = [
            {
                "id": m.id, "tipo_movimiento": m.tipo_movimiento,
                "cantidad": m.cantidad, "fecha": str(m.fecha),
                "referencia_origen": m.referencia_origen,
                "nombre_origen": describir_referencia(db, m.referencia_origen),
                "saldo_despues": m.saldo_despues,
            }
            for m in db.query(MovimientoStock)
            .filter(
                MovimientoStock.tipo_stock == "congelado",
                MovimientoStock.referencia_producto_id == prod.id,
                movimiento_no_revertido(),
            )
            .order_by(MovimientoStock.id.desc())
            .limit(20)
            .all()
        ]

        # Build full ancestor chain (walk up)
        ancestors = []
        current = prod
        while current and current.producto_padre_id:
            p = db.query(ProductoCongelado).filter(ProductoCongelado.id == current.producto_padre_id).first()
            if not p:
                break
            ancestors.insert(0, {
                "id": p.id, "nombre": p.nombre, "nivel": p.nivel,
                "receta_id": p.receta_id, "cantidad_por_padre": current.cantidad_por_padre,
            })
            current = p
        if ancestors:
            padre = ancestors[0]

        # Build full descendant tree (walk down recursively)
        def build_tree(pid: int, depth: int = 0) -> list:
            if depth > 5:
                return []
            children = db.query(ProductoCongelado).filter(ProductoCongelado.producto_padre_id == pid).all()
            return [
                {
                    "id": c.id, "nombre": c.nombre, "nivel": c.nivel,
                    "cantidad_por_padre": c.cantidad_por_padre, "receta_id": c.receta_id,
                    "hijos": build_tree(c.id, depth + 1),
                }
                for c in children
            ]

        hijos = build_tree(prod.id)

        producto = {
            "id": prod.id,
            "nombre": prod.nombre,
            "nivel": prod.nivel,
            "categoria": prod.categoria,
            "unidad": prod.unidad,
            "cantidad_por_padre": prod.cantidad_por_padre,
        }

    # Recipes that use this as sub-recipe
    usado_en = []
    for l in db.query(LineaReceta).filter(LineaReceta.subreceta_id == rec_id).all():
        r = db.get(Receta, l.receta_id)
        if r:
            usado_en.append({"id": r.id, "nombre": r.nombre})

    # Real stock consumption (productos padre)
    consume_productos = []
    if prod and prod.producto_padre_id:
        p = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod.producto_padre_id).first()
        if p:
            consume_productos.append({
                "id": p.id, "nombre": p.nombre, "nivel": p.nivel,
                "cantidad": prod.cantidad_por_padre, "receta_id": p.receta_id,
            })

    return {
        "receta": receta_out,
        "producto": producto,
        "stock_actual": stock_actual,
        "stock_history": stock_history,
        "movimientos": movimientos,
        "ancestors": ancestors,
        "padre": padre,
        "hijos": hijos,
        "usado_en": usado_en,
        "consume_productos": consume_productos,
    }


@router.get("/{rec_id}/flujo")
def get_flujo_receta(
    rec_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full production chain for a recipe — what it consumes, what products it feeds."""
    receta = db.query(Receta).filter(Receta.id == rec_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    # Ingredients consumed (only real ingredient lines, not sub-recipes which are for costing)
    lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == rec_id).all()
    ingredientes = []
    sub_recetas_coste = []
    for l in lineas:
        if l.ingrediente_id:
            ing = db.get(Ingrediente, l.ingrediente_id)
            if ing:
                ingredientes.append({"id": ing.id, "nombre": ing.nombre, "cantidad": l.cantidad, "unidad": l.unidad})
        elif l.subreceta_id:
            sr = db.get(Receta, l.subreceta_id)
            if sr:
                sub_recetas_coste.append({"id": sr.id, "nombre": sr.nombre, "cantidad": l.cantidad, "unidad": l.unidad, "solo_coste": True})

    # Real stock consumption: what ProductoCongelado padre this product consumes
    consume_productos = []
    for p in db.query(ProductoCongelado).filter(ProductoCongelado.receta_id == rec_id).all():
        if p.producto_padre_id:
            padre = db.query(ProductoCongelado).filter(ProductoCongelado.id == p.producto_padre_id).first()
            if padre:
                consume_productos.append({
                    "id": padre.id, "nombre": padre.nombre, "nivel": padre.nivel,
                    "cantidad": p.cantidad_por_padre,
                })

    # Products that use this recipe (ProductoCongelado with receta_id = this)
    productos_directos = db.query(ProductoCongelado).filter(ProductoCongelado.receta_id == rec_id).all()

    # Build full chain downstream: this recipe -> products -> children -> grandchildren
    def build_chain(prod_id: int, depth: int = 0) -> dict:
        p = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod_id).first()
        if not p or depth > 5:
            return None
        hijos = db.query(ProductoCongelado).filter(ProductoCongelado.producto_padre_id == prod_id).all()
        return {
            "id": p.id,
            "nombre": p.nombre,
            "nivel": p.nivel,
            "cantidad_por_padre": p.cantidad_por_padre,
            "receta_id": p.receta_id,
            "hijos": [build_chain(h.id, depth + 1) for h in hijos if build_chain(h.id, depth + 1)],
        }

    cadena = [build_chain(p.id) for p in productos_directos]

    # Also find recipes that use THIS recipe as sub-recipe (upstream)
    padres = db.query(LineaReceta).filter(LineaReceta.subreceta_id == rec_id).all()
    recetas_padre = []
    for l in padres:
        r = db.get(Receta, l.receta_id)
        if r:
            recetas_padre.append({"id": r.id, "nombre": r.nombre})

    total, porcion = costo_receta(receta, db)

    return {
        "receta": {
            "id": receta.id,
            "nombre": receta.nombre,
            "es_subreceta": receta.es_subreceta,
            "porciones_por_lote": receta.porciones_por_lote,
            "costo_total": round(total, 2),
            "costo_porcion": round(porcion, 2),
            "precio_venta": receta.precio_venta,
        },
        "consume": {
            "ingredientes": ingredientes,
            "productos": consume_productos,
            "sub_recetas_coste": sub_recetas_coste,
        },
        "produce": cadena,
        "usado_en": recetas_padre,
    }


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
