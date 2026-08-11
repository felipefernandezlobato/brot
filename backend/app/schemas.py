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
    num_recetas: int = 0

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


# ============================================================
# Module 3 — Stock / Inventory
# ============================================================


class InventarioRegistroCreate(BaseModel):
    ingrediente_id: int
    cantidad: float
    unidad: str
    fecha_registro: Optional[date] = None
    notas: Optional[str] = None
    ubicacion: Optional[str] = None


class InventarioRegistroUpdate(BaseModel):
    ingrediente_id: Optional[int] = None
    cantidad: Optional[float] = None
    unidad: Optional[str] = None
    fecha_registro: Optional[date] = None
    notas: Optional[str] = None
    ubicacion: Optional[str] = None


class InventarioRegistroOut(BaseModel):
    id: int
    ingrediente_id: int
    cantidad: float
    unidad: str
    fecha_registro: date
    notas: Optional[str] = None
    ubicacion: Optional[str] = None


# ============================================================
# Module 4 — Purchasing / Suppliers
# ============================================================


class ProveedorCreate(BaseModel):
    nombre: str
    notas: Optional[str] = None
    lead_time_dias: int = 2
    ciclo_pedido_dias: Optional[int] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class ProveedorUpdate(BaseModel):
    nombre: Optional[str] = None
    notas: Optional[str] = None
    lead_time_dias: Optional[int] = None
    ciclo_pedido_dias: Optional[int] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class ProveedorOut(BaseModel):
    id: int
    nombre: str
    notas: Optional[str] = None
    lead_time_dias: int
    ciclo_pedido_dias: Optional[int] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class PrecioProveedorCreate(BaseModel):
    ingrediente_id: int
    proveedor_id: int
    precio: float
    unidad: str
    cantidad: float = 1
    precio_por_unidad: float
    fecha: Optional[date] = None
    notas: Optional[str] = None


class PrecioProveedorUpdate(BaseModel):
    ingrediente_id: Optional[int] = None
    proveedor_id: Optional[int] = None
    precio: Optional[float] = None
    unidad: Optional[str] = None
    cantidad: Optional[float] = None
    precio_por_unidad: Optional[float] = None
    fecha: Optional[date] = None
    notas: Optional[str] = None


class PrecioProveedorOut(BaseModel):
    id: int
    ingrediente_id: int
    proveedor_id: int
    precio: float
    unidad: str
    cantidad: float
    precio_por_unidad: float
    fecha: date
    notas: Optional[str] = None


class LineaPedidoIn(BaseModel):
    ingrediente_id: int
    cantidad_pedida: float
    unidad: str
    cantidad_recibida: Optional[float] = None
    precio_unitario: Optional[float] = None


class PedidoCreate(BaseModel):
    proveedor_id: int
    fecha: Optional[date] = None
    estado: str = "borrador"
    notas: Optional[str] = None
    fecha_recepcion: Optional[date] = None
    lineas: list[LineaPedidoIn] = []


class PedidoUpdate(BaseModel):
    proveedor_id: Optional[int] = None
    fecha: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    fecha_recepcion: Optional[date] = None
    lineas: Optional[list[LineaPedidoIn]] = None


class LineaPedidoOut(BaseModel):
    id: int
    pedido_id: int
    ingrediente_id: int
    cantidad_pedida: float
    unidad: str
    cantidad_recibida: Optional[float] = None
    precio_unitario: Optional[float] = None


class PedidoOut(BaseModel):
    id: int
    fecha: date
    proveedor_id: int
    proveedor_nombre: str
    estado: str
    notas: Optional[str] = None
    fecha_recepcion: Optional[date] = None
    lineas: list[LineaPedidoOut] = []


# ============================================================
# Module 5 — Production
# ============================================================


class ProductoProduccionCreate(BaseModel):
    nombre: str
    categoria: str
    unidad: str
    shelf_life_days: int = 30
    default_qty: Optional[float] = None
    is_active: bool = True
    position: int = 0


class ProductoProduccionUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    unidad: Optional[str] = None
    shelf_life_days: Optional[int] = None
    default_qty: Optional[float] = None
    is_active: Optional[bool] = None
    position: Optional[int] = None


class ProductoProduccionOut(BaseModel):
    id: int
    nombre: str
    categoria: str
    unidad: str
    shelf_life_days: int
    default_qty: Optional[float] = None
    is_active: bool
    position: int


class PlanProduccionCreate(BaseModel):
    producto_id: int
    week_number: int
    day_of_week: int
    planned_qty: Optional[float] = None


