from datetime import date, datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text as sa_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    pin_hash: Mapped[str] = mapped_column(sa.String(200))
    role: Mapped[str] = mapped_column(sa.String(20), default="staff")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(200))
    nombre: Mapped[str] = mapped_column(sa.String(200))
    telefono: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(sa.String(20))
    module: Mapped[str] = mapped_column(sa.String(50))
    action: Mapped[str] = mapped_column(sa.String(20))
    allowed: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))

    __table_args__ = (
        UniqueConstraint("role", "module", "action", name="uq_permission"),
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(100), unique=True)
    tipo: Mapped[str] = mapped_column(sa.String(20))
    margen_objetivo: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    orden: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True, default=0)

    ingredientes: Mapped[list["Ingrediente"]] = relationship(back_populates="categoria_rel")
    recetas: Mapped[list["Receta"]] = relationship(back_populates="categoria_rel")


class Ingrediente(Base):
    __tablename__ = "ingredientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    unidad_compra: Mapped[str] = mapped_column(sa.String(20))
    cantidad_compra: Mapped[float] = mapped_column(sa.Float)
    precio_compra: Mapped[float] = mapped_column(sa.Float)
    unidad_uso: Mapped[str] = mapped_column(sa.String(20))
    merma_porcentaje: Mapped[float] = mapped_column(sa.Float, default=0.0)
    proveedor: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    activo: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    fecha_actualizacion: Mapped[date] = mapped_column(sa.Date, default=date.today)

    categoria_rel: Mapped["Categoria"] = relationship(back_populates="ingredientes")
    historial_precios: Mapped[list["HistorialPrecio"]] = relationship(
        back_populates="ingrediente_rel", cascade="all, delete-orphan"
    )
    lineas_receta: Mapped[list["LineaReceta"]] = relationship(
        back_populates="ingrediente_rel", foreign_keys="LineaReceta.ingrediente_id"
    )


class HistorialPrecio(Base):
    __tablename__ = "historial_precios"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingrediente_id: Mapped[int] = mapped_column(ForeignKey("ingredientes.id"))
    precio_anterior: Mapped[float] = mapped_column(sa.Float)
    precio_nuevo: Mapped[float] = mapped_column(sa.Float)
    fecha_cambio: Mapped[date] = mapped_column(sa.Date, default=date.today)

    ingrediente_rel: Mapped["Ingrediente"] = relationship(back_populates="historial_precios")


class Receta(Base):
    __tablename__ = "recetas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    porciones_por_lote: Mapped[float] = mapped_column(sa.Float, default=1)
    precio_venta: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    es_subreceta: Mapped[bool] = mapped_column(default=False)
    unidad_rendimiento: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    fecha_modificacion: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    categoria_rel: Mapped["Categoria"] = relationship(back_populates="recetas")
    lineas: Mapped[list["LineaReceta"]] = relationship(
        back_populates="receta_rel", cascade="all, delete-orphan", foreign_keys="LineaReceta.receta_id"
    )
    lineas_como_subreceta: Mapped[list["LineaReceta"]] = relationship(
        back_populates="subreceta_rel", foreign_keys="LineaReceta.subreceta_id"
    )


class LineaReceta(Base):
    __tablename__ = "lineas_receta"

    id: Mapped[int] = mapped_column(primary_key=True)
    receta_id: Mapped[int] = mapped_column(ForeignKey("recetas.id"))
    ingrediente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingredientes.id"), nullable=True)
    subreceta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    cantidad: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))

    receta_rel: Mapped["Receta"] = relationship(back_populates="lineas", foreign_keys=[receta_id])
    ingrediente_rel: Mapped[Optional["Ingrediente"]] = relationship(
        back_populates="lineas_receta", foreign_keys=[ingrediente_id]
    )
    subreceta_rel: Mapped[Optional["Receta"]] = relationship(
        back_populates="lineas_como_subreceta", foreign_keys=[subreceta_id]
    )


