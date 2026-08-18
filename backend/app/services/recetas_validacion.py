from sqlalchemy.orm import Session

from app.models import LineaReceta


def validar_xor_lineas(lineas: list) -> None:
    """Each line must reference exactly one of ingrediente_id / subreceta_id.

    `lineas` items are LineaRecetaIn (attribute access) or dicts (from
    RecetaUpdate's exclude_unset dump) — both are supported.
    """
    for l in lineas:
        ing_id = l.ingrediente_id if hasattr(l, "ingrediente_id") else l.get("ingrediente_id")
        sub_id = l.subreceta_id if hasattr(l, "subreceta_id") else l.get("subreceta_id")
        if (ing_id is None) == (sub_id is None):
            raise ValueError(
                "Cada línea debe tener exactamente un ingrediente o una subreceta, no ambos ni ninguno"
            )


def detectar_ciclo(db: Session, receta_id: int | None, candidato_subreceta_id: int) -> bool:
    """True if making `receta_id` reference `candidato_subreceta_id` as a subreceta
    would create a cycle (direct or transitive), by walking candidato's existing
    persisted subreceta chain forward and checking if it reaches back to receta_id.

    A brand-new recipe (receta_id=None) cannot yet be part of any cycle.
    """
    if receta_id is None:
        return False
    if candidato_subreceta_id == receta_id:
        return True

    visited: set[int] = set()
    stack = [candidato_subreceta_id]
    while stack:
        current = stack.pop()
        if current == receta_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        hijos = (
            db.query(LineaReceta.subreceta_id)
            .filter(LineaReceta.receta_id == current, LineaReceta.subreceta_id.isnot(None))
            .all()
        )
        stack.extend(sid for (sid,) in hijos)
    return False


def validar_lineas_receta(db: Session, receta_id: int | None, lineas: list) -> None:
    """Single entry point called by create_receta / update_receta before any DB write."""
    validar_xor_lineas(lineas)
    subreceta_ids = {
        (l.subreceta_id if hasattr(l, "subreceta_id") else l.get("subreceta_id"))
        for l in lineas
    }
    for sub_id in subreceta_ids:
        if sub_id is not None and detectar_ciclo(db, receta_id, sub_id):
            raise ValueError(f"Referenciar la subreceta #{sub_id} crearía un ciclo de recetas")
