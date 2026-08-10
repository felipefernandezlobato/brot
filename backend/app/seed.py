from sqlalchemy.orm import Session

from app.auth import hash_pin
from app.models import Categoria, Ingrediente, Receta, TareaProduccion, User
from app.permissions import seed_default_permissions


def seed_data(db: Session):
    if db.query(User).count() == 0:
        admin = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
        db.add(admin)

        categorias = [
            Categoria(nombre="Panes", tipo="receta", margen_objetivo=60, orden=1),
            Categoria(nombre="Masas Madre", tipo="receta", margen_objetivo=60, orden=2),
            Categoria(nombre="Bollería", tipo="receta", margen_objetivo=55, orden=3),
            Categoria(nombre="Pastelería", tipo="receta", margen_objetivo=55, orden=4),
            Categoria(nombre="Harinas", tipo="ingrediente", orden=1),
            Categoria(nombre="Lácteos", tipo="ingrediente", orden=2),
            Categoria(nombre="Grasas", tipo="ingrediente", orden=3),
            Categoria(nombre="Azúcares", tipo="ingrediente", orden=4),
            Categoria(nombre="Levaduras y Mejorantes", tipo="ingrediente", orden=5),
            Categoria(nombre="Frutas y Frutos Secos", tipo="ingrediente", orden=6),
            Categoria(nombre="Otros", tipo="ingrediente", orden=7),
        ]
        db.add_all(categorias)
        db.commit()
        seed_default_permissions(db)

    seed_ingredientes(db)
    seed_recetas(db)
    seed_produccion(db)


# ==============================================================
# Ingredientes
# ==============================================================

def seed_ingredientes(db: Session):
    if db.query(Ingrediente).count() > 0:
        return

    cats = {c.nombre: c.id for c in db.query(Categoria).filter(Categoria.tipo == "ingrediente").all()}

    ingredientes = [
        # Harinas
        dict(nombre="Harina 000", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=640, unidad_uso="kg"),
        dict(nombre="Harina 0000", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=760, unidad_uso="kg"),
        dict(nombre="Harina 00 Pizza", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=800, unidad_uso="kg"),
        dict(nombre="Harina Integral", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=1800, unidad_uso="kg"),
        dict(nombre="Harina Salvado", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=700, unidad_uso="kg"),
        dict(nombre="Harina Pastelera", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=2256, unidad_uso="kg"),
        dict(nombre="Semolín", categoria_id=cats["Harinas"], unidad_compra="kg", cantidad_compra=1, precio_compra=756, unidad_uso="kg"),
        # Lácteos
        dict(nombre="Leche", categoria_id=cats["Lácteos"], unidad_compra="litro", cantidad_compra=1, precio_compra=1639, unidad_uso="litro"),
        dict(nombre="Huevos", categoria_id=cats["Lácteos"], unidad_compra="kg", cantidad_compra=1, precio_compra=3933, unidad_uso="kg"),
        # Grasas
        dict(nombre="Manteca", categoria_id=cats["Grasas"], unidad_compra="kg", cantidad_compra=1, precio_compra=13412, unidad_uso="kg"),
        dict(nombre="Aceite Girasol", categoria_id=cats["Grasas"], unidad_compra="litro", cantidad_compra=1, precio_compra=3811, unidad_uso="litro"),
        dict(nombre="Aceite Oliva", categoria_id=cats["Grasas"], unidad_compra="litro", cantidad_compra=1, precio_compra=16000, unidad_uso="litro"),
        dict(nombre="Grasa de Cerdo", categoria_id=cats["Grasas"], unidad_compra="kg", cantidad_compra=1, precio_compra=3500, unidad_uso="kg"),
        # Azúcares
        dict(nombre="Azúcar", categoria_id=cats["Azúcares"], unidad_compra="kg", cantidad_compra=1, precio_compra=900, unidad_uso="kg"),
        dict(nombre="Miel", categoria_id=cats["Azúcares"], unidad_compra="kg", cantidad_compra=1, precio_compra=7500, unidad_uso="kg"),
        dict(nombre="Chocolate", categoria_id=cats["Azúcares"], unidad_compra="kg", cantidad_compra=1, precio_compra=30000, unidad_uso="kg"),
        # Levaduras y Mejorantes
        dict(nombre="Levadura", categoria_id=cats["Levaduras y Mejorantes"], unidad_compra="kg", cantidad_compra=1, precio_compra=8000, unidad_uso="kg"),
        dict(nombre="Masa Madre", categoria_id=cats["Levaduras y Mejorantes"], unidad_compra="kg", cantidad_compra=1, precio_compra=400, unidad_uso="kg"),
        # Frutas y Frutos Secos
        dict(nombre="Canela", categoria_id=cats["Frutas y Frutos Secos"], unidad_compra="kg", cantidad_compra=1, precio_compra=16900, unidad_uso="kg"),
        # Otros
        dict(nombre="Sal", categoria_id=cats["Otros"], unidad_compra="kg", cantidad_compra=1, precio_compra=340, unidad_uso="kg"),
        dict(nombre="Vinagre Blanco", categoria_id=cats["Otros"], unidad_compra="litro", cantidad_compra=1, precio_compra=1518, unidad_uso="litro"),
        dict(nombre="Agua", categoria_id=cats["Otros"], unidad_compra="litro", cantidad_compra=1, precio_compra=0, unidad_uso="litro"),
        dict(nombre="Tomate", categoria_id=cats["Otros"], unidad_compra="kg", cantidad_compra=1, precio_compra=0, unidad_uso="kg", proveedor="Aldunate"),
    ]

    for data in ingredientes:
        proveedor = data.pop("proveedor", None)
        ing = Ingrediente(**data, proveedor=proveedor)
        db.add(ing)
    db.commit()