class PrecioCompetencia(Base):
    __tablename__ = "precios_competencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    receta_id: Mapped[int] = mapped_column(ForeignKey("recetas.id"))
    competidor_nombre: Mapped[str] = mapped_column(sa.String(200))
    precio: Mapped[float] = mapped_column(sa.Float)
    fecha_registro: Mapped[date] = mapped_column(sa.Date, default=date.today)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    receta_rel: Mapped["Receta"] = relationship()


# ============================================================
# Module 3 — Stock / Inventory
# ============================================================


class InventarioRegistro(Base):
    __tablename__ = "inventario_registros"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingrediente_id: Mapped[int] = mapped_column(ForeignKey("ingredientes.id"))
    cantidad: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))
    fecha_registro: Mapped[date] = mapped_column(sa.Date, default=date.today)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    ubicacion: Mapped[Optional[str]] = mapped_column(sa.String(10), nullable=True)

    ingrediente_rel: Mapped["Ingrediente"] = relationship()


# ============================================================
# Module 4 — Purchasing / Suppliers
# ============================================================


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200), unique=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    lead_time_dias: Mapped[int] = mapped_column(sa.Integer, default=2)
    ciclo_pedido_dias: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)

    precios: Mapped[list["PrecioProveedor"]] = relationship(
        back_populates="proveedor_rel", cascade="all, delete-orphan"
    )


class PrecioProveedor(Base):
    __tablename__ = "precios_proveedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingrediente_id: Mapped[int] = mapped_column(ForeignKey("ingredientes.id"))
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id"))
    precio: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))
    cantidad: Mapped[float] = mapped_column(sa.Float, default=1)
    precio_por_unidad: Mapped[float] = mapped_column(sa.Float)
    fecha: Mapped[date] = mapped_column(sa.Date, default=date.today)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    ingrediente_rel: Mapped["Ingrediente"] = relationship()
    proveedor_rel: Mapped["Proveedor"] = relationship(back_populates="precios")


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[date] = mapped_column(sa.Date, default=date.today)
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id"))
    estado: Mapped[str] = mapped_column(sa.String(20), default="borrador")
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    fecha_recepcion: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)

    lineas: Mapped[list["LineaPedido"]] = relationship(
        back_populates="pedido_rel", cascade="all, delete-orphan"
    )
    proveedor_rel: Mapped["Proveedor"] = relationship()


class LineaPedido(Base):
    __tablename__ = "lineas_pedido"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"))
    ingrediente_id: Mapped[int] = mapped_column(ForeignKey("ingredientes.id"))
    cantidad_pedida: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))
    cantidad_recibida: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    precio_unitario: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)

    pedido_rel: Mapped["Pedido"] = relationship(back_populates="lineas")
    ingrediente_rel: Mapped["Ingrediente"] = relationship()


# ============================================================
# Module 5 — Production
# ============================================================


class ProductoProduccion(Base):
    __tablename__ = "productos_produccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    categoria: Mapped[str] = mapped_column(sa.String(50))
    unidad: Mapped[str] = mapped_column(sa.String(20))
    shelf_life_days: Mapped[int] = mapped_column(sa.Integer, default=30)
    default_qty: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    position: Mapped[int] = mapped_column(sa.Integer, default=0)

    plan_entries: Mapped[list["PlanProduccion"]] = relationship(
        back_populates="producto", cascade="all, delete-orphan"
    )
    logs: Mapped[list["LogProduccion"]] = relationship(
        back_populates="producto", cascade="all, delete-orphan"
    )


class PlanProduccion(Base):
    __tablename__ = "planes_produccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_produccion.id"))
    week_number: Mapped[int] = mapped_column(sa.Integer)
    day_of_week: Mapped[int] = mapped_column(sa.Integer)
    planned_qty: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("producto_id", "week_number", "day_of_week", name="uq_plan_produccion"),
    )

    producto: Mapped["ProductoProduccion"] = relationship(back_populates="plan_entries")


class LogProduccion(Base):
    __tablename__ = "logs_produccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_produccion.id"))
    target_date: Mapped[str] = mapped_column(sa.String(10))
    planned_qty: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    actual_qty: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    duration_minutes_machine: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    duration_minutes_human: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    is_unplanned: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    notes: Mapped[Optional[str]] = mapped_column(sa.String(500), nullable=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("producto_id", "target_date", name="uq_log_produccion"),
    )

    producto: Mapped["ProductoProduccion"] = relationship(back_populates="logs")
    user: Mapped["User"] = relationship(foreign_keys=[recorded_by])


