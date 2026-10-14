"""services.stock.ajustar_consumo_padre -- changing how much masa a bake
consumed WITHOUT rebuilding the rest of the record.

The reason this primitive exists is a production incident (2026-10-13,
CLAUDE.md "NUNCA reaplicar produccion historica"): correcting the same number
through revert+reapply recreated each record's output lot dated in the past,
and a lot inserted after a physical count is never swept by
reconciliar_lotes_tras_conteo, so the shelf inflated by ~480 units with no way
back. These tests pin the three things that must stay untouched -- the output
lot, the output movement and the ingredient deduction -- because that is the
whole point of the function, not an incidental property of it.
"""

from datetime import date, timedelta

from app.models import (
    Categoria,
    Ingrediente,
    InventarioRegistro,
    LineaReceta,
    MovimientoStock,
    ProductoCongelado,
    Receta,
    StockCongelado,
)
from app.services.stock import (
    ajustar_consumo_padre,
    get_saldo_congelado,
    get_saldo_materia_prima,
    producir_producto,
)

REF = "registro_produccion:1"


def _cadena_pan(db, lotes_de_masa=3.0):
    """Masa Pan Blanco (masa, stock in lotes) -> Pan 1kg (terminado, 20 per lote).

    Mirrors the real chain, including the yield that makes the derived
    consumption fractional: 24 panes / 20 = 1,2 lotes.
    """
    cat_i = Categoria(nombre="Harinas", tipo="ingrediente")
    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add_all([cat_i, cat_r])
    db.flush()

    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat_i.id, unidad_compra="kg",
        unidad_uso="kg", precio_compra=760.0, cantidad_compra=1.0,
    )
    db.add(ing)
    db.flush()
    db.add(InventarioRegistro(
        ingrediente_id=ing.id, cantidad=100.0, unidad="kg", fecha_registro=date.today(),
    ))

    r_masa = Receta(nombre="Masa Pan Blanco", categoria_id=cat_r.id,
                    porciones_por_lote=1.0, es_subreceta=True)
    r_pan = Receta(nombre="Pan 1kg Blanco", categoria_id=cat_r.id, porciones_por_lote=20.0)
    db.add_all([r_masa, r_pan])
    db.flush()
    db.add(LineaReceta(receta_id=r_masa.id, ingrediente_id=ing.id, cantidad=20.0, unidad="kg"))
    # The terminado has its own ingredient line so we can prove it is NOT
    # re-deducted when only the masa consumption is corrected.
    db.add(LineaReceta(receta_id=r_pan.id, ingrediente_id=ing.id, cantidad=1.0, unidad="kg"))

    masa = ProductoCongelado(nombre="Masa Pan Blanco", categoria="masas", unidad="u",
                             receta_id=r_masa.id, nivel="masa")
    db.add(masa)
    db.flush()
    pan = ProductoCongelado(
        nombre="Pan 1kg Blanco Cocinado", categoria="panes", unidad="u",
        receta_id=r_pan.id, nivel="terminado",
        producto_padre_id=masa.id, cantidad_por_padre=20.0,
    )
    db.add(pan)
    db.flush()
    db.add(StockCongelado(
        producto_congelado_id=masa.id, cantidad=lotes_de_masa,
        cantidad_original=lotes_de_masa, fecha_entrada=date.today() - timedelta(days=2),
        is_active=True,
    ))
    db.commit()
    return ing, masa, pan


def _hornear(db, pan, cantidad=24.0, registro_id=1):
    producir_producto(
        db, pan.id, cantidad, 1.0, None, REF,
        user_id=None, fecha_produccion=date.today(), registro_produccion_id=registro_id,
    )
    db.commit()


def _lote_salida(db, pan):
    return (
        db.query(StockCongelado)
        .filter(StockCongelado.producto_congelado_id == pan.id)
        .order_by(StockCongelado.id)
        .all()
    )


def _mov_salida(db, pan):
    return (
        db.query(MovimientoStock)
        .filter(
            MovimientoStock.referencia_producto_id == pan.id,
            MovimientoStock.tipo_movimiento == "produccion_salida",
        )
        .all()
    )


def test_el_consumo_derivado_de_un_horneado_es_fraccionado(db):
    """El punto de partida: 24 panes / 20 por lote = 1,2 lotes de masa."""
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    assert round(get_saldo_congelado(db, masa.id), 4) == 1.8  # 3 - 1,2


def test_ajustar_cambia_solo_el_consumo_de_la_masa(db):
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)

    mov = ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    assert mov is not None
    assert round(mov.cantidad, 4) == -1.0
    assert round(get_saldo_congelado(db, masa.id), 4) == 2.0  # 3 - 1


