from datetime import date, timedelta

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
from app.services.stock import (
    TIPOS_CONSUMO_MATERIA_PRIMA,
    conteos_manuales_movimientos,
    conteos_manuales_por_fecha,
    get_saldos_materia_prima,
    historial_movimientos_acumulado,
    orden_visual_dia,
    saldo_despues_por_movimiento,
)

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
    """Stock actual de un ingrediente, leido del LEDGER.

    `stock_actual` salia de la ultima fila de `InventarioRegistro` por
    `(fecha_registro, id)`, que es la cadena de totales guardados que no se
    re-secuencia -- la misma fuente que acaba de dejar de usar el grafico de
    esta misma pantalla. Dejarla aqui ponia la tarjeta de arriba a discrepar
    con el grafico de abajo en cuanto hubiera una carga retroactiva, que es
    rutina (recepciones y producciones se cargan tarde). Medido al cambiarlo:
    discrepaba en 1 de 28 ingredientes (Leche, 23,00 contra 23,50).

    `unidad` y `fecha_ultimo_conteo` siguen saliendo de la fila, que es donde
    viven: el ledger no las tiene.
    """
    latest = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
    )
    saldo = get_saldos_materia_prima(db, [ing_id]).get(ing_id)
    return {
        "stock_actual": saldo if saldo is not None else (latest.cantidad if latest else 0),
        "unidad": latest.unidad if latest else "",
        "fecha_ultimo_conteo": str(latest.fecha_registro) if latest else None,
    }


@router.get("/{ing_id}/evolucion")
def get_evolucion_ingrediente(
    ing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stock over time + rolling 7-day consumption, both from the LEDGER.

    Exists because the ingredient detail chart used to be built in the browser
    from `GET /api/inventario?ingrediente_id=`, i.e. raw `InventarioRegistro`
    rows, and those are stored absolute totals that never re-sequence. A
    consumption logged late but dated in the past chains off whatever row was
    the tip at write time (`get_saldo_materia_prima` orders by
    `fecha_registro, id`), so as a time series the column is simply wrong --
    see "Two parallel ways to read materia prima stock" in CLAUDE.md.

    Measured on production the day this was written: the chart had Manteca at
    -25,3 kg on 19/10 where the ledger says 5,10, because the reception row for
    pedido #92 got a higher id than the production that preceded it. Harina 000
    showed 1.022,8 kg on 21/10 -- three days before the 1.025 kg actually
    arrived. The movements table right below the chart disagreed with it on the
    same screen, because that one replays the ledger via
    `saldo_despues_por_movimiento`.

    The consumption figure is a trailing 7-day window at each point rather than
    calendar weeks, so it stays one value per stock point and the bars keep
    sharing the line's x axis. It nets `produccion_consumo` + `merma` rather
    than summing only negatives: a reversal keeps the tipo_movimiento of what
    it cancels (see `revertir_consumos`), so netting makes a reverted pair
    cancel out, where summing negatives would count the original twice.

    NOT reused for `/api/inventario/recomendacion`'s par level, which has its
    own snapshot-walking estimate that over-counts 2-6x. CLAUDE.md records that
    as a deliberate leave-alone (an inflated par orders too much, the safe
    direction), so changing it is a separate decision, not a drive-by.
    """
    ing = db.query(Ingrediente).filter(Ingrediente.id == ing_id).first()
    if not ing:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado")

    puntos = historial_movimientos_acumulado(db, "materia_prima", ids=[ing_id]).get(ing_id, [])

    # El conteo fisico va como segunda serie, misma convencion que los pivots de
    # /stock y /congelados ("calculado (contado)"). Sin el, el ultimo punto del
    # grafico parece pelearse con la tarjeta "Stock actual" de arriba: esta
    # aplica el conteo de HOY (get_saldos_materia_prima) mientras que
    # historial_movimientos_acumulado mantiene a proposito la trayectoria
    # PRE-conteo en el dia del propio conteo, y solo re-ancla al dia siguiente.
    # Medido al montarlo: Harina 000 daba tarjeta 1.046,8 contra un ultimo punto
    # de 1.049,0. Esos 2,2 kg son una discrepancia real que hay que ver, no un
    # fallo que tapar -- pero hay que poder verla, no deducirla.
    conteos = conteos_manuales_por_fecha(db, "materia_prima", [ing_id]).get(ing_id, {})

    salidas: dict[str, float] = {}
    for m in (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.tipo_stock == "materia_prima",
            MovimientoStock.referencia_producto_id == ing_id,
            MovimientoStock.tipo_movimiento.in_(TIPOS_CONSUMO_MATERIA_PRIMA),
        )
        .all()
    ):
        salidas[str(m.fecha)] = salidas.get(str(m.fecha), 0.0) + m.cantidad

    # Un conteo puede caer en una fecha sin movimientos, asi que el eje son las
    # fechas del ledger MAS las de los conteos. Un solo bucle sobre la union:
    # calcular los dias de conteo aparte dejaba su ventana de consumo en 0
    # cuando si hubo gasto en esos 7 dias.
    saldos = {p["fecha"]: p["cantidad"] for p in puntos}
    out = []
    for f in sorted(set(saldos) | set(conteos)):
        hasta = date.fromisoformat(f)
        desde = hasta - timedelta(days=6)
        consumo = -sum(c for fm, c in salidas.items() if str(desde) <= fm <= str(hasta))
        saldo = saldos.get(f)
        conteo = conteos.get(f)
        out.append({
            "fecha": f,
            "cantidad": round(saldo, 3) if saldo is not None else None,
            # Clamped at zero only for display: a window whose net is positive
            # means a reversal landed in it, not that stock was created.
            "consumo_7d": round(max(0.0, consumo), 2),
            "contado": round(conteo, 3) if conteo is not None else None,
        })

    return {"unidad": ing.unidad_uso, "puntos": out}


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
    movimientos = [
        {
            "id": m.id,
            "tipo_movimiento": m.tipo_movimiento,
            "cantidad": m.cantidad,
            "unidad": m.unidad,
            "fecha": str(m.fecha),
            "referencia_origen": m.referencia_origen,
            "nombre_origen": nombre_origen_movimiento(db, m),
            "saldo_despues": saldos_vivos.get(m.id, m.saldo_despues),
        }
        for m in movs
    ]
    conteos = conteos_manuales_movimientos(db, "materia_prima", ing_id, limit=10)
    return sorted(
        movimientos + conteos,
        key=lambda m: (m["fecha"], orden_visual_dia(m["tipo_movimiento"])),
        reverse=True,
    )[:30]