class TareaProduccion(Base):
    __tablename__ = "tareas_produccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    dia_semana: Mapped[int] = mapped_column(sa.Integer)
    hora: Mapped[Optional[str]] = mapped_column(sa.String(5), nullable=True)
    titulo: Mapped[str] = mapped_column(sa.String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    duracion_minutos: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    cantidad_planificada: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    unidad_cantidad: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    receta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    producto_congelado_id: Mapped[Optional[int]] = mapped_column(ForeignKey("productos_congelados.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(sa.String(20), default="produccion")
    posicion: Mapped[int] = mapped_column(sa.Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))

    receta: Mapped[Optional["Receta"]] = relationship(foreign_keys=[receta_id])


class RegistroProduccion(Base):
    __tablename__ = "registros_produccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    tarea_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tareas_produccion.id"), nullable=True)
    fecha: Mapped[date] = mapped_column(sa.Date)
    completada: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))
    cantidad_real: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    duracion_real: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    titulo_extra: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    unidad_extra: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    receta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    producto_congelado_id: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    bastones_consumidos: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    registrado_por: Mapped[int] = mapped_column(ForeignKey("users.id"))
    registrado_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    tarea: Mapped[Optional["TareaProduccion"]] = relationship()
    receta: Mapped[Optional["Receta"]] = relationship(foreign_keys=[receta_id])
    user: Mapped["User"] = relationship(foreign_keys=[registrado_por])


# ============================================================
# Module 6 — Frozen Stock
# ============================================================


class ProductoCongelado(Base):
    __tablename__ = "productos_congelados"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    categoria: Mapped[str] = mapped_column(sa.String(50))
    unidad: Mapped[str] = mapped_column(sa.String(20))
    receta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    nivel: Mapped[str] = mapped_column(sa.String(20), default="terminado")
    producto_padre_id: Mapped[Optional[int]] = mapped_column(ForeignKey("productos_congelados.id"), nullable=True)
    cantidad_por_padre: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    position: Mapped[int] = mapped_column(sa.Integer, default=0)

    receta: Mapped[Optional["Receta"]] = relationship(foreign_keys=[receta_id])
    padre: Mapped[Optional["ProductoCongelado"]] = relationship(remote_side=[id])


class StockCongelado(Base):
    __tablename__ = "stock_congelado"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_congelado_id: Mapped[int] = mapped_column(ForeignKey("productos_congelados.id"))
    cantidad: Mapped[float] = mapped_column(sa.Float)
    fecha_entrada: Mapped[date] = mapped_column(sa.Date, default=date.today)
    fecha_vencimiento: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    lote: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    ubicacion: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    # Plain int, not an FK: deleting a registro must never be blocked by leftover
    # lot rows, and revertir_efectos clears these pointers explicitly.
    registro_produccion_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer, nullable=True, index=True
    )

    producto: Mapped["ProductoCongelado"] = relationship()


class ConsumoFifoDetalle(Base):
    """Per-lot breakdown of a FIFO consumption.

    deducir_congelado_fifo() mutates StockCongelado rows in place and only records
    one aggregate MovimientoStock. This table remembers which lots were drawn and by
    how much, so a reversal can restore each lot exactly instead of inventing a new
    one (which would reset fecha_entrada and corrupt FIFO/expiry order).
    """

    __tablename__ = "consumo_fifo_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    movimiento_stock_id: Mapped[int] = mapped_column(
        ForeignKey("movimientos_stock.id", ondelete="CASCADE"), index=True
    )
    stock_congelado_id: Mapped[int] = mapped_column(ForeignKey("stock_congelado.id"))
    cantidad: Mapped[float] = mapped_column(sa.Float)


# ============================================================
# Module 7 — Waste
# ============================================================


