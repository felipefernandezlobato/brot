"""El consumo semanal sale del LEDGER, no de la cadena de snapshots.

`/inventario/recomendacion` lo estimaba recorriendo filas consecutivas de
`InventarioRegistro`. Esas filas son totales absolutos guardados que NO se
re-secuencian: una produccion cargada tarde pero fechada en el pasado se
engancha al total que fuera la punta de la cadena al escribirla, asi que como
serie temporal la columna esta mal (ver "Two parallel ways to read materia
prima stock" en CLAUDE.md). Medido en produccion el 29/10/2026: decia 547,9
kg/semana de Harina 000 contra 96,4 reales, y 67,9 de Manteca contra 19,0 --
sugiriendo pedir 128 kg de manteca para un gasto de 19.

Encima tenia un segundo fallo independiente del anterior: el denominador solo
acumulaba los dias en que el stock bajo (`if consumo > 0`), asi que una semana
tranquila no entraba en la division y la tasa subia sola.
"""

from datetime import date, timedelta

from app.models import Categoria, Ingrediente, MovimientoStock
from app.services.stock import consumo_semanal_materia_prima


def _ingrediente(db, nombre="Harina 000"):
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre=nombre, categoria_id=cat.id, unidad_compra="kg", unidad_uso="kg",
        cantidad_compra=1.0, precio_compra=800.0, activo=True,
    )
    db.add(ing)
    db.flush()
    return ing


def _mov(db, ing_id, cantidad, fecha, tipo="produccion_consumo"):
    db.add(MovimientoStock(
        tipo_stock="materia_prima", referencia_producto_id=ing_id,
        cantidad=cantidad, unidad="kg", tipo_movimiento=tipo, fecha=fecha,
    ))
    db.flush()


def test_promedia_sobre_las_semanas_vividas_no_sobre_las_que_bajo(db):
    """El fallo del denominador: 8 semanas de datos, consumo solo en 2."""
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -100.0, hoy - timedelta(weeks=8))  # primer movimiento
    _mov(db, ing.id, -100.0, hoy - timedelta(weeks=1))

    # 200 kg repartidos entre las 8 semanas que lleva existiendo = 25/semana.
    # La version vieja dividia solo por los dias con bajada y daba mucho mas.
    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 25.0


def test_las_recepciones_no_cuentan_como_consumo(db):
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -80.0, hoy - timedelta(weeks=4))
    _mov(db, ing.id, 1000.0, hoy - timedelta(weeks=2), tipo="recepcion")
    _mov(db, ing.id, -80.0, hoy - timedelta(weeks=1))

    # 160 kg / 4 semanas de vida = 40. Los 1000 recibidos no son consumo.
    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 40.0


def test_la_merma_si_cuenta(db):
    """Decision de Felipe (29/10/2026): lo que se tira hay que reponerlo."""
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -40.0, hoy - timedelta(weeks=2))
    _mov(db, ing.id, -40.0, hoy - timedelta(weeks=2), tipo="merma")

    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 40.0


def test_un_par_revertido_no_cuenta_dos_veces(db):
    """Por esto se NETEA en vez de sumar solo los negativos.

    `revertir_consumos` deja el movimiento original y su devolucion con el
    MISMO `tipo_movimiento` (lo dice su propio comentario), asi que sumar solo
    las cantidades negativas contaria el original como consumo real aunque ya
    estuviera anulado.
    """
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -40.0, hoy - timedelta(weeks=2))
    _mov(db, ing.id, -70.0, hoy - timedelta(weeks=1))
    _mov(db, ing.id, 70.0, hoy - timedelta(weeks=1))  # la reversion

    # Solo los 40 son consumo de verdad: 40 / 2 semanas = 20.
    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 20.0


def test_un_ingrediente_nuevo_se_divide_por_lo_que_lleva_existiendo(db):
    """Los de Limpieza y Descartables llevan semanas, no meses.

    Dividir por 8 fijas le daria la mitad de su consumo real justo cuando mas
    falta hace acertar con el primer pedido.
    """
    ing = _ingrediente(db, "Cloro")
    hoy = date.today()
    _mov(db, ing.id, -10.0, hoy - timedelta(weeks=2))

    # 10 / 2 semanas de vida = 5, no 10/8 = 1,25.
    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 5.0


def test_la_ventana_se_topa_en_8_semanas(db):
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -1000.0, hoy - timedelta(weeks=30))  # fuera de ventana
    _mov(db, ing.id, -80.0, hoy - timedelta(weeks=3))

    # Solo los 80, y sobre 8 semanas (tope), no sobre las 30 de vida.
    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 10.0


