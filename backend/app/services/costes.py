from sqlalchemy.orm import Session

from app.models import Ingrediente, LineaReceta, Receta
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
