"""Stock effects of production records: apply, edit-overwrite, reverse.

These cover the two bugs this module was built to fix:
  1. Completing a task without a quantity silently skipped the deduction.
  2. "1 receta" was read as "1 portion", deducting 1/porciones_por_lote of the recipe.
"""

from datetime import date, timedelta

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
    StockCongelado,
    TareaProduccion,
    User,
)
from app.routers.produccion import router

app.include_router(router)

HOY = date.today().isoformat()


def _auth(client, db):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _harina(db, stock_kg=100.0, contado_hace_dias=0):
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
        ingrediente_id=ing.id, cantidad=stock_kg, unidad="kg",
        fecha_registro=date.today() - timedelta(days=contado_hace_dias),
    ))
    db.commit()
    return ing


def _masa(db, ing, harina_g=12000.0, porciones=1.0):
    """A masa recipe + its frozen product + the calendar task that makes it."""
    cat = Categoria(nombre="Masas", tipo="receta")
    db.add(cat)
    db.flush()
    receta = Receta(nombre="Masa Pan Blanco", categoria_id=cat.id,
                    porciones_por_lote=porciones, es_subreceta=True)
    db.add(receta)
    db.flush()
    db.add(LineaReceta(receta_id=receta.id, ingrediente_id=ing.id, cantidad=harina_g, unidad="g"))

    prod = ProductoCongelado(nombre="Masa Pan Blanco", categoria="masas", unidad="u",
                             receta_id=receta.id, nivel="masa")
    db.add(prod)
    db.flush()

    tarea = TareaProduccion(
        dia_semana=1, hora="08:00", titulo="Amasar Pan Blanco",
        cantidad_planificada=1.0, unidad_cantidad="u receta",
        receta_id=receta.id, producto_congelado_id=prod.id, tipo="produccion",
    )
    db.add(tarea)
    db.commit()
    return receta, prod, tarea


def _saldo(db, ing_id):
    reg = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
    )
    return reg.cantidad


def _guardar(client, headers, tarea_id, cantidad, completada=True):
    return client.post(
        "/api/produccion/registro",
        json={
            "tarea_id": tarea_id, "fecha": HOY, "completada": completada,
            "cantidad_real": cantidad, "duracion_real": None, "notas": None,
        },
        headers=headers,
    )


# ==============================================================
# Bug 1 — completing without a quantity
# ==============================================================


def test_no_se_puede_completar_sin_cantidad(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _, _, tarea = _masa(db, ing)

    res = _guardar(client, headers, tarea.id, None)

    assert res.status_code == 422
    assert "cantidad" in res.json()["detail"].lower()
    assert _saldo(db, ing.id) == 100.0


def test_guardar_con_cantidad_descuenta(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    res = _guardar(client, headers, tarea.id, 1)

    assert res.status_code == 201, res.text
    assert res.json()["stock_aplicado"] is True
    assert _saldo(db, ing.id) == 88.0  # 100 - 12


# ==============================================================
# Bug 2 — "u receta" must mean whole batches, not portions
# ==============================================================


def test_una_receta_descuenta_la_receta_completa(client, db):
    """Masa Croissant rinde 9 bastones. 1 receta debe descontar los 19.5 kg, no 1/9."""
    headers = _auth(client, db)
    ing = _harina(db, stock_kg=100.0)
    _masa(db, ing, harina_g=19500.0, porciones=9.0)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 1)

    assert _saldo(db, ing.id) == 80.5  # 100 - 19.5, NOT 100 - 2.167


def test_media_receta_descuenta_la_mitad(client, db):
    headers = _auth(client, db)
    ing = _harina(db, stock_kg=100.0)
    _masa(db, ing, harina_g=19500.0, porciones=9.0)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 0.5)

    assert _saldo(db, ing.id) == 90.25  # 100 - 9.75


# ==============================================================
# Edit overwrites instead of stacking
# ==============================================================


def test_editar_sobrescribe_no_suma(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 1)
    assert _saldo(db, ing.id) == 88.0

    _guardar(client, headers, tarea.id, 2)

    # 2 recetas = 24 kg. Must be 100-24, not 100-12-24.
    assert _saldo(db, ing.id) == 76.0


def test_editar_hacia_abajo_devuelve_stock(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 3)
    assert _saldo(db, ing.id) == 64.0

    _guardar(client, headers, tarea.id, 1)

    assert _saldo(db, ing.id) == 88.0


def test_editar_un_dia_pasado_no_corrompe_el_saldo(client, db):
    """Regression: the reversal must be dated like the production it undoes.

    get_saldo_materia_prima takes the latest InventarioRegistro by (fecha, id). A
    today-dated give-back would outrank the same-transaction re-apply dated in the
    past, and the corrected consumption would vanish from the balance.
    """
    headers = _auth(client, db)
    # Counted before the production, so the production is what moves the balance.
    ing = _harina(db, contado_hace_dias=14)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()
    hace_una_semana = (date.today() - timedelta(days=7)).isoformat()

    def guardar(cantidad):
        return client.post(
            "/api/produccion/registro",
            json={"tarea_id": tarea.id, "fecha": hace_una_semana,
                  "completada": True, "cantidad_real": cantidad},
            headers=headers,
        )

    guardar(1)
    assert _saldo(db, ing.id) == 88.0

    guardar(2)

    assert _saldo(db, ing.id) == 76.0  # 100 - 24, not 100


def test_guardar_dos_veces_lo_mismo_es_idempotente(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 1)
    _guardar(client, headers, tarea.id, 1)
    _guardar(client, headers, tarea.id, 1)

    assert _saldo(db, ing.id) == 88.0