class PlanProduccionUpdate(BaseModel):
    planned_qty: Optional[float] = None


class PlanProduccionOut(BaseModel):
    id: int
    producto_id: int
    week_number: int
    day_of_week: int
    planned_qty: Optional[float] = None


class LogProduccionCreate(BaseModel):
    producto_id: int
    target_date: str
    planned_qty: Optional[float] = None
    actual_qty: Optional[float] = None
    duration_minutes_machine: Optional[int] = None
    duration_minutes_human: Optional[int] = None
    is_unplanned: bool = False
    notes: Optional[str] = None
    recorded_by: Optional[int] = None


class LogProduccionUpdate(BaseModel):
    planned_qty: Optional[float] = None
    actual_qty: Optional[float] = None
    duration_minutes_machine: Optional[int] = None
    duration_minutes_human: Optional[int] = None
    is_unplanned: Optional[bool] = None
    notes: Optional[str] = None


class LogProduccionOut(BaseModel):
    id: int
    producto_id: int
    target_date: str
    planned_qty: Optional[float] = None
    actual_qty: Optional[float] = None
    duration_minutes_machine: Optional[int] = None
    duration_minutes_human: Optional[int] = None
    is_unplanned: bool
    notes: Optional[str] = None
    recorded_by: int
    recorded_at: datetime


class TareaProduccionCreate(BaseModel):
    dia_semana: int
    hora: Optional[str] = None
    titulo: str
    descripcion: Optional[str] = None
    duracion_minutos: Optional[int] = None
    cantidad_planificada: Optional[float] = None
    unidad_cantidad: Optional[str] = None
    receta_id: Optional[int] = None
    tipo: str = "produccion"
    posicion: int = 0


class TareaProduccionUpdate(BaseModel):
    dia_semana: Optional[int] = None
    hora: Optional[str] = None
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    duracion_minutos: Optional[int] = None
    cantidad_planificada: Optional[float] = None
    unidad_cantidad: Optional[str] = None
    receta_id: Optional[int] = None
    tipo: Optional[str] = None
    posicion: Optional[int] = None
    is_active: Optional[bool] = None


class TareaProduccionOut(BaseModel):
    id: int
    dia_semana: int
    hora: Optional[str] = None
    titulo: str
    descripcion: Optional[str] = None
    duracion_minutos: Optional[int] = None
    cantidad_planificada: Optional[float] = None
    unidad_cantidad: Optional[str] = None
    receta_id: Optional[int] = None
    receta_nombre: Optional[str] = None
    tipo: str
    posicion: int
    is_active: bool


class RegistroProduccionCreate(BaseModel):
    tarea_id: int
    fecha: date
    completada: bool = False
    cantidad_real: Optional[float] = None
    duracion_real: Optional[int] = None
    notas: Optional[str] = None


class RegistroExtraCreate(BaseModel):
    fecha: date
    receta_id: int
    cantidad_real: Optional[float] = None
    duracion_real: Optional[int] = None
    notas: Optional[str] = None


class RegistroProduccionOut(BaseModel):
    id: int
    tarea_id: Optional[int] = None
    fecha: date
    completada: bool
    cantidad_real: Optional[float] = None
    duracion_real: Optional[int] = None
    notas: Optional[str] = None
    titulo_extra: Optional[str] = None
    unidad_extra: Optional[str] = None
    receta_id: Optional[int] = None
    receta_nombre: Optional[str] = None
    registrado_por: int
    registrado_at: datetime


# ============================================================
# Module 6 — Frozen Stock
# ============================================================


class ProductoCongeladoCreate(BaseModel):
    nombre: str
    categoria: str
    unidad: str
    is_active: bool = True
    position: int = 0


