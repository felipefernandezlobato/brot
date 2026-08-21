"""Direct unit tests for services.stock.ajustar_correccion_conteo -- the
ledger-adjustment primitive kept in the service layer but NOT wired into
PUT /api/inventario/{id} or PUT /api/congelados/{id} (those are plain record
corrections, see test_conteo_manual_correccion.py and both routers'
docstrings for why editing a count and syncing the ledger are kept as two
separate actions). This primitive is still the sanctioned, tested way to
fix a genuinely wrong ledger baseline (a mis-set carga_inicial) without
hand-editing MovimientoStock -- used directly against production for the
Aceite Girasol / Canela / Huevos incidents on 2026-08-21.
"""
from datetime import date

from app.models import MovimientoStock
from app.services.stock import ajustar_correccion_conteo


def _carga_inicial(db, tipo_stock, producto_id, cantidad, unidad, fecha) -> int:
    mov = MovimientoStock(
        tipo_stock=tipo_stock, referencia_producto_id=producto_id, cantidad=cantidad,
        unidad=unidad, tipo_movimiento="carga_inicial", referencia_origen="carga_inicial:historico",
        fecha=fecha,
    )
    db.add(mov)
    db.commit()
    return mov.id


def _movimiento_real(db, tipo_stock, producto_id, cantidad, unidad, tipo_movimiento, fecha, ref="registro_produccion:1"):
    db.add(MovimientoStock(
        tipo_stock=tipo_stock, referencia_producto_id=producto_id, cantidad=cantidad,
        unidad=unidad, tipo_movimiento=tipo_movimiento, referencia_origen=ref, fecha=fecha,
    ))
    db.commit()


def _ledger_sum(db, tipo_stock, producto_id) -> float:
    movs = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == tipo_stock,
        MovimientoStock.referencia_producto_id == producto_id,
    ).all()
    return round(sum(m.cantidad for m in movs), 6)


def test_corrige_carga_inicial_en_el_lugar_cuando_es_el_unico_y_misma_fecha(db):
    """Replica el caso real (Aceite Girasol): un carga_inicial mal cargado
    (4kg) es el UNICO movimiento, fechado el mismo dia del registro que se
    corrige -- nunca fue un evento real, asi que se edita en el lugar en
    vez de dejar un +4/-1 colgando para siempre."""
    carga_id = _carga_inicial(db, "materia_prima", 11, 4.0, "kg", date(2026, 8, 13))

    resultado = ajustar_correccion_conteo(db, "materia_prima", 11, 501, 3.0, "kg", date(2026, 8, 13))
    db.commit()

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 3.0
    assert carga.saldo_despues == 3.0
    assert carga.tipo_movimiento == "carga_inicial"  # edited in place, not superseded
    assert resultado.id == carga_id
    assert db.query(MovimientoStock).filter(MovimientoStock.tipo_movimiento == "correccion_conteo").count() == 0
    assert _ledger_sum(db, "materia_prima", 11) == 3.0


def test_no_corrompe_un_carga_inicial_de_otra_fecha(db):
    """Bug real (2026-08-21): con un carga_inicial del 13/08 como UNICO
    movimiento previo, corregir un conteo de una fecha POSTERIOR (20/08, sin
    nada real en el medio) coincidia con "un solo movimiento previo" y
    sobreescribia el carga_inicial del 13/08 -- arreglaba una fecha
    corrompiendo otra. Debe usar el camino de correccion aparte, fechada al
    20/08, dejando el 13/08 intacto."""
    carga_id = _carga_inicial(db, "materia_prima", 11, 4.0, "kg", date(2026, 8, 13))

    ajustar_correccion_conteo(db, "materia_prima", 11, 502, 3.0, "kg", date(2026, 8, 20))
    db.commit()

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 4.0  # 13/08 untouched
    assert str(carga.fecha) == "2026-08-13"

    correccion = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_movimiento == "correccion_conteo",
        MovimientoStock.referencia_producto_id == 11,
    ).first()
    assert correccion.cantidad == -1.0
    assert str(correccion.fecha) == "2026-08-20"
    assert _ledger_sum(db, "materia_prima", 11) == 3.0