def test_no_toca_el_lote_de_salida_ni_su_movimiento(db):
    """La falla de 2026-10-13: reaplicar creaba un lote de salida nuevo,
    fechado en el pasado, que ningun conteo posterior puede barrer."""
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)

    lotes_antes = [(l.id, l.cantidad, l.cantidad_original, l.is_active, l.fecha_entrada)
                   for l in _lote_salida(db, pan)]
    movs_antes = [(m.id, m.cantidad, m.fecha) for m in _mov_salida(db, pan)]
    assert len(lotes_antes) == 1 and len(movs_antes) == 1

    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    assert [(l.id, l.cantidad, l.cantidad_original, l.is_active, l.fecha_entrada)
            for l in _lote_salida(db, pan)] == lotes_antes
    assert [(m.id, m.cantidad, m.fecha) for m in _mov_salida(db, pan)] == movs_antes
    assert round(get_saldo_congelado(db, pan.id), 4) == 24.0


def test_no_toca_el_consumo_de_ingredientes(db):
    ing, _masa, pan = _cadena_pan(db)
    _hornear(db, pan)

    saldo_antes = get_saldo_materia_prima(db, ing.id)
    filas_antes = db.query(InventarioRegistro).filter(
        InventarioRegistro.ingrediente_id == ing.id).count()

    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    assert get_saldo_materia_prima(db, ing.id) == saldo_antes
    assert db.query(InventarioRegistro).filter(
        InventarioRegistro.ingrediente_id == ing.id).count() == filas_antes


def test_el_par_revertido_netea_a_cero_y_queda_fuera_del_feed(db):
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    # tipo_stock matters: materia_prima and congelado share an id space in
    # this table, and the fixture's ingredient happens to have the masa's id.
    movs = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == "congelado",
        MovimientoStock.referencia_producto_id == masa.id).all()
    revertidos = [m for m in movs if (m.referencia_origen or "").endswith(":rev")]
    vivos = [m for m in movs if not (m.referencia_origen or "").endswith(":rev")]

    assert round(sum(m.cantidad for m in revertidos), 6) == 0.0
    assert len(vivos) == 1 and round(vivos[0].cantidad, 4) == -1.0
    # El par revertido conserva la fecha original, o un saldo "a fecha X"
    # entre los dos movimientos no cancelaria.
    assert {m.fecha for m in revertidos} == {date.today()}


def test_no_mueve_cantidad_original_de_los_lotes_de_masa(db):
    """`cantidad_original` es lo que leen las anclas del calculado y es lo que
    muestra "lo contado". Devolver stock a un lote no puede moverlo."""
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    originales = {l.id: l.cantidad_original for l in db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == masa.id).all()}

    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    for lote_id, original in originales.items():
        assert db.get(StockCongelado, lote_id).cantidad_original == original


def test_es_idempotente(db):
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    assert ajustar_consumo_padre(db, pan.id, REF, 1.0) is not None
    db.commit()
    assert ajustar_consumo_padre(db, pan.id, REF, 1.0) is None
    db.commit()
    assert round(get_saldo_congelado(db, masa.id), 4) == 2.0


def test_devuelve_none_si_el_registro_nunca_se_aplico(db):
    _ing, _masa, pan = _cadena_pan(db)
    assert ajustar_consumo_padre(db, pan.id, REF, 1.0) is None


def test_el_endpoint_de_editar_no_recrea_el_lote_de_salida(db, client):
    """PUT /registro/{id} hacia revert+reapply incondicional, asi que corregir
    el consumo de masa de un registro viejo desde la app volvia a crear su
    lote de salida en el pasado -- el bug de 2026-10-13, alcanzable desde la
    UI. Cuando lo unico que cambia es el consumo, va por la via quirurgica."""
    from app.auth import hash_pin
    from app.models import RegistroProduccion, User
    from app.services.produccion_registro import aplicar_efectos, referencia_de

    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    db.add(user)
    db.flush()
    _ing, masa, pan = _cadena_pan(db)
    reg = RegistroProduccion(
        fecha=date.today(), completada=True, cantidad_real=24.0,
        receta_id=pan.receta_id, producto_congelado_id=pan.id, titulo_extra="Pan 1kg",
        registrado_por=user.id,
    )
    db.add(reg)
    db.commit()
    assert referencia_de(reg) == f"registro_produccion:{reg.id}"
    aplicar_efectos(db, reg, user.id)
    db.commit()

    lotes_antes = [(l.id, l.cantidad, l.fecha_entrada) for l in _lote_salida(db, pan)]
    assert len(lotes_antes) == 1

    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    resp = client.put(
        f"/api/produccion/registro/{reg.id}",
        json={"cantidad_real": 24.0, "consumo_padre_declarado": 1.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text

    assert [(l.id, l.cantidad, l.fecha_entrada) for l in _lote_salida(db, pan)] == lotes_antes
    assert round(get_saldo_congelado(db, masa.id), 4) == 2.0
    db.refresh(reg)
    assert reg.consumo_padre_declarado == 1.0


def _contar(db, masa, cantidad=0.0, dias=0):
    """Un conteo fisico, igual que lo escribe la pantalla Registrar."""
    from app.services.stock import reconciliar_lotes_tras_conteo

    lote = StockCongelado(
        producto_congelado_id=masa.id, cantidad=cantidad, cantidad_original=cantidad,
        fecha_entrada=date.today() + timedelta(days=dias), is_active=True,
    )
    db.add(lote)
    db.flush()
    reconciliar_lotes_tras_conteo(db, lote)
    db.commit()
    return lote


def test_con_un_conteo_posterior_no_toca_los_lotes(db):
    """Un conteo posterior ya absorbio el efecto de esa produccion sobre la
    estanteria. Devolverle stock a un lote que el conteo barrio lo REACTIVA
    con todo lo que tenia adentro (Masa Barra Blanca dio -1,88 en vez de
    -3,00 la primera vez). Asi que detras de un conteo solo se mueve el
    ledger."""
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    _contar(db, masa, cantidad=5.0, dias=1)

    lotes_antes = {l.id: (l.cantidad, l.is_active) for l in db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == masa.id).all()}
    saldo_antes = get_saldo_congelado(db, masa.id)

    mov = ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    assert mov is not None and round(mov.cantidad, 4) == -1.0
    assert {l.id: (l.cantidad, l.is_active) for l in db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == masa.id).all()} == lotes_antes
    assert get_saldo_congelado(db, masa.id) == saldo_antes == 5.0