class ProductoCongeladoUpdate(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    unidad: Optional[str] = None
    is_active: Optional[bool] = None
    position: Optional[int] = None


class ProductoCongeladoOut(BaseModel):
    id: int
    nombre: str
    categoria: str
    unidad: str
    is_active: bool
    position: int
    receta_id: Optional[int] = None


class StockCongeladoCreate(BaseModel):
    producto_congelado_id: int
    cantidad: float
    fecha_entrada: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    lote: Optional[str] = None
    ubicacion: Optional[str] = None
    notas: Optional[str] = None
    is_active: bool = True


class StockCongeladoUpdate(BaseModel):
    cantidad: Optional[float] = None
    fecha_entrada: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    lote: Optional[str] = None
    ubicacion: Optional[str] = None
    notas: Optional[str] = None
    is_active: Optional[bool] = None


class StockCongeladoOut(BaseModel):
    id: int
    producto_congelado_id: int
    cantidad: float
    fecha_entrada: date
    fecha_vencimiento: Optional[date] = None
    lote: Optional[str] = None
    ubicacion: Optional[str] = None
    notas: Optional[str] = None
    is_active: bool
    producto_nombre: Optional[str] = None


# ============================================================
# Module 7 — Waste
# ============================================================


class MermaRegistroCreate(BaseModel):
    ingrediente_id: Optional[int] = None
    receta_id: Optional[int] = None
    nombre_libre: Optional[str] = None
    cantidad: float
    unidad: str
    motivo: str
    notas: Optional[str] = None
    fecha: Optional[date] = None
    ubicacion: Optional[str] = None
    coste_unitario: float = 0
    coste_total: float = 0
    registered_by: Optional[int] = None


class MermaRegistroUpdate(BaseModel):
    ingrediente_id: Optional[int] = None
    receta_id: Optional[int] = None
    nombre_libre: Optional[str] = None
    cantidad: Optional[float] = None
    unidad: Optional[str] = None
    motivo: Optional[str] = None
    notas: Optional[str] = None
    fecha: Optional[date] = None
    ubicacion: Optional[str] = None
    coste_unitario: Optional[float] = None
    coste_total: Optional[float] = None


class MermaRegistroOut(BaseModel):
    id: int
    ingrediente_id: Optional[int] = None
    receta_id: Optional[int] = None
    nombre_libre: Optional[str] = None
    cantidad: float
    unidad: str
    motivo: str
    notas: Optional[str] = None
    fecha: date
    ubicacion: Optional[str] = None
    coste_unitario: float
    coste_total: float
    registered_by: Optional[int] = None
    registered_at: datetime


# ============================================================
# Module 8 — Protocols & Temperature
# ============================================================


class ProtocoloTemplateCreate(BaseModel):
    checklist_type: str
    section: str
    task_name: str
    position: int = 0
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    shift: Optional[str] = None
    is_active: bool = True


class ProtocoloTemplateUpdate(BaseModel):
    checklist_type: Optional[str] = None
    section: Optional[str] = None
    task_name: Optional[str] = None
    position: Optional[int] = None
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    shift: Optional[str] = None
    is_active: Optional[bool] = None


class ProtocoloTemplateOut(BaseModel):
    id: int
    checklist_type: str
    section: str
    task_name: str
    position: int
    day_of_week: Optional[int] = None
    day_of_month: Optional[int] = None
    shift: Optional[str] = None
    is_active: bool


class ProtocoloCompletionCreate(BaseModel):
    template_id: int
    completed_by: int
    target_date: str
    target_period: Optional[str] = None
    is_satisfactory: bool = True
    review_note: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class ProtocoloCompletionUpdate(BaseModel):
    is_satisfactory: Optional[bool] = None
    review_note: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class ProtocoloCompletionOut(BaseModel):
    id: int
    template_id: int
    completed_by: int
    completed_at: datetime
    target_date: str
    target_period: Optional[str] = None
    is_satisfactory: bool
    review_note: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None


class FrigorificoCreate(BaseModel):
    nombre: str
    tipo: str = "frigorifico"
    max_temp: float = 5.0
    position: int = 0
    is_active: bool = True


class FrigorificoUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    max_temp: Optional[float] = None
    position: Optional[int] = None
    is_active: Optional[bool] = None


class FrigorificoOut(BaseModel):
    id: int
    nombre: str
    tipo: str
    max_temp: float
    position: int
    is_active: bool


class LecturaTemperaturaCreate(BaseModel):
    frigorifico_id: int
    recorded_by: int
    target_date: str
    shift: str
    value: float
    is_alert: bool = False


class LecturaTemperaturaUpdate(BaseModel):
    value: Optional[float] = None
    is_alert: Optional[bool] = None


class LecturaTemperaturaOut(BaseModel):
    id: int
    frigorifico_id: int
    recorded_by: int
    recorded_at: datetime
    target_date: str
    shift: str
    value: float
    is_alert: bool


# ============================================================
# Module 9 — Customer Portal
# ============================================================


class ProductoCatalogoCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    categoria: str
    imagen_url: Optional[str] = None
    disponible: bool = True
    posicion: int = 0


class ProductoCatalogoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    categoria: Optional[str] = None
    imagen_url: Optional[str] = None
    disponible: Optional[bool] = None
    posicion: Optional[int] = None


class ProductoCatalogoOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    precio: float
    categoria: str
    imagen_url: Optional[str] = None
    disponible: bool
    posicion: int


class LineaPedidoRecurrenteIn(BaseModel):
    producto_id: int
    cantidad_default: float


class PedidoRecurrenteCreate(BaseModel):
    cliente_id: int
    dia_entrega: str
    activo: bool = True
    fecha_inicio: Optional[date] = None
    notas: Optional[str] = None
    lineas: list[LineaPedidoRecurrenteIn] = []


class PedidoRecurrenteUpdate(BaseModel):
    dia_entrega: Optional[str] = None
    activo: Optional[bool] = None
    notas: Optional[str] = None
    lineas: Optional[list[LineaPedidoRecurrenteIn]] = None


class LineaPedidoRecurrenteOut(BaseModel):
    id: int
    pedido_recurrente_id: int
    producto_id: int
    cantidad_default: float


class PedidoRecurrenteOut(BaseModel):
    id: int
    cliente_id: int
    dia_entrega: str
    activo: bool
    fecha_inicio: date
    notas: Optional[str] = None
    lineas: list[LineaPedidoRecurrenteOut] = []


class LineaPedidoClienteIn(BaseModel):
    producto_id: int
    cantidad: float
    precio_unitario_snapshot: float
    subtotal: float


class PedidoClienteCreate(BaseModel):
    cliente_id: int
    fecha_entrega: date
    estado: str = "pendiente"
    notas: Optional[str] = None
    total: float = 0
    pedido_recurrente_id: Optional[int] = None
    lineas: list[LineaPedidoClienteIn] = []


class PedidoClienteUpdate(BaseModel):
    fecha_entrega: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    total: Optional[float] = None
    lineas: Optional[list[LineaPedidoClienteIn]] = None


class LineaPedidoClienteOut(BaseModel):
    id: int
    pedido_cliente_id: int
    producto_id: int
    cantidad: float
    precio_unitario_snapshot: float
    subtotal: float


class PedidoClienteOut(BaseModel):
    id: int
    cliente_id: int
    fecha_pedido: datetime
    fecha_entrega: date
    estado: str
    notas: Optional[str] = None
    total: float
    pedido_recurrente_id: Optional[int] = None
    lineas: list[LineaPedidoClienteOut] = []


# ============================================================
# Module 11 — B2B
# ============================================================


class ClienteB2BCreate(BaseModel):
    nombre: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    contacto: Optional[str] = None
    notas: Optional[str] = None
    dia_entrega_preferido: Optional[str] = None
    is_active: bool = True


class ClienteB2BUpdate(BaseModel):
    nombre: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    contacto: Optional[str] = None
    notas: Optional[str] = None
    dia_entrega_preferido: Optional[str] = None
    is_active: Optional[bool] = None


class ClienteB2BOut(BaseModel):
    id: int
    nombre: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    contacto: Optional[str] = None
    notas: Optional[str] = None
    dia_entrega_preferido: Optional[str] = None
    is_active: bool


class LineaEntregaB2BIn(BaseModel):
    producto_id: int
    cantidad: float
    precio_unitario: float = 0


class EntregaB2BCreate(BaseModel):
    cliente_b2b_id: int
    fecha_entrega: date
    estado: str = "pendiente"
    notas: Optional[str] = None
    lineas: list[LineaEntregaB2BIn] = []


class EntregaB2BUpdate(BaseModel):
    fecha_entrega: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    lineas: Optional[list[LineaEntregaB2BIn]] = None


class LineaEntregaB2BOut(BaseModel):
    id: int
    entrega_id: int
    producto_id: int
    cantidad: float
    precio_unitario: float


class EntregaB2BOut(BaseModel):
    id: int
    cliente_b2b_id: int
    fecha_entrega: date
    estado: str
    notas: Optional[str] = None
    created_at: datetime
    lineas: list[LineaEntregaB2BOut] = []


# --- Movimientos Stock ---
class MovimientoStockOut(BaseModel):
    id: int
    tipo_stock: str
    referencia_producto_id: int
    cantidad: float
    unidad: str
    tipo_movimiento: str
    referencia_origen: Optional[str] = None
    saldo_despues: Optional[float] = None
    fecha: date
    notas: Optional[str] = None
    registrado_por: Optional[int] = None
    registrado_at: datetime
