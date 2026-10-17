from collections.abc import Iterable
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models import HistorialPrecio, Ingrediente, LineaReceta, ProductoCongelado, Receta
from app.services.conversiones import convertir


def precargar_arbol(db: Session, recetas: Iterable[Receta]) -> None:
    """Trae de golpe el arbol de subrecetas de `recetas`, para que costearlo no
    haga ni una consulta mas.

    El costeo baja por `subreceta_id` y en cada escalon pide las lineas de la
    subreceta y el ingrediente de cada linea. Si no estan cargadas, SQLAlchemy
    las va a buscar de una en una: una receta suelta costaba 7 consultas y
    `/api/recetas?buscar=` 40 para 12 recetas, porque las subrecetas quedan
    fuera del filtro y ninguna venia cargada. Duele por la LATENCIA, no por el
    trabajo: el backend esta en Render y la base en Neon, asi que cada consulta
    es un viaje de red aunque tarde 0,2ms en ejecutarse.

    Una consulta por NIVEL del arbol, no por receta: la cadena real es
    masa -> baston -> terminado, o sea tres. Deliberadamente no carga el
    catalogo entero -- seria una sola consulta hoy con 42 recetas, pero ata el
    costo de abrir una receta al tamaño del catalogo, y no hace falta.

    No cambia ningun numero: solo deja los objetos en la sesion antes de que
    `costo_receta` los pida. El calculo es identico con precarga y sin ella
    (test_el_costo_es_el_mismo_con_y_sin_precarga).
    """
    pendientes = {r.id for r in recetas if r.id}
    vistos: set[int] = set()
    while pendientes:
        lote = (
            db.query(Receta)
            .options(
                joinedload(Receta.lineas).joinedload(LineaReceta.ingrediente_rel),
                # Cargar `subreceta_rel` no es solo para ahorrarse esa consulta:
                # es lo que MANTIENE VIVO lo precargado. El mapa de identidad de
                # SQLAlchemy guarda referencias DEBILES, asi que las subrecetas
                # de un nivel se recolectaban en cuanto terminaba su vuelta del
                # bucle, y el costeo volvia a pedirlas una por una. Cargadas
                # aqui, cada linea referencia a su subreceta y el arbol entero
                # queda colgando de la lista que tiene el endpoint.
                joinedload(Receta.lineas).joinedload(LineaReceta.subreceta_rel),
            )
            # Y sin populate_existing tampoco sirve: SQLAlchemy no aplica la
            # carga anticipada a objetos que YA estan en la sesion, y las
            # subrecetas ya estan (las acaba de traer la vuelta anterior).
            # Traeria las filas dejando `lineas` sin cargar.
            # Solo se usa en endpoints de lectura: refresca lo ya cargado, asi
            # que no debe llamarse con cambios pendientes sin confirmar.
            .populate_existing()
            .filter(Receta.id.in_(pendientes))
            .all()
        )
        vistos |= pendientes
        pendientes = {
            l.subreceta_id
            for r in lote
            for l in r.lineas
            if l.subreceta_id and l.subreceta_id not in vistos
        }


def precio_compra_en(db: Session, ing: Ingrediente, fecha: date | None = None) -> float:
    """What this ingredient cost per `cantidad_compra` on `fecha`.

    With fecha=None returns the live `precio_compra` — every pre-existing caller
    behaves exactly as before.

    Reconstructed from HistorialPrecio, which records one row per actual change
    (precio_anterior -> precio_nuevo, fecha_cambio). Verified against reality:
    for every ingredient with a real reception, the reconstructed price matches
    what was actually paid on `LineaPedido.precio_unitario` (see
    test_precio_reconstruido_coincide_con_lo_pagado). That matters because the
    alternative -- costing August with today's prices -- is badly wrong here:
    Harina Integral went 1.250 -> 2.400 (+92%) and Miel 13.814 -> 7.500 (-46%).

    KNOWN LIMITS. Only `precio_compra` is historised:
      - `cantidad_compra`/`unidad_compra` are not, so a repackaging is invisible.
        Papa Deshidratada was converted g -> kg on 2026-09-11, so its cost
        before that date is reconstructed against today's kg basis.
      - recipe composition is not historised either (LineaReceta has no
        history), so a reworked recipe is costed with today's lines. Focaccia
        was reworked 2026-08-17/18.
    Both are narrow, and the caller surfaces them rather than hiding them.
    """
    if fecha is None:
        return ing.precio_compra

    cambios = (
        db.query(HistorialPrecio)
        .filter(HistorialPrecio.ingrediente_id == ing.id)
        .order_by(HistorialPrecio.fecha_cambio, HistorialPrecio.id)
        .all()
    )
    if not cambios:
        return ing.precio_compra

    # the price set by the last change on or before `fecha` is the one in force
    previos = [c for c in cambios if c.fecha_cambio <= fecha]
    if previos:
        return previos[-1].precio_nuevo
    # `fecha` predates every recorded change: the price before the first one
    return cambios[0].precio_anterior


