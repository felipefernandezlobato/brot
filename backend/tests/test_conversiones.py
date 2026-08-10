import pytest
from app.services.conversiones import convertir


def test_kg_to_g():
    assert convertir(1, "kg", "g") == 1000


def test_g_to_kg():
    assert convertir(500, "g", "kg") == 0.5


def test_litro_to_ml():
    assert convertir(1, "litro", "ml") == 1000


def test_same_unit():
    assert convertir(5, "kg", "kg") == 5


def test_cross_family_raises():
    with pytest.raises(ValueError):
        convertir(1, "kg", "litro")


def test_unidad_to_unidad():
    assert convertir(3, "unidad", "unidad") == 3
