from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from sqlalchemy import func

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    LineaReceta,
    MovimientoStock,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    StockCongelado,
    User,
)
from app.permissions import require_permission
from app.schemas import (
    ProductoCongeladoCreate,
    ProductoCongeladoOut,
    ProductoCongeladoUpdate,
    StockCongeladoCreate,
    StockCongeladoOut,
    StockCongeladoUpdate,
)
from app.services.produccion_registro import describir_referencia, movimiento_no_revertido
from app.services.stock import ajustar_correccion_conteo, es_conteo_manual, historial_movimientos_acumulado

router = APIRouter(prefix="/api/congelados", tags=["congelados"])


# ── helpers ────────────────────────────────────────────────────────────────────

def _stock_out(s: StockCongelado) -> dict:
    return {
        "id": s.id,
        "producto_congelado_id": s.producto_congelado_id,
        "cantidad": s.cantidad,
        "fecha_entrada": s.fecha_entrada,
        "fecha_vencimiento": s.fecha_vencimiento,
        "lote": s.lote,
        "ubicacion": s.ubicacion,
        "notas": s.notas,
        "is_active": s.is_active,
        "producto_nombre": s.producto.nombre if s.producto else None,
    }


# ── ProductoCongelado CRUD  (/api/congelados/productos) ────────────────────────

