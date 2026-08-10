import pytest
from app.models import Categoria, Ingrediente, LineaReceta, Receta
from app.services.costes import costo_por_unidad_uso, costo_receta


def test_costo_por_unidad_uso_simple(db):
    cat = Categoria(nombre="Test", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=1,
        precio_compra=500, unidad_uso="g", merma_porcentaje=0,
    )
    db.add(ing)
    db.flush()
    cost = costo_por_unidad_uso(ing)
    assert cost == pytest.approx(0.5)  # 500 ARS / 1000g


def test_costo_por_unidad_uso_with_merma(db):
    cat = Categoria(nombre="Test2", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Manteca", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=1,
        precio_compra=1000, unidad_uso="g", merma_porcentaje=10,
    )
    db.add(ing)
    db.flush()
    cost = costo_por_unidad_uso(ing)
    assert cost == pytest.approx(1000 / 1000 / 0.9)


def test_costo_receta(db):
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add(cat_r)
    db.flush()

    harina = Ingrediente(
        nombre="Harina", categoria_id=cat.id,
        unidad_compra="kg", cantidad_compra=1,
        precio_compra=500, unidad_uso="g", merma_porcentaje=0,
    )
    db.add(harina)
    db.flush()

    receta = Receta(nombre="Pan", categoria_id=cat_r.id, porciones_por_lote=10)
    db.add(receta)
    db.flush()

    linea = LineaReceta(receta_id=receta.id, ingrediente_id=harina.id, cantidad=1000, unidad="g")
    db.add(linea)
    db.commit()

    total, por_porcion = costo_receta(receta, db)
    assert total == pytest.approx(500.0)  # 1000g × 0.5 ARS/g
    assert por_porcion == pytest.approx(50.0)  # 500 / 10 porciones
