# -*- coding: utf-8 -*-
"""Load historical stock data from spreadsheets.

Run from backend/:
    python load_historical.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from datetime import date

from app.database import SessionLocal
from app.models import (
    Categoria,
    Ingrediente,
    InventarioRegistro,
    ProductoCongelado,
    StockCongelado,
)


# ── Ingredientes (seeded if missing) ────────────────────────────────────────

# (nombre, categoria_nombre, unidad_compra, cantidad_compra, precio_compra, unidad_uso, proveedor)
INGREDIENTES_DATA = [
    ("Harina 000", "Harinas", "kg", 25, 16000, "kg", "Forzani"),
    ("Harina 0000", "Harinas", "kg", 25, 19000, "kg", "Forzani"),
    ("Harina 00 Pizza", "Harinas", "kg", 25, 20000, "kg", "Forzani"),
    ("Harina Integral", "Harinas", "kg", 5, 9000, "kg", "Forzani"),
    ("Harina Salvado", "Harinas", "kg", 20, 14000, "kg", "Forzani"),
    ("Harina Pastelera", "Harinas", "kg", 1, 2256, "kg", None),
    (u"Semolín", "Harinas", "kg", 1, 756, "kg", "Forzani"),
    ("Levadura", "Levaduras y Mejorantes", "kg", 0.5, 4000, "kg", "Dunate"),
    (u"Azúcar", u"Azúcares", "kg", 50, 45000, "kg", "Forzani"),
    ("Miel", u"Azúcares", "kg", 1, 7500, "kg", None),
    ("Chocolate", u"Azúcares", "kg", 1, 30000, "kg", "Casadoro"),
    ("Leche", u"Lácteos", "L", 1, 1639, "L", None),
    ("Huevos", u"Lácteos", "kg", 1, 3933, "kg", "Finca"),
    ("Manteca", "Grasas", "kg", 1, 13412, "kg", "Luis Martin"),
    ("Aceite Girasol", "Grasas", "L", 1, 3811, "L", None),
    ("Aceite Oliva", "Grasas", "L", 1, 16000, "L", None),
    ("Grasa de Cerdo", "Grasas", "kg", 1, 3500, "kg", "Tia Nona"),
    ("Sal", "Otros", "kg", 1, 340, "kg", "Dunate"),
    ("Vinagre Blanco", "Otros", "L", 1, 1518, "L", None),
    ("Canela", "Otros", "kg", 1, 16900, "kg", None),
    ("Agua", "Otros", "L", 1, 0, "L", None),
    ("Masa Madre", "Otros", "kg", 1, 400, "kg", None),
    ("Tomate", "Otros", "kg", 1, 0, "kg", "Aldunate"),
]

# ── Stock Congelado ──────────────────────────────────────────────────────────

CONGELADO_DATES = [
    date(2026, 5, 7),
    date(2026, 5, 14),
    date(2026, 5, 21),
    date(2026, 5, 28),
    date(2026, 6, 5),
    date(2026, 6, 11),
    date(2026, 6, 18),
    date(2026, 6, 25),
    date(2026, 7, 9),
    date(2026, 7, 15),
    date(2026, 7, 23),
    date(2026, 8, 6),
]

CONGELADO_PRODUCTS = [
    # (nombre, categoria, [qty per date or None to skip])
    # --- Productos terminados ---
    ("Medialunas", "Producto terminado", [240, 250, 312, 408, 164, 325, 275, 273, 348, 360, 0, 52]),
    ("Croissant", "Producto terminado", [147, 178, 148, 190, 263, 275, 264, 208, 190, 190, 155, 42]),
    ("Caracolas", "Producto terminado", [29, 80, 130, 83, 35, 49, 0, 89, 15, 39, 70, 8]),
    ("Pan Suisse", "Producto terminado", [35, 38, 36, 41, 43, 48, 47, 51, 56, 26, 16, 16]),
    ("Ensaimadas", "Producto terminado", [30, 33, 77, 77, 77, 22, 95, 32, 95, 15, 22, 10]),
    ("Cruffin", "Producto terminado", [24, 24, 39, 58, 53, 50, 49, 39, 45, 32, 17, 6]),
    ("Moño", "Producto terminado", [16, 44, 51, 53, 58, 40, 30, 20, 17, 39, 39, 5]),
    ("Pan de Choco", "Producto terminado", [53, 38, 51, 59, 65, 80, 100, 78, 78, 50, 46, 16]),
    ("Palmerita", "Producto terminado", [0, 48, 52, 71, 37, 45, 37, 65, 31, 0, 16, 4]),
    ("Sacramento", "Producto terminado", [65, 55, 55, 18, 8, 0, 12, 16, 11, 0, 0, 7]),
    ("Pan NY", "Producto terminado", [0, 0, 0, 0, 0, 10, 0, 0, 0, 0, 0, 7]),
    ("Banda", "Producto terminado", [0, 12, 4, 11, 18, 12, 4, 21, 16, 16, 15, 7]),
    ("Cremadet", "Producto terminado", [10, 72, 63, 30, 60, 60, 48, 42, 30, 0, 36, 3]),
    ("Pan 1kg Blanco", "Producto terminado", [35, 15, 28, 27, 30, 17, 24, 8, 32, 0, 30, 8]),
    ("Pan 500g Blanco", "Producto terminado", [15, 15, 130, 42, 29, 30, 60, 20, 83, 75, 20, 6]),
    ("Pan 1kg Integral", "Producto terminado", [18, 24, 5, 20, 24, 10, 0, 26, 24, 34, 16, 3]),
    ("Pan 500g Integral", "Producto terminado", [30, 15, 15, 30, 30, 30, 15, 30, 30, 30, 15, 6]),
    ("Barra Blanca", "Producto terminado", [30, 15, 0, 49, 49, 28, 14, 30, 0, 13, 0, 5]),
    ("Barra Negra", "Producto terminado", [36, 30, 14, 15, 15, 0, 0, 0, 0, 10, 0, 5]),
    ("Pizza", "Producto terminado", [10, 10, 10, 9, 5, 10, 0, 10, 2, 0, 15, 5]),
    # --- Semi-elaborados ---
    ("Masa Caracolas", "Semi-elaborado", [1, 1, 1, 1, 1, 1, 1, 1, None, None, None, 2]),
    ("Masa Croissant", "Semi-elaborado", [8, None, 1, None, 6, None, 6, 9, None, None, None, 1]),
    ("Masa Hojaldre", "Semi-elaborado", [3, None, None, None, 2, None, 6, 6, None, None, None, 1]),
    ("Masa Medialunas", "Semi-elaborado", [3, None, None, None, 5, 6, None, None, None, None, None, 2]),
    ("Masa Ensaimadas", "Semi-elaborado", [150, 77, None, 77, None, None, None, None, None, None, None, 100]),
]

# ── Stock Materia Prima ──────────────────────────────────────────────────────

INVENTARIO_DATES = [
    date(2026, 5, 7),
    date(2026, 5, 14),
    date(2026, 5, 21),
    date(2026, 5, 28),
    date(2026, 6, 5),
    date(2026, 6, 11),
    date(2026, 6, 18),
    date(2026, 6, 25),
    date(2026, 7, 2),
    date(2026, 7, 9),
    date(2026, 7, 16),
    date(2026, 7, 23),
    date(2026, 7, 30),
    date(2026, 8, 6),
]

# Mapping: spreadsheet name -> DB ingredient name (for names that differ)
INGREDIENT_NAME_MAP = {
    "HARINA 000": "Harina 000",
    "HARINA 0000": "Harina 0000",
    "HARINA 00 PIZZA": "Harina 00 Pizza",
    "HARINA INTEGRAL": "Harina Integral",
    "HARINA SALVADO": "Harina Salvado",
    "LEVADURA": "Levadura",
    "AZUCAR": "Azúcar",
    "SAL": "Sal",
    "HUEVOS": "Huevos",
    "MANTECA": "Manteca",
    "MIEL": "Miel",
    "VINAGRE BLANCO": "Vinagre Blanco",
    "SEMOLIN": "Semolín",
    "ACEITE GIRASOL": "Aceite Girasol",
    "ACEITE OLIVA": "Aceite Oliva",
    "PASTELERA": "Harina Pastelera",
    "CHOCOLATE": "Chocolate",
    "GRASA DE CERDO": "Grasa de Cerdo",
    "LECHE": "Leche",
    "CANELA": "Canela",
}

# (spreadsheet_name, unit, [qty per date in chronological order])
INVENTARIO_DATA = [
    ("HARINA 000", "kg", [150, 75, 250, 150, 50, 625, 500, 400, 350, 225, 100, 25, 400, 350]),
    ("HARINA 0000", "kg", [300, 275, 275, 250, 200, 200, 175, 150, 140, 125, 75, 50, 125, 300]),
    ("HARINA 00 PIZZA", "kg", [50, 0, 250, 200, 125, 100, 75, 65, 10, 425, 375, 350, 350, 300]),
    ("HARINA INTEGRAL", "kg", [5, 0, 70, 55, 45, 35, 20, 10, 0, 45, 25, 20, 60, 50]),
    ("HARINA SALVADO", "kg", [40, 40, 20, 20, 20, 18, 20, 20, 20, 20, 18, 17, 16, 15]),
    ("LEVADURA", "kg", [2.5, 2, 0.75, 3.5, 1.5, 0.3, 4.7, 3.5, 2.5, 0.8, 5, 3.5, 1.9, 0]),
    ("AZUCAR", "kg", [50, 40, 38, 35, 25, 22, 70, 65, 50, 48, 40, 37, 35, 15]),
    ("SAL", "kg", [25, 25, 25, 25, 20, 19, 40, 38, 35, 33, 30, 28, 27, 20]),
    ("HUEVOS", "kg", [150, 150, 60, 9, 6, 13.5, 7.5, 6, 6, 6, 4, 3, 4, 2]),
    # Manteca = masa + laminado sumados
    ("MANTECA", "kg", [17, 32, 29, 32, 23, 25, 38, 25, 18, 35, 36, 29, 31, 19]),
    ("MIEL", "kg", [0.3, 1.5, 1, 1, 0.3, 0.5, 0.4, 0.2, 0.2, 0.05, 1.5, 1.2, 0.9, 0.4]),
    ("VINAGRE BLANCO", "L", [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
    ("SEMOLIN", "kg", [37.5, 25, 100, 100, 75, 70, 50, 49, 50, 50, 50, 50, 50, 50]),
    ("ACEITE GIRASOL", "L", [3, 5, 10, 10, 8, 7, 6, 6, 5, 8, 8, 6, 6, 4]),
    ("ACEITE OLIVA", "L", [0, 5, 5, 5, 4.5, 3.5, 3, 3, 2, 6, 6, 4, 4, 3]),
    ("PASTELERA", "L", [0, 2, 2, 0, 0, 1, 0, 0, 0, 0, 0, 0, 2, 0]),
    ("CHOCOLATE", "kg", [0.1, 1.5, 1.5, 0, 2, 1, 1, 0, 3, 3, 3, 3, 1, 0]),
    ("GRASA DE CERDO", "kg", [2, 2, 2, 2, 1.5, 1, 1, 1, 0.8, 0.1, 0, 0, 2, 1.5]),
    ("LECHE", "L", [1, 9, 15, 10, 3, 4, 3, 2, 1, 9, 0, 0, 3, 6]),
    ("CANELA", "kg", [0.3, 0.25, 0.25, 0.25, 0.15, 0.15, 0.1, 0, 0, 0.3, 0.3, 0.3, 0.3, 0.3]),
]


def load_congelados(db):
    """Create frozen products and stock entries."""
    existing_stock = db.query(StockCongelado).count()
    existing_products = db.query(ProductoCongelado).count()
    print(f"  Existing: {existing_products} products, {existing_stock} stock entries")

    # Clear previous data
    db.query(StockCongelado).delete()
    db.query(ProductoCongelado).delete()
    db.commit()
    print("  Cleared existing data")

    products_created = 0
    entries_created = 0

    for pos, (nombre, categoria, values) in enumerate(CONGELADO_PRODUCTS):
        prod = ProductoCongelado(
            nombre=nombre,
            categoria=categoria,
            unidad="u",
            is_active=True,
            position=pos,
        )
        db.add(prod)
        db.flush()

        for i, qty in enumerate(values):
            if qty is None:
                continue
            entry = StockCongelado(
                producto_congelado_id=prod.id,
                cantidad=float(qty),
                fecha_entrada=CONGELADO_DATES[i],
                is_active=True,
            )
            db.add(entry)
            entries_created += 1

        products_created += 1

    db.commit()
    print(f"  Created {products_created} products, {entries_created} stock entries")


def seed_ingredientes(db):
    """Create ingredients if they don't exist."""
    existing = db.query(Ingrediente).count()
    if existing > 0:
        print(f"  Already have {existing} ingredients, skipping")
        return

    cat_by_name = {}
    for cat in db.query(Categoria).filter(Categoria.tipo == "ingrediente").all():
        cat_by_name[cat.nombre.lower()] = cat

    created = 0
    for nombre, cat_nombre, u_compra, cant_compra, precio, u_uso, prov in INGREDIENTES_DATA:
        cat = cat_by_name.get(cat_nombre.lower())
        if not cat:
            print(f"  WARNING: Category '{cat_nombre}' not found for '{nombre}'")
            continue
        ing = Ingrediente(
            nombre=nombre,
            categoria_id=cat.id,
            unidad_compra=u_compra,
            cantidad_compra=cant_compra,
            precio_compra=precio,
            unidad_uso=u_uso,
            proveedor=prov,
        )
        db.add(ing)
        created += 1

    db.commit()
    print(f"  Created {created} ingredients")


