"""Recipe lines must reference exactly one of ingrediente/subreceta, and a
subreceta chain must never be able to reference itself, directly or transitively.

Before this validation existed, every subreceta wiring (Masa Madre, Pure, the
Focaccia rework) had to be done by hand via one-off scripts because nothing
stopped a line from having both ids, neither, or a cycle.
"""

from datetime import date

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, LineaReceta, Receta, User
from app.services.recetas_validacion import detectar_ciclo, validar_lineas_receta, validar_xor_lineas

HOY = date.today().isoformat()


def _auth(client, db):
    db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _categoria(db):
    cat = Categoria(nombre="Panes", tipo="receta")
    db.add(cat)
    db.flush()
    return cat


def _ingrediente(db):
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat.id, unidad_compra="kg", unidad_uso="kg",
        precio_compra=760.0, cantidad_compra=1.0,
    )
    db.add(ing)
    db.commit()
    return ing


def _receta(db, cat_id, nombre="Receta"):
    r = Receta(nombre=nombre, categoria_id=cat_id, porciones_por_lote=1)
    db.add(r)
    db.flush()
    return r


def _linea(receta_id, subreceta_id):
    l = LineaReceta(receta_id=receta_id, subreceta_id=subreceta_id, cantidad=1, unidad="unidad")
    return l


# ==============================================================
# validar_xor_lineas — pure unit tests
# ==============================================================


def test_xor_rejects_both_ids_set():
    lineas = [{"ingrediente_id": 1, "subreceta_id": 2, "cantidad": 1, "unidad": "kg"}]
    try:
        validar_xor_lineas(lineas)
        assert False, "should have raised"
    except ValueError:
        pass


def test_xor_rejects_neither_id_set():
    lineas = [{"ingrediente_id": None, "subreceta_id": None, "cantidad": 1, "unidad": "kg"}]
    try:
        validar_xor_lineas(lineas)
        assert False, "should have raised"
    except ValueError:
        pass


def test_xor_accepts_ingrediente_only():
    validar_xor_lineas([{"ingrediente_id": 1, "subreceta_id": None, "cantidad": 1, "unidad": "kg"}])


def test_xor_accepts_subreceta_only():
    validar_xor_lineas([{"ingrediente_id": None, "subreceta_id": 5, "cantidad": 1, "unidad": "unidad"}])


# ==============================================================
# detectar_ciclo — pure unit tests against a real (sqlite) db
# ==============================================================


def test_ciclo_none_for_brand_new_recipe(db):
    cat = _categoria(db)
    b = _receta(db, cat.id, "B")
    db.commit()
    assert detectar_ciclo(db, None, b.id) is False


def test_ciclo_self_reference(db):
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    db.commit()
    assert detectar_ciclo(db, a.id, a.id) is True


def test_ciclo_two_hop(db):
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    b = _receta(db, cat.id, "B")
    db.add(_linea(b.id, a.id))  # B already uses A as subreceta
    db.commit()
    # Now trying to make A use B would close the loop A -> B -> A
    assert detectar_ciclo(db, a.id, b.id) is True


def test_ciclo_three_hop(db):
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    b = _receta(db, cat.id, "B")
    c = _receta(db, cat.id, "C")
    db.add(_linea(b.id, c.id))  # B -> C
    db.add(_linea(c.id, a.id))  # C -> A
    db.commit()
    # A -> B would close A -> B -> C -> A
    assert detectar_ciclo(db, a.id, b.id) is True


def test_ciclo_diamond_no_false_positive(db):
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    b = _receta(db, cat.id, "B")
    c = _receta(db, cat.id, "C")
    d = _receta(db, cat.id, "D")
    db.add(_linea(b.id, d.id))  # B -> D
    db.add(_linea(c.id, d.id))  # C -> D
    db.commit()
    # A -> B and A -> C is a diamond (A->B->D, A->C->D), not a cycle
    assert detectar_ciclo(db, a.id, b.id) is False
    assert detectar_ciclo(db, a.id, c.id) is False


def test_ciclo_no_false_positive_on_valid_nesting(db):
    cat = _categoria(db)
    masa = _receta(db, cat.id, "Masa")
    terminado = _receta(db, cat.id, "Terminado")
    db.commit()
    assert detectar_ciclo(db, terminado.id, masa.id) is False


# ==============================================================
# validar_lineas_receta — combined XOR + cycle check
# ==============================================================


def test_validar_lineas_receta_raises_on_cycle(db):
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    b = _receta(db, cat.id, "B")
    db.add(_linea(b.id, a.id))  # B -> A
    db.commit()
    try:
        validar_lineas_receta(db, a.id, [{"ingrediente_id": None, "subreceta_id": b.id, "cantidad": 1, "unidad": "u"}])
        assert False, "should have raised"
    except ValueError:
        pass


# ==============================================================
# End-to-end via API — create_receta / update_receta
# ==============================================================


def test_create_receta_rejects_line_with_both_ids(client, db):
    headers = _auth(client, db)
    cat = _categoria(db)
    ing = _ingrediente(db)
    db.commit()
    body = {
        "nombre": "Pan", "categoria_id": cat.id, "porciones_por_lote": 1,
        "lineas": [{"ingrediente_id": ing.id, "subreceta_id": 999, "cantidad": 1, "unidad": "kg"}],
    }
    resp = client.post("/api/recetas", json=body, headers=headers)
    assert resp.status_code == 422


def test_create_receta_accepts_subreceta_line(client, db):
    headers = _auth(client, db)
    cat = _categoria(db)
    sub = _receta(db, cat.id, "Masa Madre")
    db.commit()
    body = {
        "nombre": "Pan de Masa Madre", "categoria_id": cat.id, "porciones_por_lote": 1,
        "lineas": [{"ingrediente_id": None, "subreceta_id": sub.id, "cantidad": 1, "unidad": "kg"}],
    }
    resp = client.post("/api/recetas", json=body, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["lineas"][0]["subreceta_id"] == sub.id


def test_update_receta_rejects_cycle(client, db):
    headers = _auth(client, db)
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    b = _receta(db, cat.id, "B")
    db.add(_linea(b.id, a.id))  # B already uses A as subreceta
    db.commit()

    resp = client.put(
        f"/api/recetas/{a.id}",
        json={"lineas": [{"ingrediente_id": None, "subreceta_id": b.id, "cantidad": 1, "unidad": "u"}]},
        headers=headers,
    )
    assert resp.status_code == 422


def test_update_receta_without_lineas_not_validated(client, db):
    """Renaming a recipe (no `lineas` key) must not re-validate its existing lines."""
    headers = _auth(client, db)
    cat = _categoria(db)
    a = _receta(db, cat.id, "A")
    db.commit()
    resp = client.put(f"/api/recetas/{a.id}", json={"nombre": "A renombrada"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "A renombrada"