def costo_por_unidad_uso(
    ing: Ingrediente, db: Session | None = None, fecha: date | None = None
) -> float:
    precio = precio_compra_en(db, ing, fecha) if (db is not None and fecha is not None) else ing.precio_compra
    cantidad_en_uso = convertir(ing.cantidad_compra, ing.unidad_compra, ing.unidad_uso)
    cpu = precio / cantidad_en_uso
    if ing.merma_porcentaje > 0:
        cpu = cpu / (1 - ing.merma_porcentaje / 100)
    return cpu


def costo_linea(
    linea: LineaReceta,
    db: Session,
    visited: set[int] | None = None,
    fecha: date | None = None,
) -> float:
    if visited is None:
        visited = set()

    if linea.ingrediente_id:
        ing = linea.ingrediente_rel or db.get(Ingrediente, linea.ingrediente_id)
        cpu = costo_por_unidad_uso(ing, db, fecha)
        cantidad_convertida = convertir(linea.cantidad, linea.unidad, ing.unidad_uso)
        return cpu * cantidad_convertida

    if linea.subreceta_id:
        if linea.subreceta_id in visited:
            return 0
        sub = linea.subreceta_rel or db.get(Receta, linea.subreceta_id)
        total_sub, _ = costo_receta(sub, db, visited, fecha)
        costo_por_porcion_sub = total_sub / sub.porciones_por_lote
        if sub.unidad_rendimiento and linea.unidad != sub.unidad_rendimiento:
            cantidad = convertir(linea.cantidad, linea.unidad, sub.unidad_rendimiento)
        else:
            cantidad = linea.cantidad
        return costo_por_porcion_sub * cantidad

    return 0


def receta_incompleta(receta: Receta, db: Session, visited: set[int] | None = None) -> bool:
    """True if any recipe in the tree has no lines, making its cost a lie.

    A cost of 0 is easy to spot, but an EMPTY SUB-recipe nested deeper produces
    a non-zero cost that is simply too low, which is far more dangerous: it
    makes the product look like the most profitable thing on the menu.

    Real case this exists for -- Cinnamon Roll:
        Cinnamon Roll -> Cinnamon Roll Crudo -> Baston Cinnamon Roll (0 lines)
    Only the canela and azucar get costed, with no dough at all, so it comes
    out at 33.91 against a 1.000 price: 96.6% margin, while every correctly
    costed product sits at ~67%. The empty bastón is two levels down, so
    checking only the top recipe's direct lines misses it.

    Callers should treat an incomplete recipe as "cost unknown" rather than
    trusting the number. See CLAUDE.md on Baston Cinnamon Roll.
    """
    visited = visited if visited is not None else set()
    if receta.id in visited:
        return False  # a cycle is a different problem; costo_linea already stops it
    visited.add(receta.id)

    lineas = receta.lineas or db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
    if not lineas:
        return True
    for l in lineas:
        if l.subreceta_id:
            sub = l.subreceta_rel or db.get(Receta, l.subreceta_id)
            if sub and receta_incompleta(sub, db, visited):
                return True
    return False


def costo_receta(
    receta: Receta,
    db: Session,
    visited: set[int] | None = None,
    fecha: date | None = None,
) -> tuple[float, float]:
    """(total del lote, costo por porcion). With `fecha`, uses the ingredient
    prices in force on that date instead of today's — see precio_compra_en."""
    if visited is None:
        visited = set()
    visited.add(receta.id)

    lineas = receta.lineas or db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
    total = sum(costo_linea(l, db, visited, fecha) for l in lineas)
    por_porcion = total / receta.porciones_por_lote if receta.porciones_por_lote else total
    return total, por_porcion


def costo_por_unidad_congelado(
    db: Session, producto_congelado_id: int, visited: set[int] | None = None
) -> float:
    """Cost of one unit of a frozen-stock product, at any level of the chain.

    Masa/baston/terminado levels usually have their own receta_id purely for
    cost roll-up (see costo_receta) even though their PHYSICAL stock moves via
    producto_padre_id. Crudo levels (and a few terminados that bake with no
    added ingredients) have no receta_id of their own -- their cost is instead
    derived by walking up producto_padre_id and dividing by cantidad_por_padre
    at each step, same relationship producir_producto() uses for the real
    stock deduction.
    """
    visited = visited if visited is not None else set()
    if producto_congelado_id in visited:
        return 0.0
    visited.add(producto_congelado_id)

    prod = db.get(ProductoCongelado, producto_congelado_id)
    if not prod:
        return 0.0

    if prod.receta_id:
        receta = db.get(Receta, prod.receta_id)
        if receta:
            _, por_porcion = costo_receta(receta, db)
            return por_porcion

    if prod.producto_padre_id and prod.cantidad_por_padre:
        costo_padre = costo_por_unidad_congelado(db, prod.producto_padre_id, visited)
        return costo_padre / prod.cantidad_por_padre

    return 0.0