def test_el_ledger_neto_queda_en_cero_tras_revertir(client, db):
    """Charts sum MovimientoStock, so a reversed production must net to zero."""
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 1)
    _guardar(client, headers, tarea.id, completada=False, cantidad=1)

    total = sum(
        m.cantidad for m in db.query(MovimientoStock)
        .filter(MovimientoStock.tipo_stock == "materia_prima",
                MovimientoStock.referencia_producto_id == ing.id)
        .all()
    )
    assert abs(total) < 1e-9


# ==============================================================
# Uncheck / delete
# ==============================================================


def test_desmarcar_devuelve_el_stock(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    _guardar(client, headers, tarea.id, 1)
    assert _saldo(db, ing.id) == 88.0

    _guardar(client, headers, tarea.id, cantidad=1, completada=False)

    assert _saldo(db, ing.id) == 100.0


def test_borrar_registro_devuelve_el_stock(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _masa(db, ing)
    tarea = db.query(TareaProduccion).first()

    reg_id = _guardar(client, headers, tarea.id, 1).json()["id"]
    assert _saldo(db, ing.id) == 88.0

    res = client.delete(f"/api/produccion/registro/{reg_id}", headers=headers)

    assert res.status_code == 200
    assert _saldo(db, ing.id) == 100.0


def test_produccion_congelada_se_revierte(client, db):
    headers = _auth(client, db)
    ing = _harina(db)
    _, prod, tarea = _masa(db, ing)

    _guardar(client, headers, tarea.id, 2)
    activos = db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == prod.id,
        StockCongelado.is_active.is_(True),
    ).all()
    assert sum(e.cantidad for e in activos) == 2.0

    _guardar(client, headers, tarea.id, cantidad=2, completada=False)

    activos = db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == prod.id,
        StockCongelado.is_active.is_(True),
    ).all()
    assert sum(e.cantidad for e in activos) == 0.0


# ==============================================================
# Multi-level chain: masa -> baston
# ==============================================================


def _cadena(db, ing):
    """Masa (from flour) -> Baston (from masa). Mirrors the real production chain."""
    _, masa_prod, masa_tarea = _masa(db, ing, harina_g=19500.0, porciones=9.0)

    cat = db.query(Categoria).filter(Categoria.tipo == "receta").first()
    r_bast = Receta(nombre="Baston Croissant", categoria_id=cat.id,
                    porciones_por_lote=1.0, es_subreceta=True)
    db.add(r_bast)
    db.flush()

    baston = ProductoCongelado(
        nombre="Baston Croissant", categoria="semis", unidad="u", receta_id=r_bast.id,
        nivel="semi", producto_padre_id=masa_prod.id, cantidad_por_padre=1.0,
    )
    db.add(baston)
    db.flush()

    t_bast = TareaProduccion(
        dia_semana=1, hora="09:00", titulo="Laminar Croissant",
        cantidad_planificada=9.0, unidad_cantidad="bastones",
        receta_id=r_bast.id, producto_congelado_id=baston.id, tipo="produccion",
    )
    db.add(t_bast)
    db.commit()
    return masa_prod, masa_tarea, baston, t_bast


def _stock_congelado(db, prod_id):
    return sum(
        e.cantidad for e in db.query(StockCongelado).filter(
            StockCongelado.producto_congelado_id == prod_id,
            StockCongelado.is_active.is_(True),
        )
    )


def test_consumo_de_padre_se_revierte_al_lote_original(client, db):
    headers = _auth(client, db)
    ing = _harina(db, stock_kg=200.0)
    masa_prod, masa_tarea, baston, t_bast = _cadena(db, ing)

    _guardar(client, headers, masa_tarea.id, 1)       # 1 receta -> 9 u de masa
    assert _stock_congelado(db, masa_prod.id) == 9.0

    _guardar(client, headers, t_bast.id, 4)           # consume 4 u de masa
    assert _stock_congelado(db, masa_prod.id) == 5.0

    _guardar(client, headers, t_bast.id, cantidad=4, completada=False)

    # The masa must come back on its ORIGINAL lot, not as a new one.
    assert _stock_congelado(db, masa_prod.id) == 9.0
    lotes = db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == masa_prod.id,
        StockCongelado.is_active.is_(True),
    ).all()
    assert len(lotes) == 1


def test_editar_produccion_ya_consumida_aguas_abajo(client, db):
    """The case that used to crash: revert a batch a later step already ate."""
    headers = _auth(client, db)
    ing = _harina(db, stock_kg=200.0)
    masa_prod, masa_tarea, baston, t_bast = _cadena(db, ing)

    _guardar(client, headers, masa_tarea.id, 1)   # 9 u de masa
    _guardar(client, headers, t_bast.id, 9)       # se consume TODA la masa
    assert _stock_congelado(db, masa_prod.id) == 0.0

    res = _guardar(client, headers, masa_tarea.id, 2)  # ahora fueron 2 recetas
    assert res.status_code == 201, res.text

    # 18 produced, 9 already consumed -> 9 left. Net stays honest.
    assert _stock_congelado(db, masa_prod.id) == 9.0
    assert _saldo(db, ing.id) == 161.0  # 200 - 39


# ==============================================================
# Tasks with no product still work as plain checkboxes
# ==============================================================


def test_tarea_sin_producto_se_completa_sin_cantidad(client, db):
    headers = _auth(client, db)
    tarea = TareaProduccion(
        dia_semana=1, hora="06:00", titulo="Limpieza", tipo="limpieza",
    )
    db.add(tarea)
    db.commit()

    res = _guardar(client, headers, tarea.id, None)

    assert res.status_code == 201
    assert res.json()["completada"] is True
    assert res.json()["stock_aplicado"] is False