def test_con_movimiento_real_usa_correccion_aparte(db):
    """En cuanto hay un movimiento real (no solo el carga_inicial) en la
    fecha del conteo, corregir NO edita el carga_inicial -- inserta una
    correccion aparte, para no reescribir un evento real."""
    carga_id = _carga_inicial(db, "materia_prima", 11, 4.0, "kg", date(2026, 8, 13))
    _movimiento_real(db, "materia_prima", 11, -0.5, "kg", "produccion_consumo", date(2026, 8, 13))

    ajustar_correccion_conteo(db, "materia_prima", 11, 503, 3.0, "kg", date(2026, 8, 13))
    db.commit()

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 4.0  # untouched

    correccion = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_movimiento == "correccion_conteo",
        MovimientoStock.referencia_producto_id == 11,
    ).first()
    assert correccion.cantidad == -0.5  # 3.0 - (4.0 - 0.5)
    assert _ledger_sum(db, "materia_prima", 11) == 3.0


def test_reeditar_no_apila_la_correccion(db):
    """Reeditar el mismo registro (identificado por registro_id) no debe
    dejar dos correcciones vivas -- la primera se revierte antes de aplicar
    la segunda."""
    carga_id = _carga_inicial(db, "materia_prima", 11, 4.0, "kg", date(2026, 8, 13))
    _movimiento_real(db, "materia_prima", 11, -0.5, "kg", "produccion_consumo", date(2026, 8, 13))

    ajustar_correccion_conteo(db, "materia_prima", 11, 504, 3.0, "kg", date(2026, 8, 13))
    ajustar_correccion_conteo(db, "materia_prima", 11, 504, 2.0, "kg", date(2026, 8, 13))
    db.commit()

    vivos = db.query(MovimientoStock).filter(
        MovimientoStock.referencia_origen == "correccion_conteo:materia_prima:504",
    ).all()
    assert len(vivos) == 1
    assert _ledger_sum(db, "materia_prima", 11) == 2.0
    assert db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first().cantidad == 4.0


def test_reeditar_colapsa_correccion_vieja_de_vuelta_al_carga_inicial(db):
    """Un registro que ya tenia una correccion aparte (por ejemplo, insertada
    manualmente con este mismo primitivo en el pasado) se debe reabsorber al
    reeditarlo si ya no hay ningun movimiento real de por medio -- no debe
    quedar apilada para siempre solo porque alguna vez existio."""
    carga_id = _carga_inicial(db, "materia_prima", 11, 4.0, "kg", date(2026, 8, 13))
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=11, cantidad=-1.0,
        unidad="kg", tipo_movimiento="correccion_conteo",
        referencia_origen="correccion_conteo:materia_prima:505", fecha=date(2026, 8, 13),
    ))
    db.commit()

    ajustar_correccion_conteo(db, "materia_prima", 11, 505, 0.22, "kg", date(2026, 8, 13))
    db.commit()

    carga = db.query(MovimientoStock).filter(MovimientoStock.id == carga_id).first()
    assert carga.cantidad == 0.22
    vivos = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_movimiento == "correccion_conteo",
        MovimientoStock.referencia_producto_id == 11,
        MovimientoStock.referencia_origen == "correccion_conteo:materia_prima:505",
    ).all()
    assert vivos == []  # the old one was reverted (retagged to :rev), nothing live remains
    assert _ledger_sum(db, "materia_prima", 11) == 0.22


def test_sin_baseline_previo_actua_como_carga_inicial(db):
    """Un item sin ningun movimiento previo: corregir su conteo debe fijar
    el ledger en el valor corregido, igual que si
    scripts/reconciliar_ledger_materia_prima.py lo hubiera hecho."""
    ajustar_correccion_conteo(db, "materia_prima", 11, 506, 3.0, "kg", date(2026, 8, 13))
    db.commit()

    assert _ledger_sum(db, "materia_prima", 11) == 3.0
