from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# --- Auth ---
class LoginRequest(BaseModel):
    name: str
    pin: str

class TokenResponse(BaseModel):
    token: str

class UserOut(BaseModel):
    id: int
    name: str
    role: str

class UserCreate(BaseModel):
    name: str
    pin: str
    role: str = "staff"

class UserUpdate(BaseModel):
    name: Optional[str] = None
    pin: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


# --- Cliente Auth ---
class ClienteRegistro(BaseModel):
    email: str
    password: str
    nombre: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None

class ClienteLogin(BaseModel):
    email: str
    password: str

class ClienteOut(BaseModel):
    id: int
    email: str
    nombre: str
    telefono: Optional[str] = None
    direccion: Optional[str] = None


# --- Permissions ---
class PermissionOut(BaseModel):
    id: int
    role: str
    module: str
    action: str
    allowed: bool

class PermissionUpdate(BaseModel):
    allowed: bool


# --- Categorias ---
class CategoriaCreate(BaseModel):
    nombre: str
    tipo: str
    margen_objetivo: Optional[float] = None
    orden: Optional[int] = 0

class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    margen_objetivo: Optional[float] = None
    orden: Optional[int] = None

class CategoriaOut(BaseModel):
    id: int
    nombre: str
    tipo: str
    margen_objetivo: Optional[float] = None
    orden: Optional[int] = None


# --- Ingredientes ---
class IngredienteCreate(BaseModel):
    nombre: str
    categoria_id: int
    unidad_compra: str
    cantidad_compra: float
    precio_compra: float
    unidad_uso: str
    merma_porcentaje: float = 0.0
    proveedor: Optional[str] = None
    notas: Optional[str] = None

class IngredienteUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria_id: Optional[int] = None
    unidad_compra: Optional[str] = None
    cantidad_compra: Optional[float] = None
    precio_compra: Optional[float] = None
    unidad_uso: Optional[str] = None
    merma_porcentaje: Optional[float] = None
    proveedor: Optional[str] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None

class IngredienteOut(BaseModel):
    id: int
    nombre: str
    categoria_id: int
    categoria_nombre: str
    unidad_compra: str
    cantidad_compra: float
    precio_compra: float
    unidad_uso: str
    merma_porcentaje: float
    proveedor: Optional[str] = None
    notas: Optional[str] = None
    activo: bool
    costo_por_unidad_uso: float
    fecha_actualizacion: date

class HistorialPrecioOut(BaseModel):
    id: int
    ingrediente_id: int
    precio_anterior: float
    precio_nuevo: float
    fecha_cambio: date


# --- Recetas ---
class LineaRecetaIn(BaseModel):
    ingrediente_id: Optional[int] = None
    subreceta_id: Optional[int] = None
    cantidad: float
    unidad: str

class RecetaCreate(BaseModel):
    nombre: str
    categoria_id: int
    porciones_por_lote: float = 1
    precio_venta: Optional[float] = None
    es_subreceta: bool = False
    unidad_rendimiento: Optional[str] = None
    notas: Optional[str] = None
    lineas: list[LineaRecetaIn] = []

class RecetaUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria_id: Optional[int] = None
    porciones_por_lote: Optional[float] = None
    precio_venta: Optional[float] = None
    es_subreceta: Optional[bool] = None
    unidad_rendimiento: Optional[str] = None
    notas: Optional[str] = None
    lineas: Optional[list[LineaRecetaIn]] = None

class LineaRecetaOut(BaseModel):
    id: int
    ingrediente_id: Optional[int] = None
    subreceta_id: Optional[int] = None
    cantidad: float
    unidad: str
    nombre: str
    costo_linea: float

class RecetaOut(BaseModel):
    id: int
    nombre: str
    categoria_id: int
    categoria_nombre: str
    porciones_por_lote: float
    precio_venta: Optional[float] = None
    es_subreceta: bool
    unidad_rendimiento: Optional[str] = None
    notas: Optional[str] = None
    costo_total: float
    costo_por_porcion: float
    margen: Optional[float] = None
    multi: Optional[float] = None
    lineas: list[LineaRecetaOut] = []


# --- Precio Competencia ---
class PrecioCompetenciaCreate(BaseModel):
    receta_id: int
    competidor_nombre: str
    precio: float
    notas: Optional[str] = None

class PrecioCompetenciaOut(BaseModel):
    id: int
    receta_id: int
    competidor_nombre: str
    precio: float
    fecha_registro: date
    notas: Optional[str] = None
