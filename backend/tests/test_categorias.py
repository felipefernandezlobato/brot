from app.main import app
from app.routers.categorias import router

app.include_router(router)

from app.auth import hash_pin
from app.models import User


def _admin_token(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    res = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"})
    return res.json()["token"]


def test_create_categoria(client, db):
    token = _admin_token(client, db)
    res = client.post("/api/categorias", json={
        "nombre": "Panes", "tipo": "receta", "margen_objetivo": 60
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    assert res.json()["nombre"] == "Panes"


def test_list_categorias(client, db):
    token = _admin_token(client, db)
    client.post("/api/categorias", json={"nombre": "A", "tipo": "ingrediente"},
                headers={"Authorization": f"Bearer {token}"})
    client.post("/api/categorias", json={"nombre": "B", "tipo": "receta"},
                headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/categorias", headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 2


def test_list_categorias_filter_tipo(client, db):
    token = _admin_token(client, db)
    client.post("/api/categorias", json={"nombre": "A", "tipo": "ingrediente"},
                headers={"Authorization": f"Bearer {token}"})
    client.post("/api/categorias", json={"nombre": "B", "tipo": "receta"},
                headers={"Authorization": f"Bearer {token}"})
    res = client.get("/api/categorias?tipo=ingrediente",
                     headers={"Authorization": f"Bearer {token}"})
    assert len(res.json()) == 1


def test_update_categoria(client, db):
    token = _admin_token(client, db)
    created = client.post("/api/categorias", json={"nombre": "Old", "tipo": "receta"},
                          headers={"Authorization": f"Bearer {token}"})
    cat_id = created.json()["id"]
    res = client.put(f"/api/categorias/{cat_id}", json={"nombre": "New"},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.json()["nombre"] == "New"


def test_delete_categoria(client, db):
    token = _admin_token(client, db)
    created = client.post("/api/categorias", json={"nombre": "Del", "tipo": "receta"},
                          headers={"Authorization": f"Bearer {token}"})
    cat_id = created.json()["id"]
    res = client.delete(f"/api/categorias/{cat_id}",
                        headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
