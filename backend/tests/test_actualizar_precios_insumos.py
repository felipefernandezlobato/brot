"""The one-off that applies the 01/09 supplier price list to the catalog.

What matters here is that every change leaves a HistorialPrecio row behind (the
whole point of the request), that a row already matching the list is left
alone, and that an id pointing at a different ingredient than the list expects
is refused rather than repriced.
"""

import importlib.util
from datetime import date
from pathlib import Path

from app.models import Categoria, HistorialPrecio, Ingrediente

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "actualizar_precios_insumos_0109.py"
_spec = importlib.util.spec_from_file_location("actualizar_precios_insumos_0109", _SCRIPT)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

PRECIOS = dict((ing_id, (nombre, precio)) for ing_id, nombre, precio in script.PRECIOS)
HARINA_000 = 1
HUEVOS = 9
ACEITE_GIRASOL = 11  # already at the list price in production


def _catalogo(db, precios_actuales: dict[int, float]):
    cat = Categoria(nombre="Insumos", tipo="ingrediente")
    db.add(cat)
    db.flush()
    for ing_id, (nombre, _) in PRECIOS.items():
        db.add(Ingrediente(
            id=ing_id, nombre=nombre, categoria_id=cat.id,
            unidad_compra="kg", unidad_uso="kg",
            precio_compra=precios_actuales.get(ing_id, 1.0), cantidad_compra=1.0,
        ))
    db.commit()


def _mudo(*_):
    pass


def test_actualiza_y_deja_el_precio_viejo_en_el_historial(db):
    viejo = 760.0
    _catalogo(db, {HARINA_000: viejo})

    cambiados = script.actualizar(db, apply=True, log=_mudo)
    db.commit()

    assert HARINA_000 in cambiados
    assert db.get(Ingrediente, HARINA_000).precio_compra == PRECIOS[HARINA_000][1]

    h = db.query(HistorialPrecio).filter(HistorialPrecio.ingrediente_id == HARINA_000).one()
    assert h.precio_anterior == viejo
    assert h.precio_nuevo == PRECIOS[HARINA_000][1]
    assert h.fecha_cambio == date.today()


def test_huevos_va_en_precio_por_kilo_no_por_unidad(db):
    """50 g por huevo a $267 -> $5.340 el kilo, no $267."""
    _catalogo(db, {HUEVOS: 3933.0})

    script.actualizar(db, apply=True, log=_mudo)
    db.commit()

    assert db.get(Ingrediente, HUEVOS).precio_compra == 267.0 / 0.050


def test_no_toca_ni_historia_un_precio_que_ya_coincide(db):
    _catalogo(db, {ACEITE_GIRASOL: PRECIOS[ACEITE_GIRASOL][1]})

    cambiados = script.actualizar(db, apply=True, log=_mudo)
    db.commit()

    assert ACEITE_GIRASOL not in cambiados
    assert db.query(HistorialPrecio).filter(
        HistorialPrecio.ingrediente_id == ACEITE_GIRASOL
    ).count() == 0


def test_el_dry_run_no_escribe(db):
    viejo = 760.0
    _catalogo(db, {HARINA_000: viejo})

    cambiados = script.actualizar(db, apply=False, log=_mudo)

    assert HARINA_000 in cambiados  # lo reporta
    assert db.get(Ingrediente, HARINA_000).precio_compra == viejo
    assert db.query(HistorialPrecio).count() == 0


def test_es_idempotente(db):
    _catalogo(db, {HARINA_000: 760.0})

    script.actualizar(db, apply=True, log=_mudo)
    db.commit()
    historial = db.query(HistorialPrecio).count()

    assert script.actualizar(db, apply=True, log=_mudo) == []
    db.commit()
    assert db.query(HistorialPrecio).count() == historial


def test_no_repricia_un_id_que_apunta_a_otro_ingrediente(db):
    """Cheap guard against id drift: the list names the ingredient, so a
    mismatch means the row moved and must not be touched."""
    _catalogo(db, {HARINA_000: 760.0})
    impostor = db.get(Ingrediente, HARINA_000)
    impostor.nombre = "Otra Cosa"
    db.commit()

    cambiados = script.actualizar(db, apply=True, log=_mudo)
    db.commit()

    assert HARINA_000 not in cambiados
    assert db.get(Ingrediente, HARINA_000).precio_compra == 760.0
    # Scoped to the renamed row: the rest of the catalog is repriced normally.
    assert db.query(HistorialPrecio).filter(
        HistorialPrecio.ingrediente_id == HARINA_000
    ).count() == 0
