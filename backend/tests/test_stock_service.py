"""historial_movimientos_acumulado(): the shared cumulative-balance-from-ledger
helper behind the congelados detail page, the escandallos /completo endpoint,
and the Stock Congelado / Stock Materia Prima pivot tables' calculated column.
"""
from datetime import date

from app.models import Categoria, Ingrediente, InventarioRegistro, MovimientoStock, ProductoCongelado, StockCongelado
from app.services.stock import deducir_congelado_fifo, historial_movimientos_acumulado


def _mov(db, producto_id, cantidad, fecha, tipo_stock="congelado"):
    db.add(MovimientoStock(
        tipo_stock=tipo_stock, referencia_producto_id=producto_id, cantidad=cantidad,
        unidad="u", tipo_movimiento="produccion_salida", fecha=fecha,
    ))


def _ingrediente(db) -> int:
    cat = Categoria(nombre="Cat-reanclaje", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Ingrediente reanclaje", categoria_id=cat.id, unidad_compra="kg",
        cantidad_compra=1, precio_compra=100, unidad_uso="kg",
    )
    db.add(ing)
    db.flush()
    return ing.id


def _producto_congelado(db) -> int:
    prod = ProductoCongelado(nombre="Producto reanclaje", categoria="bolleria", unidad="u")
    db.add(prod)
    db.flush()
    return prod.id


def test_running_balance_single_producto(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 1, -2.0, date(2026, 8, 15))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[1])

    assert result[1] == [
        {"fecha": "2026-08-14", "cantidad": 5.0},
        {"fecha": "2026-08-15", "cantidad": 3.0},
    ]


def test_same_day_movements_are_netted_before_accumulating(db):
    _mov(db, 1, 13.5, date(2026, 8, 14))
    _mov(db, 1, -1.5, date(2026, 8, 14))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[1])

    assert result[1] == [{"fecha": "2026-08-14", "cantidad": 12.0}]


def test_batched_across_products_no_cross_contamination(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 2, 9.0, date(2026, 8, 14))
    _mov(db, 1, -1.0, date(2026, 8, 15))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado")

    assert result[1] == [
        {"fecha": "2026-08-14", "cantidad": 5.0},
        {"fecha": "2026-08-15", "cantidad": 4.0},
    ]
    assert result[2] == [{"fecha": "2026-08-14", "cantidad": 9.0}]


def test_ids_filters_out_others(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 2, 9.0, date(2026, 8, 14))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[1])

    assert list(result.keys()) == [1]


def test_fecha_hasta_excludes_later_movements(db):
    _mov(db, 1, 5.0, date(2026, 8, 14))
    _mov(db, 1, -2.0, date(2026, 8, 20))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[1], fecha_hasta=date(2026, 8, 15))

    assert result[1] == [{"fecha": "2026-08-14", "cantidad": 5.0}]


def test_tipo_stock_isolates_congelado_from_materia_prima(db):
    _mov(db, 1, 5.0, date(2026, 8, 14), tipo_stock="materia_prima")
    _mov(db, 1, 2.0, date(2026, 8, 14), tipo_stock="congelado")
    db.commit()

    congelado = historial_movimientos_acumulado(db, "congelado", ids=[1])
    materia_prima = historial_movimientos_acumulado(db, "materia_prima", ids=[1])

    assert congelado[1] == [{"fecha": "2026-08-14", "cantidad": 2.0}]
    assert materia_prima[1] == [{"fecha": "2026-08-14", "cantidad": 5.0}]


def test_id_sin_movimientos_no_aparece(db):
    result = historial_movimientos_acumulado(db, "congelado", ids=[999])

    assert result == {}


# ── Re-anclaje al conteo fisico (2026-08-21) ────────────────────────────────

def test_materia_prima_se_reancla_al_conteo_del_dia_siguiente(db):
    """El dia del conteo (20/08) sigue mostrando el acumulado VIEJO -- se ve
    el desvio contra el conteo real. Recien el 21/08 arranca del conteo
    fisico del 20/08 en vez de seguir acumulando desde el 1 de agosto."""
    ing_id = _ingrediente(db)
    _mov(db, ing_id, 100.0, date(2026, 8, 1), tipo_stock="materia_prima")
    _mov(db, ing_id, -0.5, date(2026, 8, 20), tipo_stock="materia_prima")
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=3.0, unidad="kg", fecha_registro=date(2026, 8, 20),
    ))
    _mov(db, ing_id, -1.0, date(2026, 8, 21), tipo_stock="materia_prima")
    db.commit()

    result = historial_movimientos_acumulado(db, "materia_prima", ids=[ing_id])

    assert result[ing_id] == [
        {"fecha": "2026-08-01", "cantidad": 100.0},
        {"fecha": "2026-08-20", "cantidad": 99.5},   # old trajectory, desvio visible vs conteo=3.0
        {"fecha": "2026-08-21", "cantidad": 2.0},    # 3.0 (conteo del 20/08) - 1.0
    ]


