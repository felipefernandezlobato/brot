"""Cuantas consultas SQL cuesta cada pantalla.

No mide tiempo (en SQLite cualquier cosa va rapido y no diria nada): mide el
NUMERO de consultas, que es lo que se paga caro en produccion. El backend esta
en Render (Oregon) y la base en Neon (Frankfurt), asi que cada consulta cruza
el Atlantico: ~90ms de ida y vuelta. 68 consultas son 6 segundos de red aunque
cada una tarde 0,2ms en ejecutarse. Esa es toda la diferencia entre una
pantalla que abre al instante y una que se piensa.

Los limites de aqui abajo son techos, no objetivos. Si una pantalla los pasa es
que alguien reintrodujo un N+1 -- una consulta dentro de un bucle -- y el test
tiene que fallar ANTES de que se note desde Argentina. Por eso las recetas de
prueba replican la cadena real de tres niveles (masa -> baston -> terminado):
un N+1 por subrecetas solo aparece cuando hay subrecetas.
"""

from contextlib import contextmanager

from sqlalchemy import event

from app.main import app
from app.routers.recetas import router as recetas_router
from app.routers.produccion import router as produccion_router

app.include_router(recetas_router)
app.include_router(produccion_router)

from app.auth import hash_pin
from app.models import (
    Categoria,
    Ingrediente,
    LineaReceta,
    ProductoCongelado,
    Receta,
    TareaProduccion,
    User,
)
from app.services.costes import costo_linea, costo_receta, precargar_arbol


@contextmanager
def contar_consultas(db):
    """Cuenta los SELECT/INSERT/... que salen por la conexion de este test.

    Vacia la sesion antes de medir, y eso es lo que hace que la medicion valga:
    los tests comparten la sesion con el setup que creo los datos, asi que todo
    estaba en el mapa de identidad de SQLAlchemy y cada `t.receta.nombre` salia
    gratis. En produccion cada peticion abre una sesion limpia. Sin este
    expunge, el test medias 3 consultas donde la app hacia 63.
    """
    consultas = []
    conn = db.get_bind()
    db.expunge_all()

    def _antes(conn_, cursor, statement, params, context, executemany):
        consultas.append(statement)

    event.listen(conn, "before_cursor_execute", _antes)
    try:
        yield consultas
    finally:
        event.remove(conn, "before_cursor_execute", _antes)


def _cadena(db, cat_i, cat_r, n: int):
    """n cadenas completas masa -> baston -> terminado, como Croissant o Medialuna.

    Cada terminado cuesta a traves de dos subrecetas anidadas, que es
    exactamente donde el motor de costeo se iba a buscar las lineas de una en
    una.
    """
    harina = Ingrediente(
        nombre="Harina", categoria_id=cat_i.id, unidad_compra="kg",
        cantidad_compra=25, precio_compra=25000, unidad_uso="g",
    )
    manteca = Ingrediente(
        nombre="Manteca", categoria_id=cat_i.id, unidad_compra="kg",
        cantidad_compra=10, precio_compra=90000, unidad_uso="g",
    )
    db.add_all([harina, manteca])
    db.flush()

    terminados = []
    for i in range(n):
        masa = Receta(
            nombre=f"Masa {i}", categoria_id=cat_r.id, porciones_por_lote=10,
            es_subreceta=True, unidad_rendimiento="u",
        )
        db.add(masa)
        db.flush()
        db.add_all([
            LineaReceta(receta_id=masa.id, ingrediente_id=harina.id, cantidad=4000, unidad="g"),
            LineaReceta(receta_id=masa.id, ingrediente_id=manteca.id, cantidad=1000, unidad="g"),
        ])

        baston = Receta(
            nombre=f"Baston {i}", categoria_id=cat_r.id, porciones_por_lote=1,
            es_subreceta=True, unidad_rendimiento="u",
        )
        db.add(baston)
        db.flush()
        db.add(LineaReceta(receta_id=baston.id, subreceta_id=masa.id, cantidad=1, unidad="u"))

        term = Receta(
            nombre=f"Producto {i}", categoria_id=cat_r.id, porciones_por_lote=40,
            precio_venta=1500,
        )
        db.add(term)
        db.flush()
        db.add(LineaReceta(receta_id=term.id, subreceta_id=baston.id, cantidad=1, unidad="u"))
        db.flush()
        terminados.append(term.id)

    db.commit()
    return terminados


def _setup(client, db, n=12):
    user = User(name="Admin", pin_hash=hash_pin("0000"), role="admin")
    cat_i = Categoria(nombre="Harinas", tipo="ingrediente")
    cat_r = Categoria(nombre="Panes", tipo="receta")
    db.add_all([user, cat_i, cat_r])
    db.commit()
    ids_terminados = _cadena(db, cat_i, cat_r, n)
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return token, cat_r.id, ids_terminados


