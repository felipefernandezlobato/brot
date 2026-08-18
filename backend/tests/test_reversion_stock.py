"""Stock must come back when a merma or a B2B delivery is undone.

Both modules deducted on create and gave nothing back on delete, so a mistyped
waste record or a cancelled delivery quietly ate inventory forever.
"""

from datetime import date

from app.auth import hash_pin
from app.models import (
    Categoria,
    ClienteB2B,
    Ingrediente,
    InventarioRegistro,
    MovimientoStock,
    ProductoCatalogo,
    ProductoCongelado,
    Receta,
    StockCongelado,
    User,
)

HOY = date.today().isoformat()


def _auth(client, db):
    db.add(User(name="Admin", pin_hash=hash_pin("0000"), role="admin"))
    db.commit()
    token = client.post("/api/auth/login", json={"name": "Admin", "pin": "0000"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _ingrediente(db, stock=50.0):
    cat = Categoria(nombre="Harinas", tipo="ingrediente")
    db.add(cat)
    db.flush()
    ing = Ingrediente(
        nombre="Harina 000", categoria_id=cat.id, unidad_compra="kg", unidad_uso="kg",
        precio_compra=760.0, cantidad_compra=1.0,
    )
    db.add(ing)
    db.flush()
    db.add(InventarioRegistro(
        ingrediente_id=ing.id, cantidad=stock, unidad="kg", fecha_registro=date.today(),
    ))
    db.commit()
    return ing


def _saldo(db, ing_id):
    return (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ing_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
        .cantidad
    )


# ==============================================================
# Mermas
# ==============================================================


def test_borrar_merma_devuelve_el_stock(client, db):
    headers = _auth(client, db)
    ing = _ingrediente(db)

    res = client.post(
        "/api/mermas",
        json={"ingrediente_id": ing.id, "cantidad": 5.0, "unidad": "kg", "motivo": "dañado", "fecha": HOY},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert _saldo(db, ing.id) == 45.0

    assert client.delete(f"/api/mermas/{res.json()['id']}", headers=headers).status_code == 200

    assert _saldo(db, ing.id) == 50.0


def test_editar_cantidad_de_merma_sobrescribe(client, db):
    headers = _auth(client, db)
    ing = _ingrediente(db)

    mid = client.post(
        "/api/mermas",
        json={"ingrediente_id": ing.id, "cantidad": 5.0, "unidad": "kg", "motivo": "dañado", "fecha": HOY},
        headers=headers,
    ).json()["id"]
    assert _saldo(db, ing.id) == 45.0

    client.put(f"/api/mermas/{mid}", json={"cantidad": 8.0}, headers=headers)

    assert _saldo(db, ing.id) == 42.0  # 50 - 8, not 50 - 5 - 8


# ==============================================================
# Entregas B2B
# ==============================================================


def _catalogo_con_stock(db, unidades=20.0):
    cat = Categoria(nombre="Panes", tipo="receta")
    db.add(cat)
    db.flush()
    receta = Receta(nombre="Pan Blanco 1kg", categoria_id=cat.id, porciones_por_lote=1)
    db.add(receta)
    db.flush()
    prod = ProductoCongelado(
        nombre="Pan Blanco 1kg", categoria="panes", unidad="u",
        receta_id=receta.id, nivel="terminado",
    )
    db.add(prod)
    db.flush()
    db.add(StockCongelado(
        producto_congelado_id=prod.id, cantidad=unidades,
        fecha_entrada=date.today(), is_active=True,
    ))
    catalogo = ProductoCatalogo(
        nombre="Pan Blanco 1kg", precio=1262.0, categoria="panes",
        receta_id=receta.id, disponible=True,
    )
    cli = ClienteB2B(nombre="Creme")
    db.add_all([catalogo, cli])
    db.commit()
    return prod, catalogo, cli


def _stock(db, prod_id):
    return sum(
        e.cantidad for e in db.query(StockCongelado).filter(
            StockCongelado.producto_congelado_id == prod_id,
            StockCongelado.is_active.is_(True),
        )
    )


def test_borrar_entrega_entregada_devuelve_el_stock(client, db):
    headers = _auth(client, db)
    prod, catalogo, cli = _catalogo_con_stock(db)

    res = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cli.id, "fecha_entrega": HOY, "estado": "entregado",
            "lineas": [{"producto_id": catalogo.id, "cantidad": 6, "precio_unitario": 1262.0}],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert _stock(db, prod.id) == 14.0

    assert client.delete(f"/api/entregas-b2b/{res.json()['id']}", headers=headers).status_code == 200

    assert _stock(db, prod.id) == 20.0


def test_sacar_entrega_de_entregado_devuelve_el_stock(client, db):
    headers = _auth(client, db)
    prod, catalogo, cli = _catalogo_con_stock(db)

    eid = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cli.id, "fecha_entrega": HOY, "estado": "entregado",
            "lineas": [{"producto_id": catalogo.id, "cantidad": 6, "precio_unitario": 1262.0}],
        },
        headers=headers,
    ).json()["id"]
    assert _stock(db, prod.id) == 14.0

    client.put(f"/api/entregas-b2b/{eid}/estado", json={"estado": "pendiente"}, headers=headers)

    assert _stock(db, prod.id) == 20.0


def test_editar_lineas_de_entregada_sobrescribe(client, db):
    headers = _auth(client, db)
    prod, catalogo, cli = _catalogo_con_stock(db)

    eid = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cli.id, "fecha_entrega": HOY, "estado": "entregado",
            "lineas": [{"producto_id": catalogo.id, "cantidad": 6, "precio_unitario": 1262.0}],
        },
        headers=headers,
    ).json()["id"]
    assert _stock(db, prod.id) == 14.0

    client.put(
        f"/api/entregas-b2b/{eid}",
        json={"lineas": [{"producto_id": catalogo.id, "cantidad": 9, "precio_unitario": 1262.0}]},
        headers=headers,
    )

    assert _stock(db, prod.id) == 11.0  # 20 - 9, not 20 - 6 - 9