def test_congelado_se_reancla_al_conteo_del_dia_siguiente(db):
    prod_id = _producto_congelado(db)
    _mov(db, prod_id, 50.0, date(2026, 8, 1))
    _mov(db, prod_id, -2.0, date(2026, 8, 20))
    db.add(StockCongelado(producto_congelado_id=prod_id, cantidad=30.0, fecha_entrada=date(2026, 8, 20)))
    _mov(db, prod_id, 5.0, date(2026, 8, 21))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[prod_id])

    assert result[prod_id] == [
        {"fecha": "2026-08-01", "cantidad": 50.0},
        {"fecha": "2026-08-20", "cantidad": 48.0},   # old trajectory
        {"fecha": "2026-08-21", "cantidad": 35.0},   # 30.0 (conteo del 20/08) + 5.0
    ]


def test_conteo_automatico_no_reancla(db):
    """Una fila auto-generada (Consumo automatico:, Reversion de, Pedido #)
    no es un conteo fisico -- no debe usarse como ancla."""
    ing_id = _ingrediente(db)
    _mov(db, ing_id, 100.0, date(2026, 8, 1), tipo_stock="materia_prima")
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=3.0, unidad="kg", fecha_registro=date(2026, 8, 20),
        notas="Consumo automatico: registro_produccion:1",
    ))
    _mov(db, ing_id, -1.0, date(2026, 8, 21), tipo_stock="materia_prima")
    db.commit()

    result = historial_movimientos_acumulado(db, "materia_prima", ids=[ing_id])

    assert result[ing_id] == [
        {"fecha": "2026-08-01", "cantidad": 100.0},
        {"fecha": "2026-08-21", "cantidad": 99.0},  # kept accumulating, ignored the auto row
    ]


def test_congelado_suma_lotes_del_mismo_dia_como_una_sola_ancla(db):
    """Dos lotes contados el mismo dia se suman para formar el ancla, igual
    que la agregacion que ya hace la tabla pivot del frontend."""
    prod_id = _producto_congelado(db)
    _mov(db, prod_id, 50.0, date(2026, 8, 1))
    db.add(StockCongelado(producto_congelado_id=prod_id, cantidad=10.0, fecha_entrada=date(2026, 8, 20)))
    db.add(StockCongelado(producto_congelado_id=prod_id, cantidad=20.0, fecha_entrada=date(2026, 8, 20)))
    _mov(db, prod_id, 1.0, date(2026, 8, 21))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[prod_id])

    assert result[prod_id] == [
        {"fecha": "2026-08-01", "cantidad": 50.0},
        {"fecha": "2026-08-21", "cantidad": 31.0},  # (10+20) + 1.0
    ]


def test_materia_prima_conteo_sin_movimiento_posterior_igual_se_refleja(db):
    """Si nada se produjo/vendio/desperdicio desde el conteo, el calculado de
    HOY (fecha_hasta) debe ser el conteo mismo -- antes de este fix, el reset
    solo se aplicaba al iterar un movimiento POSTERIOR al conteo, y si no
    habia ninguno el calculado se quedaba pegado en la trayectoria vieja para
    siempre, ignorando el conteo por completo."""
    ing_id = _ingrediente(db)
    _mov(db, ing_id, 100.0, date(2026, 8, 1), tipo_stock="materia_prima")
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=3.0, unidad="kg", fecha_registro=date(2026, 8, 20),
    ))
    db.commit()

    result = historial_movimientos_acumulado(
        db, "materia_prima", ids=[ing_id], fecha_hasta=date(2026, 8, 21),
    )

    assert result[ing_id] == [
        {"fecha": "2026-08-01", "cantidad": 100.0},  # old trajectory, up to the count's own day
        {"fecha": "2026-08-21", "cantidad": 3.0},    # nothing moved since -- today = the count
    ]


def test_congelado_conteo_sin_movimiento_posterior_igual_se_refleja(db):
    prod_id = _producto_congelado(db)
    _mov(db, prod_id, 50.0, date(2026, 8, 1))
    db.add(StockCongelado(producto_congelado_id=prod_id, cantidad=30.0, fecha_entrada=date(2026, 8, 20)))
    db.commit()

    result = historial_movimientos_acumulado(
        db, "congelado", ids=[prod_id], fecha_hasta=date(2026, 8, 21),
    )

    assert result[prod_id] == [
        {"fecha": "2026-08-01", "cantidad": 50.0},
        {"fecha": "2026-08-21", "cantidad": 30.0},
    ]


def test_conteo_en_el_dia_de_referencia_todavia_no_reancla(db):
    """Simetria con el conteo del dia mismo: si HOY (fecha_hasta) coincide con
    la fecha del conteo, todavia se ve la trayectoria vieja ese mismo dia --
    el reset arranca al dia SIGUIENTE, no antes."""
    ing_id = _ingrediente(db)
    _mov(db, ing_id, 100.0, date(2026, 8, 1), tipo_stock="materia_prima")
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=3.0, unidad="kg", fecha_registro=date(2026, 8, 21),
    ))
    db.commit()

    result = historial_movimientos_acumulado(
        db, "materia_prima", ids=[ing_id], fecha_hasta=date(2026, 8, 21),
    )

    assert result[ing_id] == [{"fecha": "2026-08-01", "cantidad": 100.0}]


