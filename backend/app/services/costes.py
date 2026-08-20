from sqlalchemy.orm import Session

from app.models import Ingrediente, LineaReceta, ProductoCongelado, Receta
from app.services.conversiones import convertir


def costo_por_unidad_uso(ing: Ingrediente) -> float:
    cantidad_en_uso = convertir(ing.cantidad_compra, ing.unidad_compra, ing.unidad_uso)
    cpu = ing.precio_compra / cantidad_en_uso
    if ing.merma_porcentaje > 0:
        cpu = cpu / (1 - ing.merma_porcentaje / 100)
    return cpu


def costo_linea(linea: LineaReceta, db: Session, visited: set[int] | None = None) -> float:
    if visited is None:
        visited = set()

    if linea.ingrediente_id:
        ing = linea.ingrediente_rel or db.get(Ingrediente, linea.ingrediente_id)
        cpu = costo_por_unidad_uso(ing)
        cantidad_convertida = convertir(linea.cantidad, linea.unidad, ing.unidad_uso)
        return cpu * cantidad_convertida

    if linea.subreceta_id:
        if linea.subreceta_id in visited:
            return 0
        sub = linea.subreceta_rel or db.get(Receta, linea.subreceta_id)
        total_sub, _ = costo_receta(sub, db, visited)
        costo_por_porcion_sub = total_sub / sub.porciones_por_lote
        if sub.unidad_rendimiento and linea.unidad != sub.unidad_rendimiento:
            cantidad = convertir(linea.cantidad, linea.unidad, sub.unidad_rendimiento)
        else:
            cantidad = linea.cantidad
        return costo_por_porcion_sub * cantidad

    return 0


def costo_receta(receta: Receta, db: Session, visited: set[int] | None = None) -> tuple[float, float]:
    if visited is None:
        visited = set()
    visited.add(receta.id)

    lineas = receta.lineas or db.query(LineaReceta).filter(LineaReceta.receta_id == receta.id).all()
    total = sum(costo_linea(l, db, visited) for l in lineas)
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
