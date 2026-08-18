from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from pydantic import BaseModel

from app.models import (
    Ingrediente,
    LineaReceta,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    TareaProduccion,
    User,
)
from app.services.produccion_registro import aplicar_efectos, revertir_efectos
from app.permissions import require_permission
from app.schemas import (
    RegistroExtraCreate,
    RegistroExtraUpdate,
    RegistroProduccionCreate,
    RegistroProduccionOut,
    TareaProduccionCreate,
    TareaProduccionOut,
    TareaProduccionUpdate,
)

router = APIRouter(prefix="/api/produccion", tags=["produccion"])


def _necesita_bastones(db: Session, producto_congelado_id: int | None) -> bool:
    if not producto_congelado_id:
        return False
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == producto_congelado_id).first()
    if not prod or not prod.producto_padre_id:
        return False
    padre = db.query(ProductoCongelado).filter(ProductoCongelado.id == prod.producto_padre_id).first()
    return padre is not None and padre.nivel == "semi" and "baston" in padre.nombre.lower()

DIAS = {1: "Lunes", 2: "Martes", 3: "Miercoles", 4: "Jueves", 5: "Viernes", 6: "Sabado"}


def _tarea_to_out(t: TareaProduccion) -> dict:
    return {
        "id": t.id,
        "dia_semana": t.dia_semana,
        "hora": t.hora,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "duracion_minutos": t.duracion_minutos,
        "cantidad_planificada": t.cantidad_planificada,
        "unidad_cantidad": t.unidad_cantidad,
        "receta_id": t.receta_id,
        "receta_nombre": t.receta.nombre if t.receta else None,
        "producto_congelado_id": t.producto_congelado_id,
        "tipo": t.tipo,
        "posicion": t.posicion,
        "is_active": t.is_active,
    }


def _registro_to_out(r: RegistroProduccion, movimientos: int = 0, stock_aplicado: bool = False) -> dict:
    return {
        "id": r.id,
        "tarea_id": r.tarea_id,
        "fecha": r.fecha.isoformat(),
        "completada": r.completada,
        "cantidad_real": r.cantidad_real,
        "duracion_real": r.duracion_real,
        "notas": r.notas,
        "titulo_extra": r.titulo_extra,
        "unidad_extra": r.unidad_extra,
        "receta_id": r.receta_id,
        "receta_nombre": r.receta.nombre if r.receta else None,
        "producto_congelado_id": r.producto_congelado_id,
        "bastones_consumidos": r.bastones_consumidos,
        "stock_aplicado": stock_aplicado,
        "movimientos": movimientos,
        "registrado_por": r.registrado_por,
        "registrado_at": r.registrado_at,
    }


# ==============================================================
# Calendar — weekly plan grouped by day
# ==============================================================