# ==============================================================
# Recetas (escandallos)
# ==============================================================

def seed_recetas(db: Session):
    if db.query(Receta).count() > 0:
        return

    cats = {c.nombre: c.id for c in db.query(Categoria).filter(Categoria.tipo == "receta").all()}

    recetas = [
        # Sub-recetas (masas)
        dict(nombre="Masa de Croissant", categoria_id=cats["Masas Madre"], porciones_por_lote=9, es_subreceta=True, unidad_rendimiento="bastones"),
        dict(nombre="Masa de Medialuna", categoria_id=cats["Masas Madre"], porciones_por_lote=6, es_subreceta=True, unidad_rendimiento="bastones"),
        dict(nombre="Masa de Hojaldre", categoria_id=cats["Masas Madre"], porciones_por_lote=6, es_subreceta=True, unidad_rendimiento="bastones"),

        # Panes
        dict(nombre="Pan Blanco 1kg", categoria_id=cats["Panes"], porciones_por_lote=24, precio_venta=1262),
        dict(nombre="Pan Blanco 0.5kg", categoria_id=cats["Panes"], porciones_por_lote=30, precio_venta=631),
        dict(nombre="Pan Integral 1kg", categoria_id=cats["Panes"], porciones_por_lote=1, precio_venta=1880),
        dict(nombre="Pizza 350g", categoria_id=cats["Panes"], porciones_por_lote=1, precio_venta=876),
        dict(nombre="Barra Blanca 350g", categoria_id=cats["Panes"], porciones_por_lote=1, precio_venta=438),
        dict(nombre="Barra Integral 350g", categoria_id=cats["Panes"], porciones_por_lote=1, precio_venta=621),

        # Bollería
        dict(nombre="Croissant", categoria_id=cats["Bollería"], porciones_por_lote=36, precio_venta=1541, notas="36 por bastón"),
        dict(nombre="Medialuna", categoria_id=cats["Bollería"], porciones_por_lote=55, precio_venta=1129, notas="55 por bastón"),
        dict(nombre="Napolitana", categoria_id=cats["Bollería"], porciones_por_lote=36, precio_venta=3341, notas="36 por bastón"),
        dict(nombre="Cruffin", categoria_id=cats["Bollería"], porciones_por_lote=36, precio_venta=1541, notas="36 por bastón"),
        dict(nombre="Pan Suisse", categoria_id=cats["Bollería"], porciones_por_lote=36, precio_venta=2823, notas="36 por bastón"),
        dict(nombre="NY Roll", categoria_id=cats["Bollería"], porciones_por_lote=36, precio_venta=1541, notas="36 por bastón"),
        dict(nombre="Moño", categoria_id=cats["Bollería"], porciones_por_lote=36, precio_venta=1541, notas="36 por bastón"),
        dict(nombre="Ensaimadas", categoria_id=cats["Bollería"], porciones_por_lote=77, precio_venta=531),

        # Pastelería / Hojaldre
        dict(nombre="Palmerita", categoria_id=cats["Pastelería"], porciones_por_lote=54, precio_venta=1081, notas="54 por bastón"),
        dict(nombre="Cremadets", categoria_id=cats["Pastelería"], porciones_por_lote=36, precio_venta=1583, notas="36 por bastón"),
        dict(nombre="Banda de Manzana", categoria_id=cats["Pastelería"], porciones_por_lote=15, precio_venta=3800, notas="15 por bastón"),
        dict(nombre="Roll de Canela", categoria_id=cats["Pastelería"], porciones_por_lote=1, precio_venta=1000),
    ]

    for data in recetas:
        r = Receta(**data)
        db.add(r)
    db.commit()