def test_dos_conteos_seguidos_sin_movimiento_entre_ellos_reanclan_cada_uno(db):
    """Dos conteos consecutivos, sin ningun movimiento real entre medio ni
    despues -- cada uno debe reflejarse al dia siguiente de si mismo, no solo
    el ultimo."""
    ing_id = _ingrediente(db)
    _mov(db, ing_id, 100.0, date(2026, 8, 1), tipo_stock="materia_prima")
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=10.0, unidad="kg", fecha_registro=date(2026, 8, 15),
    ))
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=4.0, unidad="kg", fecha_registro=date(2026, 8, 18),
    ))
    db.commit()

    result = historial_movimientos_acumulado(
        db, "materia_prima", ids=[ing_id], fecha_hasta=date(2026, 8, 21),
    )

    assert result[ing_id] == [
        {"fecha": "2026-08-01", "cantidad": 100.0},
        {"fecha": "2026-08-16", "cantidad": 10.0},  # dia siguiente al conteo del 15
        {"fecha": "2026-08-19", "cantidad": 4.0},   # dia siguiente al conteo del 18
    ]


def test_congelado_ancla_usa_cantidad_original_no_la_mutada_por_fifo(db):
    """cantidad se muta in-place por cada consumo FIFO (deducir_congelado_fifo
    resta directo del lote) -- si el ancla leyera ese valor actual en vez de
    cantidad_original (fijo al crear el lote y nunca mas tocado), un conteo
    viejo se veria cada vez mas chico a medida que se sigue vendiendo, aunque
    lo contado ese dia haya sido siempre el mismo numero."""
    prod_id = _producto_congelado(db)
    db.add(StockCongelado(
        producto_congelado_id=prod_id, cantidad=50.0, cantidad_original=50.0,
        fecha_entrada=date(2026, 8, 1),
    ))
    db.commit()

    deducir_congelado_fifo(db, prod_id, 20.0, "entrega_b2b:1:Cliente", fecha=date(2026, 8, 5))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[prod_id])

    assert result[prod_id] == [{"fecha": "2026-08-05", "cantidad": 30.0}]


def test_congelado_ancla_no_duplica_con_multiples_consumos_posteriores(db):
    """A diferencia del intento revertido (que reconstruia sumando TODO lo
    consumido del lote y por eso duplicaba cada consumo posterior contra el
    propio ledger), anclar a cantidad_original -- fijo -- deja que cada
    consumo posterior se aplique una sola vez via el ledger normal."""
    prod_id = _producto_congelado(db)
    db.add(StockCongelado(
        producto_congelado_id=prod_id, cantidad=141.0, cantidad_original=141.0,
        fecha_entrada=date(2026, 8, 13),
    ))
    db.commit()

    deducir_congelado_fifo(db, prod_id, 2.0, "entrega_b2b:1:Cliente", fecha=date(2026, 8, 15))
    db.commit()
    deducir_congelado_fifo(db, prod_id, 5.0, "merma:1", fecha=date(2026, 8, 18))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[prod_id])

    assert result[prod_id] == [
        {"fecha": "2026-08-15", "cantidad": 139.0},
        {"fecha": "2026-08-18", "cantidad": 134.0},
    ]


def test_congelado_lote_sin_cantidad_original_usa_cantidad_como_fallback(db):
    """Filas viejas de antes de que existiera la columna (o de tests que no
    la setean) siguen funcionando -- cae de nuevo a `cantidad`."""
    prod_id = _producto_congelado(db)
    db.add(StockCongelado(producto_congelado_id=prod_id, cantidad=30.0, fecha_entrada=date(2026, 8, 20)))
    _mov(db, prod_id, 50.0, date(2026, 8, 1))
    _mov(db, prod_id, 5.0, date(2026, 8, 21))
    db.commit()

    result = historial_movimientos_acumulado(db, "congelado", ids=[prod_id])

    assert result[prod_id] == [
        {"fecha": "2026-08-01", "cantidad": 50.0},
        {"fecha": "2026-08-21", "cantidad": 35.0},
    ]


def test_item_nunca_recontado_sigue_acumulando_normal(db):
    """Sin ningun conteo manual, el comportamiento es exactamente el de
    siempre -- acumulado puro desde el primer movimiento."""
    ing_id = _ingrediente(db)
    _mov(db, ing_id, 100.0, date(2026, 8, 1), tipo_stock="materia_prima")
    _mov(db, ing_id, -5.0, date(2026, 8, 21), tipo_stock="materia_prima")
    db.commit()

    result = historial_movimientos_acumulado(db, "materia_prima", ids=[ing_id])

    assert result[ing_id] == [
        {"fecha": "2026-08-01", "cantidad": 100.0},
        {"fecha": "2026-08-21", "cantidad": 95.0},
    ]
