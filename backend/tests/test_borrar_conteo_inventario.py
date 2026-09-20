"""Deleting a manual count has to undo its effect on the rows derived from it.

InventarioRegistro stores a running TOTAL, so every automatic row written after
a count carries that count's value forward. Dropping the count row on its own
leaves a miscount alive inside rows that outlive it.
"""

from datetime import date, timedelta

import pytest

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, InventarioRegistro, User

HOY = date.today()


def _setup(client, db):
    db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
    cat = Categoria(nombre="Azúcares", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Azúcar", categoria_id=cat.id, unidad_compra="kg", unidad_uso="kg",
        precio_compra=900.0, cantidad_compra=1.0,
    )
    db.add(ing)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}, ing.id


def _fila(db, ing_id, dias_atras, cantidad, notas=None):
    reg = InventarioRegistro(
        ingrediente_id=ing_id, cantidad=cantidad, unidad="kg",
        fecha_registro=HOY - timedelta(days=dias_atras), notas=notas,
    )
    db.add(reg)
    db.commit()
    return reg


def _totales(db, ing_id):
    return [
        (r.id, r.cantidad)
        for r in db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro, InventarioRegistro.id)
        .all()
    ]


def test_borrar_conteo_reajusta_las_filas_derivadas(client, db):
    """Azucar's exact shape: a good count, a bad count, then three consumos."""
    hdrs, ing_id = _setup(client, db)
    _fila(db, ing_id, 10, 47.0)                                             # conteo bueno
    _fila(db, ing_id, 3, 42.63, "Consumo automatico: registro_produccion:240")
    malo = _fila(db, ing_id, 3, 26.7)                                       # conteo mal contado
    c1 = _fila(db, ing_id, 2, 24.45, "Consumo automatico: registro_produccion:247")
    c2 = _fila(db, ing_id, 2, 22.85, "Consumo automatico: registro_produccion:248")
    c3 = _fila(db, ing_id, 2, 22.31, "Consumo automatico: registro_produccion:261")

    res = client.delete(f"/api/inventario/{malo.id}", headers=hdrs)

    assert res.status_code == 200, res.text
    assert res.json()["registros_reajustados"] == 3
    assert res.json()["delta"] == pytest.approx(42.63 - 26.7)

    db.expire_all()
    # Los consumos (-2.25, -1.60, -0.54) ahora salen de 42.63, no de 26.7.
    assert c1.cantidad == pytest.approx(40.38)
    assert c2.cantidad == pytest.approx(38.78)
    assert c3.cantidad == pytest.approx(38.24)
    assert db.query(InventarioRegistro).filter(InventarioRegistro.id == malo.id).first() is None


def test_el_reajuste_para_en_el_siguiente_conteo_manual(client, db):
    """A later count is an independent measurement -- it and what hangs off it
    are already right, so the shift must not reach them."""
    hdrs, ing_id = _setup(client, db)
    _fila(db, ing_id, 10, 47.0)
    malo = _fila(db, ing_id, 8, 26.7)
    derivada = _fila(db, ing_id, 7, 25.0, "Consumo automatico: registro_produccion:1")
    conteo_nuevo = _fila(db, ing_id, 5, 30.0)
    tras_conteo = _fila(db, ing_id, 4, 28.0, "Consumo automatico: registro_produccion:2")

    res = client.delete(f"/api/inventario/{malo.id}", headers=hdrs)

    assert res.status_code == 200, res.text
    assert res.json()["registros_reajustados"] == 1

    db.expire_all()
    assert derivada.cantidad == pytest.approx(25.0 + (47.0 - 26.7))
    assert conteo_nuevo.cantidad == pytest.approx(30.0)  # intacto
    assert tras_conteo.cantidad == pytest.approx(28.0)   # intacto


def test_borrar_una_fila_automatica_no_reajusta_nada(client, db):
    """Only a manual count distorts what follows it. Deleting an automatic row
    is a different thing entirely and must not shift anyone."""
    hdrs, ing_id = _setup(client, db)
    _fila(db, ing_id, 5, 47.0)
    automatica = _fila(db, ing_id, 4, 44.0, "Consumo automatico: registro_produccion:1")
    siguiente = _fila(db, ing_id, 3, 42.0, "Consumo automatico: registro_produccion:2")

    res = client.delete(f"/api/inventario/{automatica.id}", headers=hdrs)

    assert res.status_code == 200, res.text
    assert res.json()["registros_reajustados"] == 0

    db.expire_all()
    assert siguiente.cantidad == pytest.approx(42.0)


def test_borrar_el_primer_conteo_deja_el_resto_quieto(client, db):
    """With nothing before it there is no trajectory to fall back on -- don't
    invent one."""
    hdrs, ing_id = _setup(client, db)
    primero = _fila(db, ing_id, 5, 47.0)
    derivada = _fila(db, ing_id, 4, 44.0, "Consumo automatico: registro_produccion:1")

    res = client.delete(f"/api/inventario/{primero.id}", headers=hdrs)

    assert res.status_code == 200, res.text
    assert res.json()["registros_reajustados"] == 0

    db.expire_all()
    assert derivada.cantidad == pytest.approx(44.0)


def test_solo_toca_el_ingrediente_del_registro(client, db):
    hdrs, ing_id = _setup(client, db)
    otro = Ingrediente(
        nombre="Sal", categoria_id=1, unidad_compra="kg", unidad_uso="kg",
        precio_compra=340.0, cantidad_compra=1.0,
    )
    db.add(otro)
    db.commit()

    _fila(db, ing_id, 5, 47.0)
    malo = _fila(db, ing_id, 4, 26.7)
    _fila(db, ing_id, 3, 25.0, "Consumo automatico: registro_produccion:1")
    ajeno = _fila(db, otro.id, 3, 10.0, "Consumo automatico: registro_produccion:1")

    client.delete(f"/api/inventario/{malo.id}", headers=hdrs)

    db.expire_all()
    assert ajeno.cantidad == pytest.approx(10.0)