def test_con_un_conteo_posterior_el_ledger_si_refleja_el_nuevo_consumo(db):
    """Lo que Felipe mira: el historial. El par viejo se anula y queda un
    unico consumo vivo por el valor redondeado."""
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    _contar(db, masa, cantidad=5.0, dias=1)
    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    movs = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == "congelado",
        MovimientoStock.referencia_producto_id == masa.id).all()
    vivos = [m for m in movs if not (m.referencia_origen or "").endswith(":rev")]
    revertidos = [m for m in movs if (m.referencia_origen or "").endswith(":rev")]
    assert len(vivos) == 1 and round(vivos[0].cantidad, 4) == -1.0
    assert round(sum(m.cantidad for m in revertidos), 6) == 0.0


def test_un_lote_barrido_por_un_conteo_no_resucita(db):
    """El fallo exacto que aborto la primera corrida: el lote barrido sigue
    inactivo y su contenido no vuelve al saldo."""
    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    _contar(db, masa, cantidad=0.0, dias=1)

    barridos = [l for l in db.query(StockCongelado).filter(
        StockCongelado.producto_congelado_id == masa.id).all()
        if not l.is_active and l.cantidad > 1e-9]
    assert barridos, "el fixture debe dejar un lote barrido con stock adentro"

    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    for l in barridos:
        assert db.get(StockCongelado, l.id).is_active is False
    assert get_saldo_congelado(db, masa.id) == 0.0


def test_revertir_despues_de_un_ajuste_solo_ledger_no_inventa_un_lote(db):
    """La trampa: en modo solo-ledger no hay `ConsumoFifoDetalle`, y la rama
    de fallback de `_restaurar_lotes` fabrica un lote nuevo, activo y
    backdateado por el monto completo. Ese lote nace con id alto y fecha
    vieja, asi que ningun conteo lo barre nunca -- exactamente el inflado
    irreversible que esta funcion existe para evitar, reintroducido por la
    puerta de atras la proxima vez que alguien edite o borre el registro."""
    from app.services.stock import revertir_consumos

    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    _contar(db, masa, cantidad=0.0, dias=1)
    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()
    assert get_saldo_congelado(db, masa.id) == 0.0

    revertir_consumos(db, REF, None, fecha=date.today())
    db.commit()

    assert get_saldo_congelado(db, masa.id) == 0.0, (
        "revertir un ajuste solo-ledger no puede crear stock fisico de la nada"
    )


def test_las_filas_sin_el_tag_nuevo_tambien_quedan_protegidas(db):
    """Las 56 filas escritas en produccion el 14/10 llevan la nota vieja, sin
    el prefijo `sin-lotes:`. Se reconocen por su texto en vez de reescribirlas,
    asi que esto pinea ese texto exacto."""
    from app.services.stock import movimiento_sin_lotes, revertir_consumos

    _ing, masa, pan = _cadena_pan(db)
    _hornear(db, pan)
    _contar(db, masa, cantidad=0.0, dias=1)
    ajustar_consumo_padre(db, pan.id, REF, 1.0)
    db.commit()

    vivo = [m for m in db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == "congelado",
        MovimientoStock.referencia_producto_id == masa.id,
        MovimientoStock.referencia_origen == REF).all()][0]
    # Reescribir la nota al formato anterior al tag.
    vivo.notas = "Consumo corregido de Masa Pan Blanco (conteo posterior: los lotes no se tocan)"
    db.commit()
    assert movimiento_sin_lotes(vivo)

    revertir_consumos(db, REF, None, fecha=date.today())
    db.commit()
    assert get_saldo_congelado(db, masa.id) == 0.0


def test_funciona_aunque_el_consumo_deje_la_masa_negativa(db):
    """Subir el consumo por encima de lo disponible no se clampea: se asienta
    en un lote de ajuste negativo, igual que cualquier otra deduccion."""
    _ing, masa, pan = _cadena_pan(db, lotes_de_masa=1.0)
    _hornear(db, pan)
    ajustar_consumo_padre(db, pan.id, REF, 2.0)
    db.commit()
    assert round(get_saldo_congelado(db, masa.id), 4) == -1.0
