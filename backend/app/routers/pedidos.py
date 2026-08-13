from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import HistorialPrecio, Ingrediente, InventarioRegistro, LineaPedido, MovimientoStock, Pedido, Proveedor, User
from app.services.stock import get_saldo_materia_prima, registrar_movimiento
from app.permissions import require_permission
from app.schemas import (
    LineaPedidoIn,
    LineaPedidoOut,
    PedidoCreate,
    PedidoOut,
    PedidoUpdate,
)

router = APIRouter(prefix="/api/pedidos", tags=["pedidos"])


def _linea_out(linea: LineaPedido) -> dict:
    return {
        "id": linea.id,
        "pedido_id": linea.pedido_id,
        "ingrediente_id": linea.ingrediente_id,
        "cantidad_pedida": linea.cantidad_pedida,
        "unidad": linea.unidad,
        "cantidad_recibida": linea.cantidad_recibida,
        "precio_unitario": linea.precio_unitario,
    }


def _load_pedido(db: Session, pedido_id: int) -> Pedido:
    """Re-query a pedido with all relationships eagerly loaded."""
    return (
        db.query(Pedido)
        .options(joinedload(Pedido.proveedor_rel), joinedload(Pedido.lineas))
        .filter(Pedido.id == pedido_id)
        .first()
    )


def _pedido_out(p: Pedido) -> dict:
    return {
        "id": p.id,
        "fecha": p.fecha,
        "proveedor_id": p.proveedor_id,
        "proveedor_nombre": p.proveedor_rel.nombre if p.proveedor_rel else "",
        "estado": p.estado,
        "notas": p.notas,
        "fecha_recepcion": p.fecha_recepcion,
        "lineas": [_linea_out(l) for l in (p.lineas or [])],
    }


# ── Collection routes ──────────────────────────────────────────────────────────

@router.get("", response_model=list[PedidoOut])
def list_pedidos(
    estado: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Pedido).options(joinedload(Pedido.proveedor_rel), joinedload(Pedido.lineas))
    if estado:
        q = q.filter(Pedido.estado == estado)
    return [_pedido_out(p) for p in q.order_by(Pedido.fecha.desc()).all()]


@router.post("", response_model=PedidoOut, status_code=201)
def create_pedido(
    data: PedidoCreate,
    user: User = require_permission("pedidos_proveedores", "create"),
    db: Session = Depends(get_db),
):
    if not db.query(Proveedor).filter(Proveedor.id == data.proveedor_id).first():
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    p = Pedido(
        proveedor_id=data.proveedor_id,
        fecha=data.fecha or date.today(),
        estado="borrador",
        notas=data.notas,
        fecha_recepcion=data.fecha_recepcion,
    )
    db.add(p)
    db.flush()
    for linea_data in data.lineas:
        ld = linea_data.model_dump()
        if not ld.get("precio_unitario"):
            ing = db.query(Ingrediente).filter(Ingrediente.id == ld["ingrediente_id"]).first()
            if ing and ing.precio_compra:
                ld["precio_unitario"] = ing.precio_compra
        linea = LineaPedido(pedido_id=p.id, **ld)
        db.add(linea)
    db.commit()
    p = _load_pedido(db, p.id)
    return _pedido_out(p)


# ── Item routes ────────────────────────────────────────────────────────────────