@router.get("/productos-dropdown")
def get_productos_dropdown(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All recipes (escandallos) for the extras dropdown."""
    recetas = (
        db.query(Receta)
        .filter(Receta.es_subreceta == False)
        .order_by(Receta.nombre)
        .all()
    )
    return [
        {"id": r.id, "nombre": r.nombre, "porciones_por_lote": r.porciones_por_lote}
        for r in recetas
    ]


@router.get("/calendario")
def get_calendario(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tareas = (
        db.query(TareaProduccion)
        .filter(TareaProduccion.is_active == True)
        .order_by(TareaProduccion.dia_semana, TareaProduccion.hora, TareaProduccion.posicion)
        .all()
    )
    result: dict = {}
    for dia_num, dia_nombre in DIAS.items():
        result[str(dia_num)] = {"nombre": dia_nombre, "tareas": []}
    for t in tareas:
        key = str(t.dia_semana)
        if key in result:
            result[key]["tareas"].append(_tarea_to_out(t))
    return result


# ==============================================================
# Day view — planned tasks + registrations for a specific date
# ==============================================================


def _preview_consumo(db: Session, t: TareaProduccion) -> dict:
    """Portions per unit typed, plus the heaviest ingredient line, for the UI preview."""
    empty = {"porciones_por_lote": None, "ingrediente_principal": None}
    if not t.receta_id:
        return empty

    receta = db.query(Receta).filter(Receta.id == t.receta_id).first()
    if not receta:
        return empty

    lineas = (
        db.query(LineaReceta)
        .filter(LineaReceta.receta_id == receta.id, LineaReceta.ingrediente_id.isnot(None))
        .all()
    )
    principal = None
    if lineas:
        mayor = max(lineas, key=lambda x: x.cantidad)
        ing = db.query(Ingrediente).filter(Ingrediente.id == mayor.ingrediente_id).first()
        if ing:
            principal = {
                "nombre": ing.nombre,
                "cantidad_por_receta": mayor.cantidad,
                "unidad": mayor.unidad,
            }

    return {
        "porciones_por_lote": receta.porciones_por_lote,
        "ingrediente_principal": principal,
    }


@router.get("/dia")
def get_dia(
    fecha: str = Query(..., description="ISO date YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha invalido")

    dow = d.isoweekday()
    if dow > 6:
        dow = 6

    tareas = (
        db.query(TareaProduccion)
        .filter(TareaProduccion.dia_semana == dow, TareaProduccion.is_active == True)
        .order_by(TareaProduccion.hora, TareaProduccion.posicion)
        .all()
    )

    registros = (
        db.query(RegistroProduccion)
        .filter(RegistroProduccion.fecha == d)
        .all()
    )
    reg_by_tarea = {r.tarea_id: r for r in registros if r.tarea_id is not None}
    extras = [r for r in registros if r.tarea_id is None]

    items = []
    for t in tareas:
        reg = reg_by_tarea.get(t.id)
        items.append({
            "tarea_id": t.id,
            "hora": t.hora,
            "titulo": t.titulo,
            "descripcion": t.descripcion,
            "duracion_planificada": t.duracion_minutos,
            "cantidad_planificada": t.cantidad_planificada,
            "unidad_cantidad": t.unidad_cantidad,
            "receta_id": t.receta_id,
            "receta_nombre": t.receta.nombre if t.receta else None,
            "producto_congelado_id": t.producto_congelado_id,
            "necesita_bastones": _necesita_bastones(db, t.producto_congelado_id),
            "tipo": t.tipo,
            "registro_id": reg.id if reg else None,
            "completada": reg.completada if reg else False,
            "cantidad_real": reg.cantidad_real if reg else None,
            "duracion_real": reg.duracion_real if reg else None,
            "notas": reg.notas if reg else None,
            "bastones_consumidos": reg.bastones_consumidos if reg else None,
            # Lets the screen show what one unit will consume, so the operator can
            # sanity-check the deduction before committing to it.
            **_preview_consumo(db, t),
        })

    extras_out = []
    for r in extras:
        prod_extra = (
            db.query(ProductoCongelado).filter(ProductoCongelado.id == r.producto_congelado_id).first()
            if r.producto_congelado_id else None
        )
        extras_out.append({
            "registro_id": r.id,
            "titulo": r.receta.nombre if r.receta else r.titulo_extra,
            "receta_id": r.receta_id,
            "producto_congelado_id": r.producto_congelado_id,
            "unidad_cantidad": r.unidad_extra or (prod_extra.unidad if prod_extra else None),
            "necesita_bastones": _necesita_bastones(db, r.producto_congelado_id),
            "completada": r.completada,
            "cantidad_real": r.cantidad_real,
            "duracion_real": r.duracion_real,
            "bastones_consumidos": r.bastones_consumidos,
            "notas": r.notas,
        })

    return {
        "fecha": fecha,
        "dia_semana": dow,
        "dia_nombre": DIAS.get(dow, ""),
        "tareas": items,
        "extras": extras_out,
    }


# ==============================================================
# Registration — log production for a planned task
# ==============================================================


@router.post("/registro", response_model=RegistroProduccionOut, status_code=201)
def upsert_registro(
    data: RegistroProduccionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a production record and bring stock in line with it, atomically.

    Saving is the only thing that moves stock. Re-saving an existing record reverses
    whatever it moved before and re-applies from the new values, so correcting 1 to 2
    leaves stock at 2 rather than 3.
    """
    tarea = db.query(TareaProduccion).filter(TareaProduccion.id == data.tarea_id).first()
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # A task tied to a product cannot be completed without a quantity — that is the
    # bug this endpoint exists to kill. Silently skipping the deduction is not an option.
    if data.completada and tarea.producto_congelado_id:
        if data.cantidad_real is None or data.cantidad_real <= 0:
            raise HTTPException(
                status_code=422,
                detail="Ingresa la cantidad producida antes de guardar esta tarea.",
            )

    reg = (
        db.query(RegistroProduccion)
        .filter(
            RegistroProduccion.tarea_id == data.tarea_id,
            RegistroProduccion.fecha == data.fecha,
        )
        .first()
    )

    if reg:
        # Undo the previous effects before overwriting the values they were based on.
        revertir_efectos(db, reg, user.id)
        reg.completada = data.completada
        reg.cantidad_real = data.cantidad_real
        reg.duracion_real = data.duracion_real
        reg.notas = data.notas
        reg.bastones_consumidos = data.bastones_consumidos
    else:
        reg = RegistroProduccion(
            tarea_id=data.tarea_id,
            fecha=data.fecha,
            completada=data.completada,
            cantidad_real=data.cantidad_real,
            duracion_real=data.duracion_real,
            notas=data.notas,
            bastones_consumidos=data.bastones_consumidos,
            registrado_por=user.id,
        )
        db.add(reg)
        db.flush()  # need reg.id for the movement tag

    movimientos = aplicar_efectos(db, reg, user.id)

    db.commit()
    db.refresh(reg)
    return _registro_to_out(reg, movimientos, movimientos > 0)


@router.post("/registro/extra", response_model=RegistroProduccionOut, status_code=201)
def create_extra(
    data: RegistroExtraCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receta = db.query(Receta).filter(Receta.id == data.receta_id).first()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    if data.cantidad_real is None or data.cantidad_real <= 0:
        raise HTTPException(status_code=422, detail="Ingresa la cantidad producida.")

    reg = RegistroProduccion(
        tarea_id=None,
        fecha=data.fecha,
        completada=True,
        cantidad_real=data.cantidad_real,
        duracion_real=data.duracion_real,
        notas=data.notas,
        receta_id=data.receta_id,
        titulo_extra=receta.nombre,
        bastones_consumidos=data.bastones_consumidos,
        registrado_por=user.id,
    )
    db.add(reg)
    db.flush()

    movimientos = aplicar_efectos(db, reg, user.id)

    db.commit()
    db.refresh(reg)
    return _registro_to_out(reg, movimientos, movimientos > 0)


@router.put("/registro/{registro_id}", response_model=RegistroProduccionOut)
def update_registro(
    registro_id: int,
    data: RegistroExtraUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edit an existing record in place, keyed by its own id.

    /registro's upsert keys off (tarea_id, fecha), which "produccion extra"
    records don't have -- they carry no tarea_id at all. This is what lets an
    extra be corrected the same way a planned task is, instead of only
    delete-and-recreate.
    """
    reg = db.query(RegistroProduccion).filter(RegistroProduccion.id == registro_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if data.cantidad_real is None or data.cantidad_real <= 0:
        raise HTTPException(status_code=422, detail="Ingresa la cantidad producida.")

    revertir_efectos(db, reg, user.id)
    reg.cantidad_real = data.cantidad_real
    reg.duracion_real = data.duracion_real
    reg.notas = data.notas
    reg.bastones_consumidos = data.bastones_consumidos

    movimientos = aplicar_efectos(db, reg, user.id)

    db.commit()
    db.refresh(reg)
    return _registro_to_out(reg, movimientos, movimientos > 0)


@router.delete("/registro/{registro_id}")
def delete_registro(
    registro_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reg = db.query(RegistroProduccion).filter(RegistroProduccion.id == registro_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    # Give the ingredients back before the record that explains them disappears.
    revertidos = revertir_efectos(db, reg, user.id)

    db.delete(reg)
    db.commit()
    return {"ok": True, "movimientos_revertidos": revertidos}


# ==============================================================
# Analytics
# ==============================================================


@router.get("/analytics")
def get_analytics(
    desde: str = Query(..., description="Start date YYYY-MM-DD"),
    hasta: str = Query(..., description="End date YYYY-MM-DD"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        d_desde = date.fromisoformat(desde)
        d_hasta = date.fromisoformat(hasta)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha invalido")

    all_dates: list[date] = []
    cur = d_desde
    while cur <= d_hasta:
        if cur.isoweekday() <= 6:
            all_dates.append(cur)
        cur += timedelta(days=1)

    registros = (
        db.query(RegistroProduccion)
        .filter(
            RegistroProduccion.fecha >= d_desde,
            RegistroProduccion.fecha <= d_hasta,
            RegistroProduccion.tarea_id != None,
        )
        .all()
    )
    reg_set = {(r.tarea_id, r.fecha): r for r in registros}

    tareas_by_day: dict[int, list[TareaProduccion]] = {}
    all_tareas = (
        db.query(TareaProduccion)
        .filter(TareaProduccion.is_active == True, TareaProduccion.tipo == "produccion")
        .all()
    )
    for t in all_tareas:
        tareas_by_day.setdefault(t.dia_semana, []).append(t)

    total_planned = 0
    total_completed = 0
    por_dia = []
    tarea_stats: dict[int, dict] = {}

    for d in all_dates:
        dow = d.isoweekday()
        day_tareas = tareas_by_day.get(dow, [])
        day_planned = len(day_tareas)
        day_completed = 0

        for t in day_tareas:
            reg = reg_set.get((t.id, d))
            if t.id not in tarea_stats:
                tarea_stats[t.id] = {
                    "tarea_id": t.id,
                    "titulo": t.titulo,
                    "cantidad_planificada": t.cantidad_planificada,
                    "unidad_cantidad": t.unidad_cantidad,
                    "duracion_planificada": t.duracion_minutos,
                    "veces_planificada": 0,
                    "veces_completada": 0,
                    "cantidades": [],
                    "duraciones": [],
                }
            tarea_stats[t.id]["veces_planificada"] += 1

            if reg and reg.completada:
                day_completed += 1
                tarea_stats[t.id]["veces_completada"] += 1
                if reg.cantidad_real is not None:
                    tarea_stats[t.id]["cantidades"].append(reg.cantidad_real)
                if reg.duracion_real is not None:
                    tarea_stats[t.id]["duraciones"].append(reg.duracion_real)

        total_planned += day_planned
        total_completed += day_completed

        if day_planned > 0:
            por_dia.append({
                "fecha": d.isoformat(),
                "dia_nombre": DIAS.get(dow, ""),
                "planificadas": day_planned,
                "completadas": day_completed,
                "porcentaje": round(day_completed / day_planned * 100, 1),
            })

    por_tarea = []
    for stats in tarea_stats.values():
        cantidades = stats.pop("cantidades")
        duraciones = stats.pop("duraciones")
        stats["cantidad_promedio"] = round(sum(cantidades) / len(cantidades), 1) if cantidades else None
        stats["duracion_promedio"] = round(sum(duraciones) / len(duraciones), 1) if duraciones else None
        por_tarea.append(stats)

    return {
        "resumen": {
            "total_planificadas": total_planned,
            "total_completadas": total_completed,
            "porcentaje_cumplimiento": round(total_completed / total_planned * 100, 1) if total_planned else 0,
            "dias_registrados": len(por_dia),
        },
        "por_dia": por_dia,
        "por_tarea": sorted(por_tarea, key=lambda x: x["titulo"]),
    }


# ==============================================================
# Plan tasks — CRUD (admin-only for write)
# ==============================================================


@router.get("/tareas", response_model=list[TareaProduccionOut])
def list_tareas(
    dia_semana: Optional[int] = Query(None),
    tipo: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(TareaProduccion)
    if dia_semana is not None:
        q = q.filter(TareaProduccion.dia_semana == dia_semana)
    if tipo is not None:
        q = q.filter(TareaProduccion.tipo == tipo)
    rows = q.order_by(
        TareaProduccion.dia_semana, TareaProduccion.hora, TareaProduccion.posicion,
    ).all()
    return [_tarea_to_out(t) for t in rows]


@router.get("/tareas/{tarea_id}", response_model=TareaProduccionOut)
def get_tarea(
    tarea_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = db.query(TareaProduccion).filter(TareaProduccion.id == tarea_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return _tarea_to_out(t)


@router.post("/tareas", response_model=TareaProduccionOut, status_code=201)
def create_tarea(
    data: TareaProduccionCreate,
    user: User = require_permission("produccion", "create"),
    db: Session = Depends(get_db),
):
    t = TareaProduccion(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return _tarea_to_out(t)


@router.put("/tareas/{tarea_id}", response_model=TareaProduccionOut)
def update_tarea(
    tarea_id: int,
    data: TareaProduccionUpdate,
    user: User = require_permission("produccion", "edit"),
    db: Session = Depends(get_db),
):
    t = db.query(TareaProduccion).filter(TareaProduccion.id == tarea_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(t, key, val)
    db.commit()
    db.refresh(t)
    return _tarea_to_out(t)


@router.delete("/tareas/{tarea_id}")
def delete_tarea(
    tarea_id: int,
    user: User = require_permission("produccion", "delete"),
    db: Session = Depends(get_db),
):
    t = db.query(TareaProduccion).filter(TareaProduccion.id == tarea_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.delete(t)
    db.commit()
    return {"ok": True}


# ==============================================================
# Multi-level production (new system)
# ==============================================================


class ProduccionRequest(BaseModel):
    producto_id: int
    cantidad_producida: float
    bastones_consumidos: Optional[float] = None
    fecha: Optional[str] = None
    duracion_real: Optional[int] = None
    notas: Optional[str] = None


@router.post("/producir", status_code=201)
def producir(
    data: ProduccionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prod = db.query(ProductoCongelado).filter(ProductoCongelado.id == data.producto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if data.cantidad_producida is None or data.cantidad_producida <= 0:
        raise HTTPException(status_code=422, detail="Ingresa la cantidad producida.")

    from datetime import date as date_type
    fecha = date_type.fromisoformat(data.fecha) if data.fecha else date.today()

    # Every stock movement gets an editable record behind it, so this production can
    # be corrected or undone later like any other.
    reg = RegistroProduccion(
        tarea_id=None,
        fecha=fecha,
        completada=True,
        cantidad_real=data.cantidad_producida,
        duracion_real=data.duracion_real,
        notas=data.notas,
        receta_id=prod.receta_id,
        titulo_extra=prod.nombre,
        producto_congelado_id=prod.id,
        bastones_consumidos=data.bastones_consumidos,
        registrado_por=user.id,
    )
    db.add(reg)
    db.flush()

    movimientos = aplicar_efectos(db, reg, user.id)
    db.commit()

    return {
        "ok": True,
        "producto": prod.nombre,
        "cantidad": data.cantidad_producida,
        "registro_id": reg.id,
        "movimientos": movimientos,
    }
