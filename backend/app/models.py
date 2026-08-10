from datetime import date, datetime
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
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(200))
    nombre: Mapped[str] = mapped_column(sa.String(200))
    telefono: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


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
    fecha_creacion: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    fecha_modificacion: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

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
