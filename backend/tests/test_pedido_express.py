"""La regla de pedido express, sin HTTP ni base de datos.

Fechas fijas y `hoy` inyectado a proposito: el camino express solo existe
cuando la entrega cae a 1 dia, asi que un test que dependiera de `date.today()`
solo recorreria esa rama los martes y los viernes.
"""

import dataclasses
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.pedido_express import (
    DIAS_ANTICIPACION_NORMAL,
    RECARGO_EXPRESS_PCT,
    Anticipacion,
    calcular_recargo,
    evaluar,
    hoy_arg,
)

# 2026-01-07 es miercoles de verdad (dia de entrega valido).
MIERCOLES = date(2026, 1, 7)
MARTES = date(2026, 1, 6)
LUNES = date(2026, 1, 5)
DOMINGO = date(2026, 1, 4)


def test_dos_dias_de_antelacion_no_paga_recargo():
    a = evaluar(MIERCOLES, hoy=LUNES)
    assert a.dias == 2
    assert a.se_puede_pedir
    assert not a.es_express
    assert a.recargo_pct == 0.0


def test_tres_dias_tampoco():
    a = evaluar(MIERCOLES, hoy=DOMINGO)
    assert a.se_puede_pedir
    assert not a.es_express


def test_un_dia_de_antelacion_es_express():
    a = evaluar(MIERCOLES, hoy=MARTES)
    assert a.dias == 1
    assert a.se_puede_pedir
    assert a.es_express
    assert a.recargo_pct == RECARGO_EXPRESS_PCT


def test_el_mismo_dia_no_se_puede_pedir():
    a = evaluar(MIERCOLES, hoy=MIERCOLES)
    assert a.dias == 0
    assert not a.se_puede_pedir
    assert not a.es_express


def test_una_fecha_pasada_no_se_puede_pedir():
    a = evaluar(MIERCOLES, hoy=date(2026, 1, 9))
    assert a.dias == -2
    assert not a.se_puede_pedir


def test_el_recargo_es_el_cinco_por_ciento():
    express = evaluar(MIERCOLES, hoy=MARTES)
    assert calcular_recargo(1000.0, express) == 50.0


def test_el_recargo_redondea_a_dos_decimales():
    express = evaluar(MIERCOLES, hoy=MARTES)
    # 333.33 * 5% = 16.6665
    assert calcular_recargo(333.33, express) == 16.67


def test_una_fecha_normal_no_paga_nada():
    normal = evaluar(MIERCOLES, hoy=LUNES)
    assert calcular_recargo(99999.0, normal) == 0.0


def test_el_borde_utc_no_adelanta_el_dia():
    """El test que justifica que exista `hoy_arg()`.

    Las 22:30 de un martes en Argentina son las 01:30 UTC del miercoles. Con
    `date.today()` en el servidor (que en Render es UTC) el backend creeria que
    hoy ya es miercoles y rechazaria, por "mismo dia", un pedido express para
    ese miercoles que el cliente todavia tiene derecho a hacer hasta las 23:59
    hora local.

    Si alguien borra la conversion de huso "para simplificar", este test se
    rompe. No lo arregles cambiando la expectativa.
    """
    martes_2230_arg = datetime(2026, 1, 7, 1, 30, tzinfo=timezone.utc)

    # La lectura ingenua -- la que NO hay que hacer.
    assert martes_2230_arg.date() == MIERCOLES

    # La correcta: en Argentina todavia es martes.
    assert hoy_arg(martes_2230_arg) == MARTES

    a = evaluar(MIERCOLES, hoy=hoy_arg(martes_2230_arg))
    assert a.se_puede_pedir
    assert a.es_express


def test_justo_despues_de_medianoche_argentina_ya_es_tarde():
    """La otra cara: pasada la medianoche local, el miercoles ya es "hoy"."""
    miercoles_0030_arg = datetime(2026, 1, 7, 3, 30, tzinfo=timezone.utc)
    assert hoy_arg(miercoles_0030_arg) == MIERCOLES
    assert not evaluar(MIERCOLES, hoy=hoy_arg(miercoles_0030_arg)).se_puede_pedir


def test_hoy_arg_acepta_un_datetime_sin_huso():
    """Por si alguien le pasa un naive: se asume UTC, que es lo que da el server."""
    assert hoy_arg(datetime(2026, 1, 7, 1, 30)) == MARTES


def test_el_umbral_normal_es_el_que_dice_la_constante():
    """Ancla la constante contra la rama, para que cambiar una sin la otra falle."""
    justo = evaluar(MIERCOLES, hoy=MIERCOLES - timedelta(days=DIAS_ANTICIPACION_NORMAL))
    assert not justo.es_express
    uno_menos = evaluar(MIERCOLES, hoy=MIERCOLES - timedelta(days=DIAS_ANTICIPACION_NORMAL - 1))
    assert uno_menos.es_express


def test_anticipacion_es_inmutable():
    """frozen=True: nadie le cambia el recargo a una evaluacion ya hecha."""
    a = evaluar(MIERCOLES, hoy=MARTES)
    assert isinstance(a, Anticipacion)
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.recargo_pct = 99.0  # type: ignore[misc]