class MermaRegistro(Base):
    __tablename__ = "mermas"

    id: Mapped[int] = mapped_column(primary_key=True)
    ingrediente_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ingredientes.id"), nullable=True)
    receta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    nombre_libre: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    cantidad: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))
    motivo: Mapped[str] = mapped_column(sa.String(20))
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    fecha: Mapped[date] = mapped_column(sa.Date, default=date.today)
    ubicacion: Mapped[Optional[str]] = mapped_column(sa.String(10), nullable=True)
    coste_unitario: Mapped[float] = mapped_column(sa.Float, default=0)
    coste_total: Mapped[float] = mapped_column(sa.Float, default=0)
    registered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    ingrediente_rel: Mapped[Optional["Ingrediente"]] = relationship(foreign_keys=[ingrediente_id])
    receta_rel: Mapped[Optional["Receta"]] = relationship(foreign_keys=[receta_id])


# ============================================================
# Module 8 — Protocols & Temperature
# ============================================================


class ProtocoloTemplate(Base):
    __tablename__ = "protocolo_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_type: Mapped[str] = mapped_column(sa.String(20))
    section: Mapped[str] = mapped_column(sa.String(100))
    task_name: Mapped[str] = mapped_column(sa.String(500))
    position: Mapped[int] = mapped_column(sa.Integer, default=0)
    day_of_week: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    day_of_month: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    shift: Mapped[Optional[str]] = mapped_column(sa.String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))

    completions: Mapped[list["ProtocoloCompletion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class ProtocoloCompletion(Base):
    __tablename__ = "protocolo_completions"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("protocolo_templates.id"))
    completed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    target_date: Mapped[str] = mapped_column(sa.String(10))
    target_period: Mapped[Optional[str]] = mapped_column(sa.String(10), nullable=True)
    is_satisfactory: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    review_note: Mapped[Optional[str]] = mapped_column(sa.String(500), nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("template_id", "target_date", name="uq_protocolo_completion"),
    )

    template: Mapped["ProtocoloTemplate"] = relationship(back_populates="completions")
    user: Mapped["User"] = relationship(foreign_keys=[completed_by])
    reviewer: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by])


class Frigorifico(Base):
    __tablename__ = "frigorificos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(100))
    tipo: Mapped[str] = mapped_column(sa.String(20), default="frigorifico")
    max_temp: Mapped[float] = mapped_column(sa.Float, default=5.0)
    position: Mapped[int] = mapped_column(sa.Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))

    readings: Mapped[list["LecturaTemperatura"]] = relationship(
        back_populates="frigorifico", cascade="all, delete-orphan"
    )


class LecturaTemperatura(Base):
    __tablename__ = "lecturas_temperatura"

    id: Mapped[int] = mapped_column(primary_key=True)
    frigorifico_id: Mapped[int] = mapped_column(ForeignKey("frigorificos.id"))
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    target_date: Mapped[str] = mapped_column(sa.String(10))
    shift: Mapped[str] = mapped_column(sa.String(20))
    value: Mapped[float] = mapped_column(sa.Float)
    is_alert: Mapped[bool] = mapped_column(default=False, server_default=sa_text("false"))

    __table_args__ = (
        UniqueConstraint("frigorifico_id", "target_date", "shift", name="uq_lectura_temperatura"),
    )

    frigorifico: Mapped["Frigorifico"] = relationship(back_populates="readings")
    user: Mapped["User"] = relationship(foreign_keys=[recorded_by])


# ============================================================
# Module 9 — Customer Portal
# ============================================================


class ProductoCatalogo(Base):
    __tablename__ = "productos_catalogo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    precio: Mapped[float] = mapped_column(sa.Float)
    categoria: Mapped[str] = mapped_column(sa.String(50))
    imagen_url: Mapped[Optional[str]] = mapped_column(sa.String(500), nullable=True)
    receta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("recetas.id"), nullable=True)
    disponible: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    posicion: Mapped[int] = mapped_column(sa.Integer, default=0)

    receta: Mapped[Optional["Receta"]] = relationship(foreign_keys=[receta_id])


class PedidoRecurrente(Base):
    __tablename__ = "pedidos_recurrentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes_b2b.id"))
    dia_entrega: Mapped[str] = mapped_column(sa.String(10))
    activo: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    fecha_inicio: Mapped[date] = mapped_column(sa.Date, default=date.today)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    cliente: Mapped["ClienteB2B"] = relationship()
    lineas: Mapped[list["LineaPedidoRecurrente"]] = relationship(
        back_populates="pedido_recurrente", cascade="all, delete-orphan"
    )


