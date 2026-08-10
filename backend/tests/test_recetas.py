from app.main import app
from app.routers.recetas import router
app.include_router(router)

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, User


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat_i = Categoria(nombre="Harinas", tipo="ingrediente")
    cat_r = Categoria(nombre="Panes", tipo="receta", margen_objetivo=60)
    db.add_all([cat_i, cat_r])
    db.commit()

    harina = Ingrediente(
        nombre="Harina", categoria_id=cat_i.id,
        unidad_compra="kg", cantidad_compra=25,
        precio_compra=5000, unidad_uso="g",
    )
    db.add(harina)
    db.commit()

    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, cat_r.id, harina.id


def test_create_receta_with_lines(client, db):
    token, cat_id, harina_id = _setup(client, db)
    res = client.post("/api/recetas", json={
        "nombre": "Pan Francés",
        "categoria_id": cat_id,
        "porciones_por_lote": 20,
        "precio_venta": 500,
        "lineas": [
            {"ingrediente_id": harina_id, "cantidad": 1000, "unidad": "g"},
        ],
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    data = res.json()
    assert data["nombre"] == "Pan Francés"
    assert data["costo_total"] > 0
    assert data["costo_por_porcion"] > 0
    assert data["margen"] is not None
    assert data["multi"] is not None
    assert len(data["lineas"]) == 1


def test_update_receta_replaces_lines(client, db):
    token, cat_id, harina_id = _setup(client, db)
    created = client.post("/api/recetas", json={
        "nombre": "Pan", "categoria_id": cat_id, "porciones_por_lote": 10,
        "lineas": [{"ingrediente_id": harina_id, "cantidad": 500, "unidad": "g"}],
    }, headers={"Authorization": f"Bearer {token}"})
    rec_id = created.json()["id"]

    res = client.put(f"/api/recetas/{rec_id}", json={
        "lineas": [{"ingrediente_id": harina_id, "cantidad": 1000, "unidad": "g"}],
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["lineas"][0]["cantidad"] == 1000


def test_delete_receta(client, db):
    token, cat_id, harina_id = _setup(client, db)
    created = client.post("/api/recetas", json={
        "nombre": "Pan", "categoria_id": cat_id, "porciones_por_lote": 1,
        "lineas": [],
    }, headers={"Authorization": f"Bearer {token}"})
    rec_id = created.json()["id"]
    res = client.delete(f"/api/recetas/{rec_id}",
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
