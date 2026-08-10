"""Tests for the mermas (waste/shrinkage) router."""
from app.main import app
from app.routers.mermas import router

app.include_router(router)

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, User


def _setup(client, db):
    """Create admin user, a category, and an ingredient; return token + ids."""
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)

    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.commit()

    # Ingredient: 25 kg for 5000 → 0.2 €/g (plus no merma)
    ing = Ingrediente(
        nombre="Harina 000",
        categoria_id=cat.id,
        unidad_compra="kg",
        cantidad_compra=25,
        precio_compra=5000,
        unidad_uso="g",
        merma_porcentaje=0.0,
    )
    db.add(ing)
    db.commit()

    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, ing.id


# ── test_create_merma_with_ingredient ─────────────────────────────────────────


def test_create_merma_with_ingredient(client, db):
    """Cost should be auto-calculated from the ingredient's unit cost."""
    token, ing_id = _setup(client, db)

    res = client.post(
        "/api/mermas",
        json={
            "ingrediente_id": ing_id,
            "cantidad": 500,       # 500 g
            "unidad": "g",
            "motivo": "caducado",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    body = res.json()

    # costo_por_unidad_uso = 5000 / (25 * 1000) = 0.2 €/g
    expected_cpu = 5000 / (25 * 1000)
    assert abs(body["coste_unitario"] - expected_cpu) < 1e-6
    assert abs(body["coste_total"] - expected_cpu * 500) < 1e-4
    assert body["motivo"] == "caducado"
    assert body["ingrediente_id"] == ing_id


# ── test_create_merma_free_text ───────────────────────────────────────────────


def test_create_merma_free_text(client, db):
    """Waste can be recorded without a linked ingredient (free-text name)."""
    token, _ = _setup(client, db)

    res = client.post(
        "/api/mermas",
        json={
            "nombre_libre": "Restos de decoración",
            "cantidad": 1,
            "unidad": "kg",
            "motivo": "otro",
            "coste_unitario": 200,
            "coste_total": 200,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["nombre_libre"] == "Restos de decoración"
    assert body["ingrediente_id"] is None
    assert body["coste_total"] == 200


# ── test_invalid_motivo ───────────────────────────────────────────────────────


def test_invalid_motivo_rejected(client, db):
    """Motivo must be one of the allowed values."""
    token, _ = _setup(client, db)

    res = client.post(
        "/api/mermas",
        json={
            "nombre_libre": "Algo",
            "cantidad": 1,
            "unidad": "kg",
            "motivo": "accidente",  # not valid
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422, res.text


# ── test_list_mermas_filter_motivo ────────────────────────────────────────────


def test_list_mermas_filter_motivo(client, db):
    """Listing with motivo filter returns only matching records."""
    token, ing_id = _setup(client, db)

    hdrs = {"Authorization": f"Bearer {token}"}
    base = {"cantidad": 100, "unidad": "g", "ingrediente_id": ing_id}

    client.post("/api/mermas", json={**base, "motivo": "caducado"}, headers=hdrs)
    client.post("/api/mermas", json={**base, "motivo": "caducado"}, headers=hdrs)
    client.post("/api/mermas", json={**base, "motivo": "dañado"}, headers=hdrs)

    res = client.get("/api/mermas?motivo=caducado", headers=hdrs)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert all(r["motivo"] == "caducado" for r in data)

    res2 = client.get("/api/mermas?motivo=dañado", headers=hdrs)
    assert len(res2.json()) == 1


# ── test_merma_analisis ───────────────────────────────────────────────────────


def test_merma_analisis(client, db):
    """Analysis endpoint returns aggregated totals, per-motivo breakdown, and top items."""
    token, ing_id = _setup(client, db)

    hdrs = {"Authorization": f"Bearer {token}"}

    # Create several waste records
    client.post("/api/mermas", json={
        "ingrediente_id": ing_id, "cantidad": 1000, "unidad": "g", "motivo": "caducado",
    }, headers=hdrs)
    client.post("/api/mermas", json={
        "ingrediente_id": ing_id, "cantidad": 500, "unidad": "g", "motivo": "dañado",
    }, headers=hdrs)
    client.post("/api/mermas", json={
        "nombre_libre": "Embalaje roto", "cantidad": 1, "unidad": "ud",
        "motivo": "otro", "coste_unitario": 10, "coste_total": 10,
    }, headers=hdrs)

    res = client.get("/api/mermas/analisis", headers=hdrs)
    assert res.status_code == 200, res.text
    body = res.json()

    assert "coste_total_global" in body
    assert "total_registros" in body
    assert "por_motivo" in body
    assert "top_items" in body

    assert body["total_registros"] == 3

    # Verify global cost > 0
    assert body["coste_total_global"] > 0

    # Per-motivo breakdown should have 3 entries
    motivos = {m["motivo"] for m in body["por_motivo"]}
    assert "caducado" in motivos
    assert "dañado" in motivos
    assert "otro" in motivos

    # Top items list shouldn't be empty
    assert len(body["top_items"]) > 0


# ── test_get_single_and_delete ────────────────────────────────────────────────


def test_get_single_and_delete(client, db):
    """Fetching and deleting a single merma record works correctly."""
    token, ing_id = _setup(client, db)
    hdrs = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/mermas", json={
        "ingrediente_id": ing_id, "cantidad": 200, "unidad": "g", "motivo": "produccion",
    }, headers=hdrs)
    merma_id = created.json()["id"]

    # GET single
    res = client.get(f"/api/mermas/{merma_id}", headers=hdrs)
    assert res.status_code == 200
    assert res.json()["id"] == merma_id

    # DELETE
    del_res = client.delete(f"/api/mermas/{merma_id}", headers=hdrs)
    assert del_res.status_code == 200
    assert del_res.json()["ok"] is True

    # 404 after deletion
    assert client.get(f"/api/mermas/{merma_id}", headers=hdrs).status_code == 404


# ── test_update_recalculates_coste_total ──────────────────────────────────────


def test_update_recalculates_coste_total(client, db):
    """Updating cantidad on a merma record recalculates coste_total."""
    token, ing_id = _setup(client, db)
    hdrs = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/mermas", json={
        "ingrediente_id": ing_id, "cantidad": 100, "unidad": "g", "motivo": "caducado",
    }, headers=hdrs)
    merma_id = created.json()["id"]
    original_cpu = created.json()["coste_unitario"]

    # Double the quantity
    res = client.put(f"/api/mermas/{merma_id}", json={"cantidad": 200}, headers=hdrs)
    assert res.status_code == 200
    body = res.json()
    assert abs(body["coste_total"] - original_cpu * 200) < 1e-4
