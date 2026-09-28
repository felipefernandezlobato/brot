"""The one-off that re-runs logged Masa de Pizza productions against the current recipe.

Reproduces the real situation: two batches produced while receta 7 carried
0,05 L of Tomate per lote, then the recipe corrected to 1 L. The script has to
move the past consumption to the new figure exactly once, leave every other
ingredient alone, and do nothing at all on a second run.
"""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

from app.auth import hash_pin
from app.models import (
    Categoria,
    Ingrediente,
    InventarioRegistro,
    LineaReceta,
    MovimientoStock,
    ProductoCongelado,
    Receta,
    User,
)
from app.services.produccion_registro import movimiento_no_revertido
from app.services.stock import get_saldo_materia_prima

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "reprocesar_producciones_pizza.py"
_spec = importlib.util.spec_from_file_location("reprocesar_producciones_pizza", _SCRIPT)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

# The script keys off the real production ids, so the fixture has to use them too.
RECETA_ID = script.RECETA_MASA_ID  # 7
PRODUCTO_ID = script.PRODUCTO_MASA_ID  # 46

AYER = date.today() - timedelta(days=30)
HOY = date.today()

TOMATE_VIEJO = 0.05
TOMATE_NUEVO = 1.0
HARINA_G = 3700.0
TOMATE_INICIAL = 6.0


def _auth(client, db):
    db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _mundo(db):
    """Receta 7 with the old 0,05 L Tomate line, plus its masa product."""
    cat_i = Categoria(nombre="Varios", tipo="ingrediente")
    db.add(cat_i)
    db.flush()

    harina = Ingrediente(
        nombre="Harina 00 Pizza", categoria_id=cat_i.id, unidad_compra="kg",
        unidad_uso="kg", precio_compra=900.0, cantidad_compra=1.0,
    )
    tomate = Ingrediente(
        nombre="Tomate", categoria_id=cat_i.id, unidad_compra="litro",
        unidad_uso="litro", precio_compra=0.0, cantidad_compra=1.0,
    )
    db.add_all([harina, tomate])
    db.flush()
    db.add_all([
        InventarioRegistro(ingrediente_id=harina.id, cantidad=100.0, unidad="kg",
                           fecha_registro=AYER - timedelta(days=1)),
        InventarioRegistro(ingrediente_id=tomate.id, cantidad=TOMATE_INICIAL, unidad="litro",
                           fecha_registro=AYER - timedelta(days=1)),
    ])

    cat_r = Categoria(nombre="Pizzas", tipo="receta")
    db.add(cat_r)
    db.flush()

    receta = Receta(id=RECETA_ID, nombre="Pizza 350g", categoria_id=cat_r.id,
                    porciones_por_lote=1.0)
    db.add(receta)
    db.flush()
    db.add_all([
        LineaReceta(receta_id=receta.id, ingrediente_id=harina.id, cantidad=HARINA_G, unidad="g"),
        LineaReceta(receta_id=receta.id, ingrediente_id=tomate.id,
                    cantidad=TOMATE_VIEJO, unidad="litro"),
    ])
    db.add(ProductoCongelado(id=PRODUCTO_ID, nombre="Masa de Pizza", categoria="Masas",
                             unidad="u", receta_id=receta.id, nivel="masa"))
    db.commit()
    return harina, tomate


def _producir(client, headers, fecha):
    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": fecha.isoformat(), "receta_id": RECETA_ID, "cantidad_real": 1.0},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _consumo_vivo(db, ing_id):
    """Total still booked against this ingredient, ignoring reversed pairs."""
    movs = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.tipo_stock == "materia_prima",
            MovimientoStock.referencia_producto_id == ing_id,
            movimiento_no_revertido(),
        )
        .all()
    )
    return sorted(-m.cantidad for m in movs)


def _corregir_receta(db, tomate):
    linea = (
        db.query(LineaReceta)
        .filter(LineaReceta.receta_id == RECETA_ID, LineaReceta.ingrediente_id == tomate.id)
        .first()
    )
    linea.cantidad = TOMATE_NUEVO
    db.commit()