def test_sin_movimientos_da_cero_y_no_revienta(db):
    ing = _ingrediente(db)
    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 0.0


def test_nunca_devuelve_negativo(db):
    """Una reversion que cae dentro de la ventana mientras su original quedo
    fuera deja el neto en positivo. Eso no es stock creado."""
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -50.0, hoy - timedelta(weeks=20))
    _mov(db, ing.id, 50.0, hoy - timedelta(weeks=1))

    assert consumo_semanal_materia_prima(db, [ing.id])[ing.id] == 0.0


# ---------------------------------------------------------------------------
# GET /api/ingredientes/{id}/evolucion -- la serie que dibuja el grafico de la
# ficha del ingrediente. Se construia en el navegador restando filas de
# /api/inventario, y llego a pintar Manteca a -25,3 kg el 19/10 donde el ledger
# dice 5,10, contradiciendo a la tabla de movimientos de la misma pantalla.
# ---------------------------------------------------------------------------

from app.models import InventarioRegistro  # noqa: E402
from app.routers.ingredientes import get_evolucion_ingrediente  # noqa: E402


def _conteo(db, ing_id, cantidad, fecha, notas=""):
    db.add(InventarioRegistro(
        ingrediente_id=ing_id, cantidad=cantidad, unidad="kg",
        fecha_registro=fecha, notas=notas,
    ))
    db.flush()


def test_evolucion_sigue_al_ledger_no_a_las_filas_guardadas(db):
    """El caso exacto que se vio en produccion: una recepcion cargada tarde.

    La fila de `InventarioRegistro` de la produccion se engancho al total de
    DESPUES de la recepcion, asi que la serie guardada daba un saldo negativo
    donde el ledger da uno positivo.
    """
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, 25.0, hoy - timedelta(days=12), tipo="recepcion")
    _mov(db, ing.id, -20.0, hoy - timedelta(days=10))

    puntos = {p["fecha"]: p for p in get_evolucion_ingrediente(ing.id, None, db)["puntos"]}
    assert puntos[str(hoy - timedelta(days=10))]["cantidad"] == 5.0


def test_evolucion_expone_el_conteo_fisico_aparte_del_calculado(db):
    """Los dos numeros tienen que poder verse a la vez.

    En la fecha del propio conteo, `historial_movimientos_acumulado` mantiene a
    proposito la trayectoria PRE-conteo: esa diferencia es la discrepancia que
    el historial existe para ensenar. Si el grafico solo pintara una de las dos
    series, quedaria peleado con la tarjeta "Stock actual" de arriba sin que se
    pueda saber por que.
    """
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, 10.0, hoy - timedelta(days=5), tipo="recepcion")
    _conteo(db, ing.id, 8.0, hoy - timedelta(days=5))

    punto = {p["fecha"]: p for p in get_evolucion_ingrediente(ing.id, None, db)["puntos"]}
    punto = punto[str(hoy - timedelta(days=5))]
    assert punto["cantidad"] == 10.0   # el ledger
    assert punto["contado"] == 8.0     # lo que se conto


def test_un_conteo_sin_movimientos_ese_dia_igual_sale_con_su_consumo(db):
    """Un conteo puede caer en una fecha sin movimientos. Ese dia tiene que
    aparecer en el eje Y llevar su ventana de consumo de verdad: calcularlo
    aparte lo dejaba en 0 aunque hubiera habido gasto en esos 7 dias."""
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -14.0, hoy - timedelta(days=3))
    _conteo(db, ing.id, 2.0, hoy)

    puntos = {p["fecha"]: p for p in get_evolucion_ingrediente(ing.id, None, db)["puntos"]}
    assert str(hoy) in puntos
    assert puntos[str(hoy)]["cantidad"] is None   # no hubo movimiento ese dia
    assert puntos[str(hoy)]["contado"] == 2.0
    assert puntos[str(hoy)]["consumo_7d"] == 14.0


def test_una_fila_automatica_no_es_un_conteo(db):
    """Solo cuentan los conteos de persona. Comparar el calculado contra una
    fila que el propio sistema escribio al consumir seria compararlo consigo
    mismo."""
    ing = _ingrediente(db)
    hoy = date.today()
    _mov(db, ing.id, -5.0, hoy - timedelta(days=2))
    _conteo(db, ing.id, 99.0, hoy - timedelta(days=2), notas="Consumo automatico: registro_produccion:1")

    puntos = {p["fecha"]: p for p in get_evolucion_ingrediente(ing.id, None, db)["puntos"]}
    assert puntos[str(hoy - timedelta(days=2))]["contado"] is None