def test_entrega_no_entregada_no_toca_stock(client, db):
    headers = _auth(client, db)
    prod, catalogo, cli = _catalogo_con_stock(db)

    eid = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cli.id, "fecha_entrega": HOY, "estado": "pendiente",
            "lineas": [{"producto_id": catalogo.id, "cantidad": 6, "precio_unitario": 1262.0}],
        },
        headers=headers,
    ).json()["id"]
    assert _stock(db, prod.id) == 20.0

    client.delete(f"/api/entregas-b2b/{eid}", headers=headers)

    assert _stock(db, prod.id) == 20.0


def test_entrega_mayor_al_stock_no_deja_el_ledger_negativo(client, db):
    """Pedir mas de lo que hay debe clampear en el stock real, no restar el pedido completo.

    Antes, el movimiento registraba -cantidad (lo pedido) sin importar cuanto
    habia realmente: pedir 9 con solo 5 disponibles restaba 9 del ledger aunque
    fisicamente solo salieron 5 unidades.
    """
    headers = _auth(client, db)
    prod, catalogo, cli = _catalogo_con_stock(db, unidades=5.0)

    res = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cli.id, "fecha_entrega": HOY, "estado": "entregado",
            "lineas": [{"producto_id": catalogo.id, "cantidad": 9, "precio_unitario": 1262.0}],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert _stock(db, prod.id) == 0.0

    mov = db.query(MovimientoStock).filter(
        MovimientoStock.tipo_stock == "congelado",
        MovimientoStock.referencia_producto_id == prod.id,
        MovimientoStock.tipo_movimiento == "entrega_b2b",
    ).one()
    assert mov.cantidad == -5.0  # lo que realmente salio, not -9
    assert "insuficiente" in (mov.notas or "").lower()


def _catalogo_de_terminado_sin_receta_propia(db, unidades_masa=100.0, unidades_terminado=20.0):
    """Ensaimadas: la masa tiene receta_id=X, pero el terminado (solo horneado,
    sin insumos propios) no tiene receta -- comparten familia via producto_padre_id,
    no via receta_id. El catalogo apunta a la receta de la masa (es la unica que
    existe), pero una venta debe salir del terminado, nunca de la masa cruda."""
    cat = Categoria(nombre="Bolleria", tipo="receta")
    db.add(cat)
    db.flush()
    receta_masa = Receta(nombre="Ensaimadas", categoria_id=cat.id, porciones_por_lote=1)
    db.add(receta_masa)
    db.flush()

    masa = ProductoCongelado(
        nombre="Ensaimada Amasada", categoria="masas", unidad="u",
        receta_id=receta_masa.id, nivel="masa",
    )
    db.add(masa)
    db.flush()
    db.add(StockCongelado(
        producto_congelado_id=masa.id, cantidad=unidades_masa,
        fecha_entrada=date.today(), is_active=True,
    ))

    terminado = ProductoCongelado(
        nombre="Ensaimadas Cocinado", categoria="Bolleria", unidad="u",
        receta_id=None, nivel="terminado",
        producto_padre_id=masa.id, cantidad_por_padre=1.0,
    )
    db.add(terminado)
    db.flush()
    db.add(StockCongelado(
        producto_congelado_id=terminado.id, cantidad=unidades_terminado,
        fecha_entrada=date.today(), is_active=True,
    ))

    catalogo = ProductoCatalogo(
        nombre="Ensaimadas", precio=500.0, categoria="Bolleria",
        receta_id=receta_masa.id, disponible=True,
    )
    cli = ClienteB2B(nombre="Olula")
    db.add_all([catalogo, cli])
    db.commit()
    return masa, terminado, catalogo, cli


def test_entrega_de_terminado_sin_receta_propia_no_descuenta_la_masa(client, db):
    """Bug real: el catalogo resolvia por receta_id y encontraba la masa (unica
    con esa receta), asi que una entrega de Ensaimadas terminadas vaciaba la
    masa cruda en vez del producto horneado."""
    headers = _auth(client, db)
    masa, terminado, catalogo, cli = _catalogo_de_terminado_sin_receta_propia(db)

    res = client.post(
        "/api/entregas-b2b",
        json={
            "cliente_b2b_id": cli.id, "fecha_entrega": HOY, "estado": "entregado",
            "lineas": [{"producto_id": catalogo.id, "cantidad": 8, "precio_unitario": 500.0}],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text

    assert _stock(db, terminado.id) == 12.0  # 20 - 8
    assert _stock(db, masa.id) == 100.0  # sin tocar
