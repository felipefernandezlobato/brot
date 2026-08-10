from app.main import app
from app.routers.competencia import router

app.include_router(router)

from app.auth import hash_pin
from app.models import Categoria, Receta, User


def _setup(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    cat = Categoria(nombre="Panes", tipo="receta", margen_objetivo=50)
    db.add(cat)
    db.commit()
    receta = Receta(
        nombre="Pan de molde",
        categoria_id=cat.id,
        porciones_por_lote=10,
        precio_venta=3.50,
    )
    db.add(receta)
    db.commit()
    token = client.post(
        "/api/auth/login", json={"name": "Admin", "pin": "0000"}
    ).json()["token"]
    return token, receta.id


def test_add_competitor_price(client, db):
    token, receta_id = _setup(client, db)

    res = client.post(
        "/api/competencia",
        json={
            "receta_id": receta_id,
            "competidor_nombre": "Panaderia Rival",
            "precio": 4.00,
            "notas": "precio de lunes",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] is not None
    assert data["receta_id"] == receta_id
    assert data["competidor_nombre"] == "Panaderia Rival"
    assert data["precio"] == 4.00
    assert data["notas"] == "precio de lunes"
    assert data["fecha_registro"] is not None


def test_comparar_view(client, db):
    token, receta_id = _setup(client, db)

    # Add two competitor prices for the same recipe
    client.post(
        "/api/competencia",
        json={"receta_id": receta_id, "competidor_nombre": "Panaderia Rival", "precio": 4.00},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/competencia",
        json={"receta_id": receta_id, "competidor_nombre": "Panaderia Sur", "precio": 3.80},
        headers={"Authorization": f"Bearer {token}"},
    )

    res = client.get(
        "/api/competencia/comparar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

    # Find our recipe entry
    entry = next((r for r in data if r["receta_id"] == receta_id), None)
    assert entry is not None, "Recipe not found in comparar response"
    assert entry["receta_nombre"] == "Pan de molde"
    assert entry["pvp"] == 3.50
    assert len(entry["competidores"]) == 2

    nombres = {c["competidor_nombre"] for c in entry["competidores"]}
    assert "Panaderia Rival" in nombres
    assert "Panaderia Sur" in nombres