def test_listado_de_recetas_no_escala_con_la_cantidad(client, db):
    """El costeo de 36 recetas no puede costar mas consultas que el de 9."""
    token, _, _ = _setup(client, db, n=12)
    headers = {"Authorization": f"Bearer {token}"}

    with contar_consultas(db) as consultas:
        res = client.get("/api/recetas", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 36  # 12 cadenas x 3 niveles

    # 1 usuario (auth) + categorias + recetas + lineas + ingredientes, y poco mas.
    assert len(consultas) <= 8, (
        f"{len(consultas)} consultas para listar 36 recetas:\n"
        + "\n".join(consultas)
    )


def test_listado_filtrado_no_paga_por_las_subrecetas_que_quedan_fuera(client, db):
    """El filtro es donde dolia: 40 consultas para 12 recetas.

    Sin filtro, toda subreceta esta en el propio resultado y ya viene cargada.
    Filtrando por nombre o categoria, los bastones y las masas quedan fuera y
    el costeo bajaba a buscarlos de uno en uno, dos niveles por receta.
    """
    token, cat_r_id, _ = _setup(client, db, n=12)
    headers = {"Authorization": f"Bearer {token}"}

    for url, esperadas in [("/api/recetas?buscar=Producto", 12),
                           (f"/api/recetas?categoria_id={cat_r_id}", 36)]:
        with contar_consultas(db) as consultas:
            res = client.get(url, headers=headers)
        assert res.status_code == 200
        assert len(res.json()) == esperadas
        assert all(r["costo_por_porcion"] > 0 for r in res.json() if r["lineas"])
        assert len(consultas) <= 8, (
            f"{len(consultas)} consultas en {url}:\n" + "\n".join(consultas)
        )


def test_el_costo_es_el_mismo_con_y_sin_precarga(client, db):
    """La precarga no puede mover ni un decimal: solo adelanta consultas.

    Compara bit a bit el mismo costeo con la sesion fria y sin precargar contra
    el costeo precargado. Es la unica garantia que importa de todo este
    archivo: las demas pruebas miden velocidad, esta mide que el numero sigue
    siendo el mismo.

    De paso fija el valor: masa 4000g harina (4.000) + 1000g manteca (9.000) =
    13.000 el lote de 10 -> 1.300 la porcion -> el baston usa 1 porcion -> el
    terminado usa 1 baston / 40 porciones = 32,50.
    """
    token, _, terminados = _setup(client, db, n=3)

    sin_precarga = {}
    for rid in terminados:
        db.expunge_all()
        receta = db.query(Receta).filter(Receta.id == rid).first()
        sin_precarga[rid] = (
            costo_receta(receta, db),
            [costo_linea(l, db) for l in receta.lineas],
        )

    con_precarga = {}
    for rid in terminados:
        db.expunge_all()
        receta = db.query(Receta).filter(Receta.id == rid).first()
        precargar_arbol(db, [receta])
        con_precarga[rid] = (
            costo_receta(receta, db),
            [costo_linea(l, db) for l in receta.lineas],
        )

    assert con_precarga == sin_precarga
    assert round(sin_precarga[terminados[0]][0][1], 2) == 32.50

    # Y lo mismo a traves de la API, que es por donde se mira de verdad.
    headers = {"Authorization": f"Bearer {token}"}
    uno = client.get(f"/api/recetas/{terminados[0]}", headers=headers).json()
    en_lista = [r for r in client.get("/api/recetas", headers=headers).json()
                if r["id"] == terminados[0]][0]
    assert round(uno["costo_por_porcion"], 2) == 32.50
    assert en_lista["costo_por_porcion"] == uno["costo_por_porcion"]
    assert en_lista["lineas"][0]["costo_linea"] == uno["lineas"][0]["costo_linea"]


def test_dia_de_produccion_no_escala_con_las_tareas(client, db):
    """La pantalla del dia hacia 4-5 consultas por tarea.

    Por cada tarea: el producto congelado, su padre, la receta, las lineas de
    la receta y el ingrediente mayor. Con 20 tareas eso son 150-200 consultas
    para pintar una lista que cabe en una pantalla.
    """
    token, cat_r, terminados = _setup(client, db, n=12)
    headers = {"Authorization": f"Bearer {token}"}

    # Cada terminado cuelga de un padre, que es la condicion para que la vista
    # tenga que resolver el consumo declarable.
    for i, term_id in enumerate(terminados):
        padre = ProductoCongelado(
            nombre=f"Masa {i}", nivel="masa", unidad="u", categoria="Panes",
        )
        db.add(padre)
        db.flush()
        hijo = ProductoCongelado(
            nombre=f"Producto {i}", nivel="terminado", unidad="u",
            categoria="Panes", receta_id=term_id,
            producto_padre_id=padre.id, cantidad_por_padre=40,
        )
        db.add(hijo)
        db.flush()
        db.add(TareaProduccion(
            dia_semana=1, hora="06:00", titulo=f"Hornear {i}", tipo="produccion",
            cantidad_planificada=40, unidad_cantidad="u",
            receta_id=term_id, producto_congelado_id=hijo.id,
            posicion=i, is_active=True,
        ))
    db.commit()

    with contar_consultas(db) as consultas:
        res = client.get("/api/produccion/dia?fecha=2026-10-19", headers=headers)  # lunes
    assert res.status_code == 200
    datos = res.json()
    assert len(datos["tareas"]) == 12
    assert all(t["consumo_padre_label"] is not None for t in datos["tareas"])
    assert all(t["porciones_por_lote"] == 40 for t in datos["tareas"])

    assert len(consultas) <= 10, (
        f"{len(consultas)} consultas para 12 tareas:\n" + "\n".join(consultas)
    )