class LineaPedidoRecurrente(Base):
    __tablename__ = "lineas_pedido_recurrente"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_recurrente_id: Mapped[int] = mapped_column(ForeignKey("pedidos_recurrentes.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_catalogo.id"))
    cantidad_default: Mapped[float] = mapped_column(sa.Float)

    pedido_recurrente: Mapped["PedidoRecurrente"] = relationship(back_populates="lineas")
    producto: Mapped["ProductoCatalogo"] = relationship()


class PedidoCliente(Base):
    __tablename__ = "pedidos_clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes_b2b.id"))
    fecha_pedido: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    fecha_entrega: Mapped[date] = mapped_column(sa.Date)
    estado: Mapped[str] = mapped_column(sa.String(20), default="pendiente")
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    total: Mapped[float] = mapped_column(sa.Float, default=0)
    pedido_recurrente_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pedidos_recurrentes.id"), nullable=True
    )

    cliente: Mapped["ClienteB2B"] = relationship()
    lineas: Mapped[list["LineaPedidoCliente"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan"
    )
    pedido_recurrente: Mapped[Optional["PedidoRecurrente"]] = relationship()


class LineaPedidoCliente(Base):
    __tablename__ = "lineas_pedido_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_cliente_id: Mapped[int] = mapped_column(ForeignKey("pedidos_clientes.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_catalogo.id"))
    cantidad: Mapped[float] = mapped_column(sa.Float)
    precio_unitario_snapshot: Mapped[float] = mapped_column(sa.Float)
    subtotal: Mapped[float] = mapped_column(sa.Float)

    pedido: Mapped["PedidoCliente"] = relationship(back_populates="lineas")
    producto: Mapped["ProductoCatalogo"] = relationship()


# ============================================================
# Module 11 — B2B
# ============================================================


class ClienteB2B(Base):
    __tablename__ = "clientes_b2b"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(sa.String(200))
    email: Mapped[Optional[str]] = mapped_column(sa.String(200), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    contacto: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    dia_entrega_preferido: Mapped[Optional[str]] = mapped_column(sa.String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    created_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime, nullable=True)


class EntregaB2B(Base):
    __tablename__ = "entregas_b2b"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_b2b_id: Mapped[int] = mapped_column(ForeignKey("clientes_b2b.id"))
    fecha_entrega: Mapped[date] = mapped_column(sa.Date)
    estado: Mapped[str] = mapped_column(sa.String(20), default="pendiente")
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    cliente: Mapped["ClienteB2B"] = relationship()
    lineas: Mapped[list["LineaEntregaB2B"]] = relationship(
        back_populates="entrega", cascade="all, delete-orphan"
    )


class LineaEntregaB2B(Base):
    __tablename__ = "lineas_entrega_b2b"

    id: Mapped[int] = mapped_column(primary_key=True)
    entrega_id: Mapped[int] = mapped_column(ForeignKey("entregas_b2b.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos_catalogo.id"))
    cantidad: Mapped[float] = mapped_column(sa.Float)
    precio_unitario: Mapped[float] = mapped_column(sa.Float, default=0)

    entrega: Mapped["EntregaB2B"] = relationship(back_populates="lineas")
    producto: Mapped["ProductoCatalogo"] = relationship()


# ============================================================
# Stock Movement Ledger
# ============================================================


class MovimientoStock(Base):
    __tablename__ = "movimientos_stock"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_stock: Mapped[str] = mapped_column(sa.String(20))
    referencia_producto_id: Mapped[int] = mapped_column(sa.Integer)
    cantidad: Mapped[float] = mapped_column(sa.Float)
    unidad: Mapped[str] = mapped_column(sa.String(20))
    tipo_movimiento: Mapped[str] = mapped_column(sa.String(30))
    referencia_origen: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    saldo_despues: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    fecha: Mapped[date] = mapped_column(sa.Date, default=date.today)
    notas: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    registrado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    registrado_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