@router.get("/{pedido_id}", response_model=PedidoOut)
def get_pedido(
    pedido_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = _load_pedido(db, pedido_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return _pedido_out(p)


@router.put("/{pedido_id}", response_model=PedidoOut)
def update_pedido(
    pedido_id: int,
    data: PedidoUpdate,
    user: User = require_permission("pedidos_proveedores", "edit"),
    db: Session = Depends(get_db),
):
    p = _load_pedido(db, pedido_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    for key, val in data.model_dump(exclude_unset=True, exclude={"lineas"}).items():
        setattr(p, key, val)
    if data.lineas is not None:
        for linea in list(p.lineas):
            db.delete(linea)
        db.flush()
        for linea_data in data.lineas:
            db.add(LineaPedido(pedido_id=p.id, **linea_data.model_dump()))
    db.commit()
    p = _load_pedido(db, pedido_id)
    return _pedido_out(p)


@router.delete("/{pedido_id}")
def delete_pedido(
    pedido_id: int,
    user: User = require_permission("pedidos_proveedores", "delete"),
    db: Session = Depends(get_db),
):
    p = _load_pedido(db, pedido_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if p.estado == "recibido":
        ref = f"pedido:{pedido_id}"
        for linea in p.lineas:
            cantidad = linea.cantidad_recibida if linea.cantidad_recibida is not None else linea.cantidad_pedida
            saldo_actual = get_saldo_materia_prima(db, linea.ingrediente_id)
            nuevo_saldo = saldo_actual - cantidad
            db.add(InventarioRegistro(
                ingrediente_id=linea.ingrediente_id,
                cantidad=nuevo_saldo,
                unidad=linea.unidad,
                fecha_registro=date.today(),
                notas=f"Pedido #{pedido_id} eliminado (-{cantidad})",
            ))
            registrar_movimiento(
                db, "materia_prima", linea.ingrediente_id, -cantidad,
                linea.unidad, "correccion", f"pedido_borrado:{pedido_id}", nuevo_saldo, user.id,
            )
        db.query(MovimientoStock).filter(MovimientoStock.referencia_origen == ref).delete()

    db.delete(p)
    db.commit()
    return {"ok": True}


# ── Status transitions ─────────────────────────────────────────────────────────

@router.post("/{pedido_id}/enviar", response_model=PedidoOut)
def enviar_pedido(
    pedido_id: int,
    user: User = require_permission("pedidos_proveedores", "edit"),
    db: Session = Depends(get_db),
):
    """Transition: borrador → enviado."""
    p = _load_pedido(db, pedido_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if p.estado != "borrador":
        raise HTTPException(status_code=409, detail="El pedido debe estar en borrador para enviarse")
    p.estado = "enviado"
    db.commit()
    p = _load_pedido(db, pedido_id)
    return _pedido_out(p)


class _LineaRecepcion(BaseModel):
    linea_id: int
    cantidad_recibida: float
    precio_unitario: float | None = None


class _RecepcionRequest(BaseModel):
    lineas: list[_LineaRecepcion] = []


@router.post("/{pedido_id}/recibir", response_model=PedidoOut)
def recibir_pedido(
    pedido_id: int,
    data: _RecepcionRequest | None = None,
    user: User = require_permission("pedidos_proveedores", "edit"),
    db: Session = Depends(get_db),
):
    """Transition: enviado → recibido. Accepts optional received quantities per line."""
    p = _load_pedido(db, pedido_id)
    if not p:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if p.estado != "enviado":
        raise HTTPException(status_code=409, detail="El pedido debe estar enviado para recibirse")

    recepcion_map = {}
    if data and data.lineas:
        for lr in data.lineas:
            recepcion_map[lr.linea_id] = lr

    p.estado = "recibido"
    p.fecha_recepcion = date.today()
    for linea in p.lineas:
        rec = recepcion_map.get(linea.id)
        if rec:
            linea.cantidad_recibida = rec.cantidad_recibida
            if rec.precio_unitario is not None:
                linea.precio_unitario = rec.precio_unitario
        cantidad_recibida = (
            linea.cantidad_recibida
            if linea.cantidad_recibida is not None
            else linea.cantidad_pedida
        )
        saldo_actual = get_saldo_materia_prima(db, linea.ingrediente_id)
        nuevo_saldo = saldo_actual + cantidad_recibida
        db.add(InventarioRegistro(
            ingrediente_id=linea.ingrediente_id,
            cantidad=nuevo_saldo,
            unidad=linea.unidad,
            fecha_registro=date.today(),
            notas=f"Pedido #{pedido_id} recibido (+{cantidad_recibida})",
        ))
        registrar_movimiento(
            db, "materia_prima", linea.ingrediente_id, +cantidad_recibida,
            linea.unidad, "recepcion", f"pedido:{pedido_id}", nuevo_saldo, user.id,
        )
        if linea.precio_unitario:
            ing = db.query(Ingrediente).filter(Ingrediente.id == linea.ingrediente_id).first()
            if ing and ing.precio_compra != linea.precio_unitario:
                db.add(HistorialPrecio(
                    ingrediente_id=ing.id,
                    precio_anterior=ing.precio_compra,
                    precio_nuevo=linea.precio_unitario,
                    fecha_cambio=date.today(),
                ))
                ing.precio_compra = linea.precio_unitario
                ing.fecha_actualizacion = date.today()
    db.commit()
    p = _load_pedido(db, pedido_id)
    return _pedido_out(p)


# ── Line-level endpoints ───────────────────────────────────────────────────────

@router.post("/{pedido_id}/lineas", response_model=LineaPedidoOut, status_code=201)
def add_linea(
    pedido_id: int,
    data: LineaPedidoIn,
    user: User = require_permission("pedidos_proveedores", "edit"),
    db: Session = Depends(get_db),
):
    if not db.query(Pedido).filter(Pedido.id == pedido_id).first():
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    linea = LineaPedido(pedido_id=pedido_id, **data.model_dump())
    db.add(linea)
    db.commit()
    db.refresh(linea)
    return _linea_out(linea)


@router.put("/{pedido_id}/lineas/{linea_id}", response_model=LineaPedidoOut)
def update_linea(
    pedido_id: int,
    linea_id: int,
    data: LineaPedidoIn,
    user: User = require_permission("pedidos_proveedores", "edit"),
    db: Session = Depends(get_db),
):
    linea = (
        db.query(LineaPedido)
        .filter(LineaPedido.id == linea_id, LineaPedido.pedido_id == pedido_id)
        .first()
    )
    if not linea:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(linea, key, val)
    db.commit()
    db.refresh(linea)
    return _linea_out(linea)


@router.delete("/{pedido_id}/lineas/{linea_id}")
def delete_linea(
    pedido_id: int,
    linea_id: int,
    user: User = require_permission("pedidos_proveedores", "delete"),
    db: Session = Depends(get_db),
):
    linea = (
        db.query(LineaPedido)
        .filter(LineaPedido.id == linea_id, LineaPedido.pedido_id == pedido_id)
        .first()
    )
    if not linea:
        raise HTTPException(status_code=404, detail="Línea no encontrada")
    db.delete(linea)
    db.commit()
    return {"ok": True}
