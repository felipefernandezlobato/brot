"""The one-off that reprocesses the barra productions logged under the old chain.

Reproduces the real situation end to end: a barra terminado whose recipe carries
the whole dough formula as direct ingredient lines AND whose ProductoCongelado
hangs off Masa Pan Blanco, so producing it deducts both. Then applies the same
catalog rewiring scripts/crear_masas_barra.py does, and asserts the correction
endpoint leaves exactly one deduction of the ingredients and gives the pan dough
back.
"""

from datetime import date

import pytest

from app.auth import hash_pin
from app.main import app
from app.models import (
    Categoria,
    Ingrediente,
    InventarioRegistro,
    LineaReceta,
    MovimientoStock,
    ProductoCongelado,
    Receta,
    RegistroProduccion,
    StockCongelado,
    User,
)
from app.routers.produccion import router
from app.services.stock import get_saldo_congelado

app.include_router(router)

HOY = date.today()
HARINA_POR_LOTE_G = 5000.0
PORCIONES = 24.0


def _auth(client, db):
    db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _saldo_mp(db, ing_id):
    reg = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
    )
    return reg.cantidad


def _mundo_viejo(db):
    """Barra hanging off Masa Pan Blanco, with its dough formula as direct lines."""
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat.id, unidad_compra="kg", unidad_uso="kg",
        precio_compra=760.0, cantidad_compra=1.0,
    )
    db.add(ing)
    db.flush()
    db.add(InventarioRegistro(
        ingrediente_id=ing.id, cantidad=100.0, unidad="kg", fecha_registro=HOY,
    ))

    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add(cat_r)
    db.flush()

    masa_pan = Receta(nombre="Masa Pan Blanco", categoria_id=cat_r.id,
                      porciones_por_lote=1.0, es_subreceta=True)
    db.add(masa_pan)
    db.flush()
    pc_masa_pan = ProductoCongelado(nombre="Masa Pan Blanco", categoria="Masas", unidad="u",
                                    receta_id=masa_pan.id, nivel="masa")
    db.add(pc_masa_pan)
    db.flush()
    # Two lotes on the shelf, so the wrong deduction has somewhere to come from.
    db.add(StockCongelado(
        producto_congelado_id=pc_masa_pan.id, cantidad=2.0, cantidad_original=2.0,
        fecha_entrada=HOY, is_active=True,
    ))

    barra = Receta(nombre="Barra Blanca 350g", categoria_id=cat_r.id,
                   porciones_por_lote=PORCIONES, precio_venta=438.0)
    db.add(barra)
    db.flush()
    db.add(LineaReceta(receta_id=barra.id, ingrediente_id=ing.id,
                       cantidad=HARINA_POR_LOTE_G, unidad="g"))
    pc_barra = ProductoCongelado(
        nombre="Barra Blanca Cocinado", categoria="Panes", unidad="u",
        receta_id=barra.id, nivel="terminado",
        producto_padre_id=pc_masa_pan.id, cantidad_por_padre=PORCIONES,
    )
    db.add(pc_barra)
    db.commit()
    return ing, masa_pan, pc_masa_pan, barra, pc_barra


def _rewire(db, ing, barra, pc_barra):
    """What scripts/crear_masas_barra.py does: move the formula out to its own masa."""
    masa_barra = Receta(nombre="Masa Barra Blanca", categoria_id=barra.categoria_id,
                        porciones_por_lote=1.0, es_subreceta=False, unidad_rendimiento="u")
    db.add(masa_barra)
    db.flush()
    for linea in db.query(LineaReceta).filter(LineaReceta.receta_id == barra.id).all():
        linea.receta_id = masa_barra.id
    pc_masa_barra = ProductoCongelado(nombre="Masa Barra Blanca", categoria="Masas", unidad="u",
                                      receta_id=masa_barra.id, nivel="masa")
    db.add(pc_masa_barra)
    db.flush()
    db.add(LineaReceta(receta_id=barra.id, subreceta_id=masa_barra.id, cantidad=1.0, unidad="u"))
    pc_barra.producto_padre_id = pc_masa_barra.id
    pc_barra.cantidad_por_padre = PORCIONES
    db.commit()
    return masa_barra, pc_masa_barra


def test_corrige_el_doble_descuento(client, db, monkeypatch):
    from app.routers import produccion as router_mod

    headers = _auth(client, db)
    ing, _, pc_masa_pan, barra, pc_barra = _mundo_viejo(db)

    # 26 barras logged under the old chain -> ingredients AND pan dough.
    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "receta_id": barra.id, "cantidad_real": 26.0},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    registro_id = res.json()["id"]

    lotes = 26.0 / PORCIONES
    harina_lote_kg = HARINA_POR_LOTE_G / 1000
    assert _saldo_mp(db, ing.id) == pytest.approx(100.0 - harina_lote_kg * lotes)
    assert get_saldo_congelado(db, pc_masa_pan.id) == pytest.approx(2.0 - lotes)

    masa_barra, pc_masa_barra = _rewire(db, ing, barra, pc_barra)
    monkeypatch.setattr(
        router_mod, "_BARRAS_A_CORREGIR", [(registro_id, masa_barra.id, lotes)],
    )

    res = client.post("/api/produccion/corregir-barras-masa", headers=headers)
    assert res.status_code == 200, res.text
    assert len(res.json()["corregidos"]) == 1

    # Ingredients deducted exactly once -- by the amasado, not by the barras.
    assert _saldo_mp(db, ing.id) == pytest.approx(100.0 - harina_lote_kg * lotes)
    # The pan dough it never should have touched is back.
    assert get_saldo_congelado(db, pc_masa_pan.id) == pytest.approx(2.0)
    # The barra's own masa nets to zero: amasada and used the same day.
    assert get_saldo_congelado(db, pc_masa_barra.id) == pytest.approx(0.0)
    # The barras themselves are untouched.
    assert get_saldo_congelado(db, pc_barra.id) == pytest.approx(26.0)

    amasado = (
        db.query(RegistroProduccion)
        .filter(RegistroProduccion.receta_id == masa_barra.id)
        .one()
    )
    assert amasado.fecha == HOY
    assert amasado.cantidad_real == pytest.approx(lotes, abs=1e-4)