@router.get("/productos", response_model=list[ProductoCongeladoOut])
def list_productos_congelados(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.costes import costo_por_unidad_congelado

    productos = (
        db.query(ProductoCongelado)
        .order_by(ProductoCongelado.position, ProductoCongelado.nombre)
        .all()
    )
    return [
        {
            "id": p.id,
            "nombre": p.nombre,
            "categoria": p.categoria,
            "unidad": p.unidad,
            "is_active": p.is_active,
            "position": p.position,
            "receta_id": p.receta_id,
            "nivel": p.nivel,
            "producto_padre_id": p.producto_padre_id,
            "cantidad_por_padre": p.cantidad_por_padre,
            "costo_unitario": round(costo_por_unidad_congelado(db, p.id), 4),
        }
        for p in productos
    ]


@router.post("/productos", response_model=ProductoCongeladoOut, status_code=201)
def create_producto_congelado(
    data: ProductoCongeladoCreate,
    user: User = require_permission("congelados", "create"),
    db: Session = Depends(get_db),
):
    prod = ProductoCongelado(**data.model_dump())
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod


@router.get("/productos/{prod_id}/detalle")
def get_producto_detalle(
    prod_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Full ancestor chain (walk up)
    ancestors = []
    current = prod
    while current and current.producto_padre_id:
        p = db.query(ProductoCongelado).filter(ProductoCongelado.id == current.producto_padre_id).first()
        if not p:
            break
        ancestors.insert(0, {
            "id": p.id, "nombre": p.nombre, "nivel": p.nivel, "unidad": p.unidad,
            "receta_id": p.receta_id, "cantidad_por_padre": current.cantidad_por_padre,
        })
        current = p
    padre = ancestors[0] if ancestors else None

    # Full descendant tree (walk down)
    def build_tree(pid: int, depth: int = 0) -> list:
        if depth > 5:
            return []
        children = db.query(ProductoCongelado).filter(ProductoCongelado.producto_padre_id == pid).all()
        return [
            {"id": c.id, "nombre": c.nombre, "nivel": c.nivel,
             "cantidad_por_padre": c.cantidad_por_padre, "receta_id": c.receta_id,
             "hijos": build_tree(c.id, depth + 1)}
            for c in children
        ]
    hijos = build_tree(prod_id)

    # Recipe info
    receta_info = None
    if prod.receta_id:
        r = db.query(Receta).filter(Receta.id == prod.receta_id).first()
        if r:
            lineas = db.query(LineaReceta).filter(LineaReceta.receta_id == r.id).all()
            from app.services.costes import costo_receta
            total, porcion = costo_receta(r, db)
            receta_info = {
                "id": r.id,
                "nombre": r.nombre,
                "porciones_por_lote": r.porciones_por_lote,
                "costo_total": round(total, 2),
                "costo_porcion": round(porcion, 2),
                "precio_venta": r.precio_venta,
                "num_ingredientes": len(lineas),
            }

    # Stock actual
    stock_total = (
        db.query(func.coalesce(func.sum(StockCongelado.cantidad), 0))
        .filter(StockCongelado.producto_congelado_id == prod_id, StockCongelado.is_active.is_(True))
        .scalar()
    ) or 0

    # Cumulative stock history from MovimientoStock (shows both production AND consumption)
    stock_history = historial_movimientos_acumulado(db, "congelado", ids=[prod_id]).get(prod_id, [])

    # Recent movements
    movimientos = [
        {
            "id": m.id, "tipo_movimiento": m.tipo_movimiento,
            "cantidad": m.cantidad, "fecha": m.fecha,
            "referencia_origen": m.referencia_origen,
            "nombre_origen": describir_referencia(db, m.referencia_origen),
            "saldo_despues": m.saldo_despues,
        }
        for m in db.query(MovimientoStock)
        .filter(
            MovimientoStock.tipo_stock == "congelado",
            MovimientoStock.referencia_producto_id == prod_id,
            movimiento_no_revertido(),
        )
        .order_by(MovimientoStock.fecha.desc(), MovimientoStock.id.desc())
        .limit(20)
        .all()
    ]

    return {
        "id": prod.id,
        "nombre": prod.nombre,
        "categoria": prod.categoria,
        "unidad": prod.unidad,
        "nivel": prod.nivel,
        "cantidad_por_padre": prod.cantidad_por_padre,
        "stock_actual": stock_total,
        "ancestors": ancestors,
        "padre": padre,
        "hijos": hijos,
        "receta": receta_info,
        "stock_history": stock_history,
        "movimientos": movimientos,
    }


@router.put("/productos/{prod_id}", response_model=ProductoCongeladoOut)
def update_producto_congelado(
    prod_id: int,
    data: ProductoCongeladoUpdate,
    user: User = require_permission("congelados", "edit"),
    db: Session = Depends(get_db),
):
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto congelado no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(prod, k, v)
    db.commit()
    db.refresh(prod)
    return prod


@router.delete("/productos/{prod_id}")
def delete_producto_congelado(
    prod_id: int,
    user: User = require_permission("congelados", "delete"),
    db: Session = Depends(get_db),
):
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto congelado no encontrado")
    if (
        db.query(StockCongelado)
        .filter(StockCongelado.producto_congelado_id == prod_id)
        .count()
        > 0
    ):
        raise HTTPException(status_code=409, detail="Producto tiene stock asociado")
    db.delete(prod)
    db.commit()
    return {"ok": True}


@router.post("/productos/{viejo_id}/fusionar-en/{nuevo_id}")
def fusionar_producto(
    viejo_id: int,
    nuevo_id: int,
    user: User = require_permission("congelados", "edit"),
    db: Session = Depends(get_db),
):
    """Fold a superseded product's stock lots and movement history into its
    replacement, when a product was restructured (renamed, or split across a
    new baston/crudo/terminado chain) and the production calendar was
    pointed at the wrong one for a while -- so real, already-completed
    production doesn't just sit stranded on a product nobody looks at
    anymore.

    Only re-parents `producto_congelado_id`/`referencia_producto_id`
    (StockCongelado, congelado MovimientoStock, RegistroProduccion) --
    never touches materia_prima movements, since the ingredients for that
    production were already correctly deducted once; redoing that would
    double-consume them.
    """
    viejo = db.query(ProductoCongelado).filter(ProductoCongelado.id == viejo_id).first()
    if not viejo:
        raise HTTPException(status_code=404, detail="Producto viejo no encontrado")
    nuevo = db.query(ProductoCongelado).filter(ProductoCongelado.id == nuevo_id).first()
    if not nuevo:
        raise HTTPException(status_code=404, detail="Producto nuevo no encontrado")
    if viejo_id == nuevo_id:
        raise HTTPException(status_code=422, detail="No se puede fusionar un producto consigo mismo")

    lotes = db.query(StockCongelado).filter(StockCongelado.producto_congelado_id == viejo_id).all()
    for lote in lotes:
        lote.producto_congelado_id = nuevo_id

    movimientos = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == "congelado",
        MovimientoStock.referencia_producto_id == viejo_id,
    ).all()
    for mov in movimientos:
        mov.referencia_producto_id = nuevo_id

    registros = db.query(RegistroProduccion).filter(
        RegistroProduccion.producto_congelado_id == viejo_id
    ).all()
    for reg in registros:
        reg.producto_congelado_id = nuevo_id

    db.commit()
    return {
        "lotes_movidos": len(lotes),
        "movimientos_movidos": len(movimientos),
        "registros_produccion_movidos": len(registros),
    }


# ── Stock CRUD  (/api/congelados) ──────────────────────────────────────────────

@router.get("/alertas-vencimiento", response_model=list[StockCongeladoOut])
def alertas_vencimiento(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stock entries already expired or expiring within the next 7 days."""
    cutoff = date.today() + timedelta(days=7)
    entries = (
        db.query(StockCongelado)
        .options(joinedload(StockCongelado.producto))
        .filter(StockCongelado.is_active.is_(True))
        .filter(StockCongelado.fecha_vencimiento.isnot(None))
        .filter(StockCongelado.fecha_vencimiento <= cutoff)
        .order_by(StockCongelado.fecha_vencimiento)
        .all()
    )
    return [_stock_out(e) for e in entries]


@router.get("", response_model=list[StockCongeladoOut])
def list_stock_congelado(
    producto_id: int | None = Query(None),
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(StockCongelado).options(joinedload(StockCongelado.producto))
    if producto_id:
        q = q.filter(StockCongelado.producto_congelado_id == producto_id)
    if fecha_desde:
        q = q.filter(StockCongelado.fecha_entrada >= fecha_desde)
    if fecha_hasta:
        q = q.filter(StockCongelado.fecha_entrada <= fecha_hasta)
    return [_stock_out(e) for e in q.order_by(StockCongelado.fecha_entrada.desc()).all()]


@router.get("/calculado")
def get_stock_calculado(
    fecha_desde: date | None = Query(None),
    fecha_hasta: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculated (ledger) stock over time for every product with movements --
    companion to GET /api/congelados (the manual/physical counts), for the
    Historial pivot table's "physical vs calculated" comparison.

    fecha_desde is NOT used to filter the underlying query: a running balance
    is only correct when computed from full history up to fecha_hasta, so
    trimming to fecha_desde would silently reset the baseline to zero at the
    window edge. It's trimmed for the response instead, keeping the last
    point before fecha_desde as an opening balance so a "nearest date <= X"
    lookup on the frontend still works for dates right at the start of range.
    """
    historial = historial_movimientos_acumulado(db, "congelado", fecha_hasta=fecha_hasta)

    productos_out = []
    for pid, puntos in historial.items():
        if fecha_desde:
            corte = str(fecha_desde)
            antes = [p for p in puntos if p["fecha"] < corte]
            despues = [p for p in puntos if p["fecha"] >= corte]
            puntos = ([antes[-1]] if antes else []) + despues
        productos_out.append({"producto_congelado_id": pid, "historial": puntos})

    return {"productos": productos_out}


@router.post("", response_model=StockCongeladoOut, status_code=201)
def add_stock_congelado(
    data: StockCongeladoCreate,
    user: User = require_permission("congelados", "create"),
    db: Session = Depends(get_db),
):
    entry = StockCongelado(**data.model_dump(exclude_none=True))
    entry.cantidad_original = entry.cantidad
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.refresh(entry, ["producto"])
    return _stock_out(entry)


@router.put("/{entry_id}", response_model=StockCongeladoOut)
def update_stock_congelado(
    entry_id: int,
    data: StockCongeladoUpdate,
    user: User = require_permission("congelados", "edit"),
    db: Session = Depends(get_db),
):
    """Correct a past manual stock count -- a mistyped quantity or a wrong
    date.

    This is a plain record correction: it does NOT touch MovimientoStock
    (see update_inventario's docstring for why edits and the ledger are
    kept independent). A lot created BY a production run
    (registro_produccion_id set) still can't have its quantity/date
    corrected here -- edit the production record itself instead, since its
    stock effect is exactly what that record's own revert/reapply cycle is
    responsible for.

    Correcting `cantidad` also updates `cantidad_original` to match -- that
    field is what the historial pivot's calculado anchors to (see
    _conteos_manuales_por_fecha), and it's meant to always equal "what this
    count actually said" the same way it does at creation. Leaving it stale
    here would mean fixing a mistyped count silently stops applying to
    calculado for every date after it -- the exact case this endpoint exists
    to fix in the first place.
    """
    entry = (
        db.query(StockCongelado)
        .options(joinedload(StockCongelado.producto))
        .filter(StockCongelado.id == entry_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de stock no encontrada")

    updates = data.model_dump(exclude_unset=True)
    cambia_stock = bool({"cantidad", "fecha_entrada"} & updates.keys())

    if cambia_stock and entry.registro_produccion_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Este lote proviene de una produccion -- corregi la produccion, no este lote.",
        )
    if cambia_stock and not es_conteo_manual("congelado", entry.notas):
        raise HTTPException(
            status_code=409,
            detail="Esta entrada fue generada automaticamente -- corregi el origen, no esta entrada.",
        )

    for k, v in updates.items():
        setattr(entry, k, v)
    if "cantidad" in updates:
        entry.cantidad_original = updates["cantidad"]

    db.commit()
    db.refresh(entry)
    return _stock_out(entry)


@router.post("/{entry_id}/sincronizar-ledger")
def sincronizar_ledger(
    entry_id: int,
    user: User = require_permission("congelados", "edit"),
    db: Session = Depends(get_db),
):
    """One-off correction: re-anchor the ledger's carga_inicial baseline to
    this manual count's current (corrected) value.

    Only takes effect when ajustar_correccion_conteo finds the sole ledger
    movement on or before this entry's date is a lone carga_inicial dated
    the same day -- see that function's docstring, and
    inventario.py's identical materia_prima version, for the full guard.

    Uses `cantidad_original`, not `cantidad`: unlike materia_prima's
    InventarioRegistro (an immutable snapshot), a congelado lot's `cantidad`
    is mutated in place by every later FIFO draw, so once any of it has
    been consumed it no longer means "the corrected count" -- it means
    "what's left". Passing that reduced number here would overwrite a
    perfectly correct carga_inicial with the post-consumption remainder
    (found in production against Barra Negra Cocinado's 2026-08-13 lot:
    a real 12-unit entrega had already consumed the lot to 0, and this
    endpoint had rewritten the carga_inicial from 12 down to 0 to match).
    """
    entry = db.query(StockCongelado).filter(StockCongelado.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de stock no encontrada")
    if not es_conteo_manual("congelado", entry.notas):
        raise HTTPException(
            status_code=409,
            detail="Esta entrada no es un conteo manual -- no aplica.",
        )

    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == entry.producto_congelado_id).first()
    valor = entry.cantidad_original if entry.cantidad_original is not None else entry.cantidad
    mov = ajustar_correccion_conteo(
        db,
        tipo_stock="congelado",
        producto_id=entry.producto_congelado_id,
        registro_id=entry.id,
        nueva_cantidad=valor,
        unidad=prod.unidad if prod else "u",
        fecha=entry.fecha_entrada,
        user_id=user.id,
    )
    db.commit()
    return {"ajustado": mov is not None, "movimiento_id": mov.id if mov else None}


@router.delete("/{entry_id}")
def delete_stock_congelado(
    entry_id: int,
    user: User = require_permission("congelados", "delete"),
    db: Session = Depends(get_db),
):
    entry = db.query(StockCongelado).filter(StockCongelado.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de stock no encontrada")
    db.delete(entry)
    db.commit()
    return {"ok": True}