# ==============================================================
# Produccion (calendario semanal)
# ==============================================================

def _t(dia, hora, titulo, descripcion, duracion, tipo="produccion", cantidad=None, unidad=None, receta_nombre=None):
    return {
        "dia": dia, "hora": hora, "titulo": titulo, "descripcion": descripcion,
        "duracion": duracion, "tipo": tipo, "cantidad": cantidad, "unidad": unidad,
        "receta_nombre": receta_nombre,
    }


def seed_produccion(db: Session):
    if db.query(TareaProduccion).count() > 0:
        return

    receta_map = {r.nombre: r.id for r in db.query(Receta).all()}

    tareas_data = [
        # === LUNES (1) ===
        _t(1, "07:00", "Pan Masa - Pan Blanco 1kg",
           "24x1kg\n50min 10 pesar + 40 amasar",
           50, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(1, "07:00", "Pan Masa - Pan Blanco 0.5kg",
           "30x0.5kg",
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(1, "08:00", "Laminar Hojaldre",
           "3 bastones\n- 18 min 1a vuelta +\n- 12 min 2a vuelta\n30 min",
           30, cantidad=3, unidad="bastones", receta_nombre="Masa de Hojaldre"),
        _t(1, "09:00", "Croissant Cortar",
           "5 bastones - 204 crois\n50min (10 min / baston)",
           50, cantidad=204, unidad="unidades", receta_nombre="Croissant"),
        _t(1, "10:00", "Croissant Armar",
           "5 bastones - 204 crois\n40min (8min / baston)",
           40, cantidad=204, unidad="unidades", receta_nombre="Croissant"),
        _t(1, "11:00", "Pan Armar - Pan Blanco 1kg",
           "24x1kg\n20 min",
           20, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(1, "11:00", "Pan Armar - Pan Blanco 0.5kg",
           "30x0.5kg",
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(1, "12:00", "Limpieza",
           "Bandejas, bacha, horno...\n90 min",
           90, "limpieza"),

        # === MARTES (2) ===
        _t(2, "07:00", "Cocinar Pan - Pan Blanco 1kg",
           "x5 horneadas\n10min por horneada",
           50, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(2, "07:00", "Cocinar Pan - Pan Blanco 0.5kg",
           None,
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(2, "08:00", "Medialuna Cortar",
           "5 bastones\n- 15 min por baston\n75 min",
           75, cantidad=5, unidad="bastones", receta_nombre="Medialuna"),
        _t(2, "10:00", "Medialuna Armar",
           "5 bastones\n- 12 min por baston\n60 min",
           60, cantidad=5, unidad="bastones", receta_nombre="Medialuna"),
        _t(2, "11:00", "Croissant Preparacion",
           "- 60 units = 10 min\n210 units\n40 min",
           40, cantidad=210, unidad="unidades", receta_nombre="Croissant"),
        _t(2, "12:00", "Croissant Cocina",
           "- 60 units = 18 min\n210 units\n72 min",
           72, cantidad=210, unidad="unidades", receta_nombre="Croissant"),
        _t(2, None, "Pedir Manteca", None, None, "nota"),

        # === MIERCOLES (3) ===
        _t(3, "07:00", "Pan Masa - Pan Blanco 1kg",
           "24x1kg\n50min 10 pesar + 40 amasar",
           50, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(3, "07:00", "Pan Masa - Pan Blanco 0.5kg",
           "30x0.5kg",
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(3, "08:00", "Bolleria Hojaldre invertido",
           "2 Baston - 76 units\n27 minutos",
           27, "nota"),
        _t(3, "09:00", "Napolitana",
           "1 baston - 36 units\n19 min",
           19, cantidad=36, unidad="unidades", receta_nombre="Napolitana"),
        _t(3, "09:00", "Cruffin",
           "1 baston - 35 units\n19 min",
           19, cantidad=35, unidad="unidades", receta_nombre="Cruffin"),
        _t(3, "10:00", "Bolleria Caracolas",
           "1 baston - 63 units\n20 min",
           20, "nota"),
        _t(3, "11:00", "Bolleria Sacramento",
           "1 baston Med - 65 units\n27 min",
           27, "nota"),
        _t(3, "12:00", "Pan Armar - Pan Blanco 1kg",
           "24x1kg\n20 min",
           20, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(3, "12:00", "Pan Armar - Pan Blanco 0.5kg",
           "30x0.5kg",
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(3, "13:00", "Medialuna Preparacion",
           "- 125 units = 10 min\n325 units\n30 min",
           30, cantidad=325, unidad="unidades", receta_nombre="Medialuna"),
        _t(3, "14:00", "Medialuna Cocina",
           "- 125 units = 12 min\n325 units\n36 min",
           36, cantidad=325, unidad="unidades", receta_nombre="Medialuna"),
        _t(3, None, "LLEVAR PEDIDO", None, None, "entrega"),

        # === JUEVES (4) ===
        _t(4, "07:00", "Cocinar Pan - Pan Blanco 1kg",
           "x5 horneadas\n10min por horneada",
           50, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(4, "07:00", "Cocinar Pan - Pan Blanco 0.5kg",
           None,
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(4, "08:00", "Palmeritas",
           "55 units\n15 min pre forma\n10 min cortar y estirar\n25 min total",
           25, cantidad=55, unidad="unidades", receta_nombre="Palmerita"),
        _t(4, "09:00", "Cremadets",
           "37 units\n15 min",
           15, cantidad=37, unidad="unidades", receta_nombre="Cremadets"),
        _t(4, "10:00", "Banda de Manzana",
           "15 units\n25 min",
           25, cantidad=15, unidad="unidades", receta_nombre="Banda de Manzana"),
        _t(4, "11:00", "Cocinar Napolitana",
           "36 units\n18 min",
           18, cantidad=36, unidad="unidades", receta_nombre="Napolitana"),
        _t(4, "11:00", "Cocinar Cruffin",
           "35 units\n18 min",
           18, cantidad=35, unidad="unidades", receta_nombre="Cruffin"),
        _t(4, "11:00", "Cocinar Caracolas",
           "63 units\n18 min",
           18, "nota"),
        _t(4, "11:00", "Cocinar Sacramento",
           "65 units\n18 min",
           18, "nota"),
        _t(4, "11:00", "Cocinar Hojaldre invertido",
           "76 units\n18 min",
           18, "nota"),
        _t(4, "12:00", "Cocinar Palmeritas",
           "55 units\n20 min",
           20, cantidad=55, unidad="unidades", receta_nombre="Palmerita"),
        _t(4, "12:00", "Cocinar Banda de Manzana",
           "15 units\n20 min",
           20, cantidad=15, unidad="unidades", receta_nombre="Banda de Manzana"),
        _t(4, "13:00", "Inventario",
           "45 min",
           45, "admin"),
        _t(4, None, "Guardar + Armar Pedido",
           "40 min",
           40, "admin"),

        # === VIERNES (5) ===
        _t(5, "07:00", "Manteca",
           "Manteca pomada\n100 min",
           100, "nota"),
        _t(5, "09:00", "Pan Masa - Pan Blanco 1kg",
           "24x1kg\n50min 10 pesar + 40 amasar",
           50, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(5, "09:00", "Pan Masa - Pan Blanco 0.5kg",
           "30x0.5kg",
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(5, "10:00", "Croissant Masa",
           "- 10 min pesar\n- 20 min amasar\n30 min total",
           30, cantidad=9, unidad="bastones", receta_nombre="Masa de Croissant"),
        _t(5, "11:00", "Medialuna Masa",
           "- 10 min pesar\n- 20 min amasar\n30 min total",
           30, cantidad=6, unidad="bastones", receta_nombre="Masa de Medialuna"),
        _t(5, "12:00", "Pan Armar - Pan Blanco 1kg",
           "24x1kg\n20 min",
           20, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(5, "12:00", "Pan Armar - Pan Blanco 0.5kg",
           "30x0.5kg",
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(5, "13:00", "Limpieza",
           "Bandeja, laminadora...\n45 min",
           45, "limpieza"),
        _t(5, None, "LLEVAR PEDIDO", None, None, "entrega"),

        # === SABADO (6) ===
        _t(6, "07:00", "Laminar Croissant",
           "12 bastones\n6 min por baston\n66 min",
           66, cantidad=12, unidad="bastones", receta_nombre="Masa de Croissant"),
        _t(6, "08:00", "Laminar Medialuna",
           "6 bastones\n6 min por baston\n36 min",
           36, cantidad=6, unidad="bastones", receta_nombre="Masa de Medialuna"),
        _t(6, "09:00", "Cocinar Pan - Pan Blanco 1kg",
           "x5 horneadas\n10min por horneada",
           50, cantidad=24, unidad="unidades", receta_nombre="Pan Blanco 1kg"),
        _t(6, "09:00", "Cocinar Pan - Pan Blanco 0.5kg",
           None,
           None, cantidad=30, unidad="unidades", receta_nombre="Pan Blanco 0.5kg"),
        _t(6, "10:00", "Laminar Croissant",
           "9 bastones\n4 min por baston\n36 min",
           36, cantidad=9, unidad="bastones", receta_nombre="Masa de Croissant"),
        _t(6, "11:00", "Laminar Medialuna",
           "9 bastones\n4 min por baston\n36 min",
           36, cantidad=9, unidad="bastones", receta_nombre="Masa de Medialuna"),
        _t(6, "12:00", "Hojaldre Masa",
           "15 min",
           15, cantidad=6, unidad="bastones", receta_nombre="Masa de Hojaldre"),
        _t(6, "13:00", "Ensaimadas",
           "77 units\nPrimera parte: 15 min\nSegunda parte: 20 min\nTercera parte: 10 min\n45 min",
           45, cantidad=77, unidad="unidades", receta_nombre="Ensaimadas"),
        _t(6, None, "Armar Pedido",
           "30min",
           30, "admin"),
    ]

    pos = 0
    for d in tareas_data:
        receta_id = receta_map.get(d["receta_nombre"]) if d["receta_nombre"] else None
        t = TareaProduccion(
            dia_semana=d["dia"],
            hora=d["hora"],
            titulo=d["titulo"],
            descripcion=d["descripcion"],
            duracion_minutos=d["duracion"],
            tipo=d["tipo"],
            cantidad_planificada=d["cantidad"],
            unidad_cantidad=d["unidad"],
            receta_id=receta_id,
            posicion=pos,
        )
        db.add(t)
        pos += 1
    db.commit()
