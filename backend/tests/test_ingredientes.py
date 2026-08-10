from app.main import app
from app.routers.ingredientes import router

app.include_router(router)

from app.auth import hash_pin
from app.models import Categoria, User


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, cat.id


def test_create_ingrediente(client, db):
    token, cat_id = _setup(client, db)
    res = client.post("/api/ingredientes", json={
        "nombre": "Harina 000", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 25,
        "precio_compra": 5000, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    assert res.json()["nombre"] == "Harina 000"
    assert "costo_por_unidad_uso" in res.json()


def test_list_ingredientes(client, db):
    token, cat_id = _setup(client, db)
    client.post("/api/ingredientes", json={
        "nombre": "A", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 1,
        "precio_compra": 100, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/ingredientes", headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 1


def test_update_precio_creates_historial(client, db):
    token, cat_id = _setup(client, db)
    created = client.post("/api/ingredientes", json={
        "nombre": "Manteca", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 1,
        "precio_compra": 1000, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    ing_id = created.json()["id"]

    client.put(f"/api/ingredientes/{ing_id}", json={"precio_compra": 1200},
               headers={"Authorization": f"Bearer {token}"})

    res = client.get(f"/api/ingredientes/{ing_id}/historial",
                     headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 1
    assert res.json()[0]["precio_anterior"] == 1000
    assert res.json()[0]["precio_nuevo"] == 1200


def test_delete_blocked_if_in_recipe(client, db):
    token, cat_id = _setup(client, db)
    # Create ingredient
    ing = client.post("/api/ingredientes", json={
        "nombre": "X", "categoria_id": cat_id,
        "unidad_compra": "kg", "cantidad_compra": 1,
        "precio_compra": 100, "unidad_uso": "g",
    }, headers={"Authorization": f"Bearer {token}"})
    ing_id = ing.json()["id"]

    # Create recipe category + recipe using the ingredient
    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add(cat_r)
    db.commit()
    from app.models import LineaReceta, Receta
    receta = Receta(nombre="Pan", categoria_id=cat_r.id, porciones_por_lote=1)
    db.add(receta)
    db.flush()
    linea = LineaReceta(receta_id=receta.id, ingrediente_id=ing_id, cantidad=100, unidad="g")
    db.add(linea)
    db.commit()

    res = client.delete(f"/api/ingredientes/{ing_id}",
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 409
