"""Una sola definición del importe de una entrega, y entregas sin líneas.

La multiplicación `cantidad × precio_unitario` estaba escrita a mano en cinco
sitios. Estos tests fijan las dos cosas que se arreglaron: que el importe
salga igual lo mire quien lo mire, y que no se pueda guardar una entrega
vacía.
"""

from datetime import date, datetime, timezone

import pytest

from app.auth import hash_pin
from app.main import app
from app.models import (
    ClienteB2B,
    EntregaB2B,
    LineaEntregaB2B,
    ProductoCatalogo,
    User,
)
from app.services.importes import importe_linea, total_entrega
from app.services.mensual import ventas
from app.services.pedidos_vista import construir_entrega_out

HOY = date.today()


def _token(client, db, role="admin"):
    u = User(name=f"U-{role}", pin_hash=hash_pin("1234"), role=role)
    db.add(u)
    db.commit()
    return client.post("/api/auth/login", json={"name": f"U-{role}", "pin": "1234"}).json()["token"]


def _entrega_con(db, lineas, estado="entregado"):
    c = ClienteB2B(nombre="Cliente", is_active=True)
    db.add(c)
    db.flush()
    e = EntregaB2B(cliente_b2b_id=c.id, fecha_entrega=HOY, estado=estado,
                   created_at=datetime.now(timezone.utc))
    db.add(e)
    db.flush()
    for nombre, cant, precio in lineas:
        p = ProductoCatalogo(nombre=nombre, precio=precio or 0, categoria="Panes")
        db.add(p)
        db.flush()
        db.add(LineaEntregaB2B(entrega_id=e.id, producto_id=p.id,
                               cantidad=cant, precio_unitario=precio))
    db.flush()
    db.refresh(e, ["lineas"])
    return c, e


def test_un_precio_en_cero_vale_cero_y_no_estorba(db):
    """El formulario deja entregar productos sin precio, después de avisar
    ("se registrarán como entregados sin facturar").

    Esto NO cubre un `precio_unitario` nulo: no es alcanzable. La columna lleva
    `default=0` y el esquema de entrada también, así que un None se convierte
    en 0 al insertar — se comprobó contra producción, 0 nulos en 303 líneas.
    Las guardas `or 0` del código son defensivas, no arreglan un fallo vivo.
    """
    _, e = _entrega_con(db, [("Pan", 3, 1000), ("Regalo", 2, 0)])
    db.commit()

    assert total_entrega(e) == pytest.approx(3000)
    assert importe_linea(e.lineas[1]) == 0


def test_el_endpoint_de_todas_devuelve_el_total_consolidado(client, db):
    """Este endpoint tenía su propia copia de la fórmula; ahora usa la común."""
    token = _token(client, db)
    _entrega_con(db, [("Pan", 3, 1000), ("Regalo", 2, 0)])
    db.commit()

    res = client.get("/api/entregas-b2b/todas", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert res.json()[0]["total"] == pytest.approx(3000)


def test_las_tres_vistas_dan_el_mismo_importe(db):
    """`ventas()` (estadísticas), `construir_entrega_out` (historial) y
    `total_entrega` (listados) tienen que coincidir al peso: si divergen, dos
    pantallas enseñan cifras distintas de la misma entrega y nadie sabe cuál
    creer."""
    _, e = _entrega_con(db, [("Croissant", 7, 1550), ("Focaccia", 2, 14160)])
    db.commit()

    esperado = 7 * 1550 + 2 * 14160
    assert total_entrega(e) == pytest.approx(esperado)
    assert construir_entrega_out(e).total == pytest.approx(esperado)
    desde_ventas = sum(l.monto for l in ventas(db, HOY, HOY) if l.canal == "b2b")
    assert desde_ventas == pytest.approx(esperado)


def test_no_se_puede_crear_una_entrega_sin_productos(client, db):
    """Contaba como pedido en la ficha del cliente, aportaba 0 al facturado y
    diluía el ticket promedio. El portal ya lo exigía; el obrador no."""
    token = _token(client, db)
    c = ClienteB2B(nombre="Cliente", is_active=True)
    db.add(c)
    db.commit()

    res = client.post(
        "/api/entregas-b2b",
        json={"cliente_b2b_id": c.id, "fecha_entrega": HOY.isoformat(),
              "estado": "pendiente", "lineas": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert "al menos un producto" in res.json()["detail"]


def test_no_se_puede_vaciar_una_entrega_al_editarla(client, db):
    token = _token(client, db)
    _, e = _entrega_con(db, [("Pan", 3, 1000)], estado="pendiente")
    db.commit()

    res = client.put(
        f"/api/entregas-b2b/{e.id}",
        json={"lineas": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    # Y la entrega sigue con su linea, no se quedo a medias.
    db.refresh(e, ["lineas"])
    assert len(e.lineas) == 1


def test_editar_sin_mandar_lineas_sigue_permitido(client, db):
    """`None` es "no toques las líneas" y tiene que seguir pasando: un PUT que
    solo corrige la fecha es el caso más común de esta pantalla."""
    token = _token(client, db)
    _, e = _entrega_con(db, [("Pan", 3, 1000)], estado="pendiente")
    db.commit()
    otra = (HOY.toordinal() + 2)

    res = client.put(
        f"/api/entregas-b2b/{e.id}",
        json={"fecha_entrega": date.fromordinal(otra).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    db.refresh(e, ["lineas"])
    assert len(e.lineas) == 1