def load_inventario(db):
    """Create inventory snapshot records for raw materials."""
    # Look up all ingredients by name
    all_ingredients = db.query(Ingrediente).all()
    ing_by_name = {}
    for ing in all_ingredients:
        ing_by_name[ing.nombre.lower()] = ing

    existing = db.query(InventarioRegistro).count()
    print(f"  Existing: {existing} inventory records")

    # Clear previous data
    db.query(InventarioRegistro).delete()
    db.commit()
    print("  Cleared existing data")

    entries_created = 0
    not_found = []

    for sheet_name, unidad, values in INVENTARIO_DATA:
        db_name = INGREDIENT_NAME_MAP.get(sheet_name, sheet_name)
        ing = ing_by_name.get(db_name.lower())

        if not ing:
            not_found.append(f"{sheet_name} -> {db_name}")
            continue

        for i, qty in enumerate(values):
            if qty is None:
                continue
            reg = InventarioRegistro(
                ingrediente_id=ing.id,
                cantidad=float(qty),
                unidad=unidad,
                fecha_registro=INVENTARIO_DATES[i],
            )
            db.add(reg)
            entries_created += 1

    db.commit()
    print(f"  Created {entries_created} inventory records")
    if not_found:
        print(f"  WARNING: Could not find ingredients: {not_found}")


def main():
    db = SessionLocal()
    try:
        print("=== Loading Stock Congelado ===")
        load_congelados(db)

        print("\n=== Seeding Ingredientes ===")
        seed_ingredientes(db)

        print("\n=== Loading Stock Materia Prima ===")
        load_inventario(db)

        print("\nDone!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
