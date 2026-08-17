"""historial_congelado_acumulado(): the shared cumulative-balance-from-ledger
helper behind the congelados detail page, the escandallos /completo endpoint,
and the Stock Congelado pivot table's calculated column.
"""
from datetime import date

from app.models import MovimientoStock
from app.services.stock import historial_congelado_acumulado


def _mov(db, producto_id, cantidad, fecha, tipo_stock="congelado"):
    db.add(MovimientoStock(
        tipo_stock=tipo_stock, referencia_producto_id=producto_id, cantidad=cantidad,
        unidad="u", tipo_movimiento="produccion_salida", fecha=fecha,
    ))


def test_running_balance_single_producto(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 1, -2.0, date(2026, 8, 15))
    db.commit()

    result = historial_congelado_acumulado(db, producto_ids=[1])

    assert result[1] == [
        {"fecha": "2026-08-14", "cantidad": 5.0},
        {"fecha": "2026-08-15", "cantidad": 3.0},
    ]


def test_same_day_movements_are_netted_before_accumulating(db):
    _mov(db, 1, 13.5, date(2026, 8, 14))
    _mov(db, 1, -1.5, date(2026, 8, 14))
    db.commit()

    result = historial_congelado_acumulado(db, producto_ids=[1])

    assert result[1] == [{"fecha": "2026-08-14", "cantidad": 12.0}]


def test_batched_across_products_no_cross_contamination(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 2, 9.0, date(2026, 8, 14))
    _mov(db, 1, -1.0, date(2026, 8, 15))
    db.commit()

    result = historial_congelado_acumulado(db)

    assert result[1] == [
        {"fecha": "2026-08-14", "cantidad": 5.0},
        {"fecha": "2026-08-15", "cantidad": 4.0},
    ]
    assert result[2] == [{"fecha": "2026-08-14", "cantidad": 9.0}]


def test_producto_ids_filters_out_others(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 2, 9.0, date(2026, 8, 14))
    db.commit()

    result = historial_congelado_acumulado(db, producto_ids=[1])

    assert list(result.keys()) == [1]


def test_fecha_hasta_excludes_later_movements(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 1, -2.0, date(2026, 8, 20))
    db.commit()

    result = historial_congelado_acumulado(db, producto_ids=[1], fecha_hasta=date(2026, 8, 15))

    assert result[1] == [{"fecha": "2026-08-14", "cantidad": 5.0}]


def test_materia_prima_movements_are_ignored(db):
    _mov(db, 1, 5.0, date(2026, 8, 14), tipo_stock="materia_prima")
    db.commit()

    result = historial_congelado_acumulado(db, producto_ids=[1])

    assert result == {}


def test_producto_sin_movimientos_no_aparece(db):
    result = historial_congelado_acumulado(db, producto_ids=[999])

    assert result == {}