def test_mueve_el_consumo_pasado_a_la_receta_nueva(client, db):
    headers = _auth(client, db)
    harina, tomate = _mundo(db)

    _producir(client, headers, AYER)
    _producir(client, headers, HOY)
    assert _consumo_vivo(db, tomate.id) == [TOMATE_VIEJO, TOMATE_VIEJO]
    assert get_saldo_materia_prima(db, tomate.id) == TOMATE_INICIAL - 2 * TOMATE_VIEJO

    _corregir_receta(db, tomate)

    reprocesados = script.reprocesar(db, apply=True, log=lambda *_: None)
    db.commit()

    assert len(reprocesados) == 2
    assert _consumo_vivo(db, tomate.id) == [TOMATE_NUEVO, TOMATE_NUEVO]
    # The other line didn't change, so it must not be double-counted either.
    assert _consumo_vivo(db, harina.id) == [HARINA_G / 1000, HARINA_G / 1000]


def test_un_conteo_posterior_sigue_mandando_sobre_el_stock_actual(client, db):
    """Reprocessing a backdated record corrects the ledger, not the running total.

    Stock MP is a running total: every consumption INSERTs an InventarioRegistro
    carrying the resulting balance, and get_saldo_materia_prima() reads the
    latest one by (fecha_registro, id). revertir_consumos deliberately dates its
    give-back to the record's own date (see its docstring), so re-running an old
    production writes rows that a later manual count outranks -- which is the
    behaviour we want here: the count IS the truth for "how much is on the
    shelf", and what was wrong was the ledger, which is what `calculado`
    compares against. This mirrors production exactly: Tomate was counted at
    4,00 L on 24/09, after both pizza batches.
    """
    headers = _auth(client, db)
    _, tomate = _mundo(db)
    _producir(client, headers, AYER)
    _corregir_receta(db, tomate)

    contado = 4.0
    db.add(InventarioRegistro(ingrediente_id=tomate.id, cantidad=contado, unidad="litro",
                              fecha_registro=HOY))
    db.commit()

    script.reprocesar(db, apply=True, log=lambda *_: None)
    db.commit()

    assert get_saldo_materia_prima(db, tomate.id) == contado
    assert _consumo_vivo(db, tomate.id) == [TOMATE_NUEVO]


def test_el_dry_run_no_escribe(client, db):
    headers = _auth(client, db)
    _, tomate = _mundo(db)
    _producir(client, headers, HOY)
    _corregir_receta(db, tomate)

    antes = db.query(MovimientoStock).count()
    reprocesados = script.reprocesar(db, apply=False, log=lambda *_: None)

    assert reprocesados == [1]  # reported, not applied
    assert db.query(MovimientoStock).count() == antes
    assert _consumo_vivo(db, tomate.id) == [TOMATE_VIEJO]


def test_es_idempotente(client, db):
    headers = _auth(client, db)
    _, tomate = _mundo(db)
    _producir(client, headers, HOY)
    _corregir_receta(db, tomate)

    script.reprocesar(db, apply=True, log=lambda *_: None)
    db.commit()
    movimientos = db.query(MovimientoStock).count()

    assert script.reprocesar(db, apply=True, log=lambda *_: None) == []
    db.commit()
    assert db.query(MovimientoStock).count() == movimientos
    assert _consumo_vivo(db, tomate.id) == [TOMATE_NUEVO]
    assert get_saldo_materia_prima(db, tomate.id) == TOMATE_INICIAL - TOMATE_NUEVO


def test_no_toca_una_produccion_que_ya_coincide(client, db):
    """A record logged after the recipe was fixed is left exactly as it is."""
    headers = _auth(client, db)
    _, tomate = _mundo(db)
    _corregir_receta(db, tomate)
    _producir(client, headers, HOY)

    antes = db.query(MovimientoStock).count()
    assert script.reprocesar(db, apply=True, log=lambda *_: None) == []
    assert db.query(MovimientoStock).count() == antes