def test_es_idempotente(client, db, monkeypatch):
    from app.routers import produccion as router_mod

    headers = _auth(client, db)
    ing, _, pc_masa_pan, barra, pc_barra = _mundo_viejo(db)

    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "receta_id": barra.id, "cantidad_real": 26.0},
        headers=headers,
    )
    registro_id = res.json()["id"]
    lotes = 26.0 / PORCIONES

    masa_barra, pc_masa_barra = _rewire(db, ing, barra, pc_barra)
    monkeypatch.setattr(
        router_mod, "_BARRAS_A_CORREGIR", [(registro_id, masa_barra.id, lotes)],
    )

    client.post("/api/produccion/corregir-barras-masa", headers=headers)
    saldo_mp = _saldo_mp(db, ing.id)

    res = client.post("/api/produccion/corregir-barras-masa", headers=headers)

    assert res.status_code == 200
    assert res.json()["corregidos"] == []
    assert len(res.json()["omitidos"]) == 1
    assert _saldo_mp(db, ing.id) == pytest.approx(saldo_mp)
    assert get_saldo_congelado(db, pc_masa_pan.id) == pytest.approx(2.0)
    assert get_saldo_congelado(db, pc_masa_barra.id) == pytest.approx(0.0)
    assert (
        db.query(RegistroProduccion)
        .filter(RegistroProduccion.receta_id == masa_barra.id)
        .count()
    ) == 1


def test_registro_sin_ingredientes_previos_los_descuenta(client, db, monkeypatch):
    """Registro 88's shape: logged before the recipe was linked, so it only ever
    took pan dough and the flour for that batch was never deducted at all."""
    from app.routers import produccion as router_mod

    headers = _auth(client, db)
    ing, _, pc_masa_pan, barra, pc_barra = _mundo_viejo(db)

    # Strip the ingredient lines so producing deducts only the parent, which is
    # what PC 18 did while it had no receta_id at all.
    for linea in db.query(LineaReceta).filter(LineaReceta.receta_id == barra.id).all():
        db.delete(linea)
    db.commit()

    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "receta_id": barra.id, "cantidad_real": 24.0},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    registro_id = res.json()["id"]
    assert _saldo_mp(db, ing.id) == 100.0  # nothing came out of Stock MP
    assert get_saldo_congelado(db, pc_masa_pan.id) == pytest.approx(1.0)

    db.add(LineaReceta(receta_id=barra.id, ingrediente_id=ing.id,
                       cantidad=HARINA_POR_LOTE_G, unidad="g"))
    db.commit()
    masa_barra, pc_masa_barra = _rewire(db, ing, barra, pc_barra)
    monkeypatch.setattr(
        router_mod, "_BARRAS_A_CORREGIR", [(registro_id, masa_barra.id, 1.0)],
    )

    res = client.post("/api/produccion/corregir-barras-masa", headers=headers)
    assert res.status_code == 200, res.text

    assert _saldo_mp(db, ing.id) == pytest.approx(100.0 - HARINA_POR_LOTE_G / 1000)
    assert get_saldo_congelado(db, pc_masa_pan.id) == pytest.approx(2.0)
    assert get_saldo_congelado(db, pc_masa_barra.id) == pytest.approx(0.0)


def test_no_deja_movimientos_vivos_del_padre_viejo(client, db, monkeypatch):
    """The old pan-dough consumption must be retagged `:rev`, not left live --
    activity feeds filter on that tag."""
    from app.routers import produccion as router_mod

    headers = _auth(client, db)
    ing, _, pc_masa_pan, barra, pc_barra = _mundo_viejo(db)

    res = client.post(
        "/api/produccion/registro/extra",
        json={"fecha": HOY.isoformat(), "receta_id": barra.id, "cantidad_real": 26.0},
        headers=headers,
    )
    registro_id = res.json()["id"]
    lotes = 26.0 / PORCIONES

    masa_barra, _ = _rewire(db, ing, barra, pc_barra)
    monkeypatch.setattr(
        router_mod, "_BARRAS_A_CORREGIR", [(registro_id, masa_barra.id, lotes)],
    )
    client.post("/api/produccion/corregir-barras-masa", headers=headers)

    vivos = (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.referencia_origen == f"registro_produccion:{registro_id}",
            MovimientoStock.tipo_stock == "congelado",
            MovimientoStock.referencia_producto_id == pc_masa_pan.id,
        )
        .all()
    )
    assert vivos == []
