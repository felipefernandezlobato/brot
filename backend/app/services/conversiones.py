CONVERSIONES = {
    ("kg", "g"): 1000,
    ("kg", "mg"): 1_000_000,
    ("g", "mg"): 1000,
    ("g", "kg"): 0.001,
    ("mg", "g"): 0.001,
    ("mg", "kg"): 0.000001,
    ("litro", "ml"): 1000,
    ("litro", "cl"): 100,
    ("ml", "litro"): 0.001,
    ("ml", "cl"): 0.1,
    ("cl", "ml"): 10,
    ("cl", "litro"): 0.01,
}

FAMILIAS = {
    "kg": "peso", "g": "peso", "mg": "peso",
    "litro": "volumen", "ml": "volumen", "cl": "volumen",
    "unidad": "unidad", "u": "unidad",
}


def convertir(cantidad: float, de_unidad: str, a_unidad: str) -> float:
    if de_unidad == a_unidad:
        return cantidad

    fam_de = FAMILIAS.get(de_unidad)
    fam_a = FAMILIAS.get(a_unidad)

    if not fam_de or not fam_a:
        raise ValueError(f"Unidad desconocida: {de_unidad} o {a_unidad}")
    if fam_de != fam_a:
        raise ValueError(f"No se puede convertir {de_unidad} ({fam_de}) a {a_unidad} ({fam_a})")

    factor = CONVERSIONES.get((de_unidad, a_unidad))
    if factor is None:
        raise ValueError(f"Conversión no definida: {de_unidad} → {a_unidad}")

    return cantidad * factor
