"""El pedido 20 de Creme pidio 'Pan NY' donde queria 'Pan 1kg Blanco'.

Pedido del portal #20 (Creme, entrega 07/11/2026), cargado el 06/11 a las
00:21. Felipe avisa que el cliente se confundio de producto: la linea 141 dice
Pan NY x1 ($1.550) y tiene que decir Pan 1kg Blanco x1 ($1.590). Encaja con el
historial -- las 8 entregas anteriores de Creme llevan Pan 1kg Blanco y ninguna
lleva Pan NY nunca.

**Por que es SQL y no un endpoint, que es la excepcion a justificar.** Un
pedido del portal no tiene forma de editar sus lineas: `pedidos_clientes.py`
expone POST / GET, y `pedidos_clientes_admin.py` + `entregas_b2b.py` solo
`PUT /{id}/estado` y `DELETE`. Es la misma laguna que CLAUDE.md ya anota para
la FECHA de un pedido del portal (se ofrecio construir el endpoint el 29/09 y
Felipe lo descarto, "no se hara a menudo"). El camino alternativo seria borrar
y recrear, y es peor: cambia el id, pierde `fecha_pedido` y vuelve a disparar
el aviso por correo al panadero.

**No toca el ledger, y eso esta medido, no supuesto.** El pedido esta en
`pendiente`, asi que `_aplicar_pedido_portal` nunca corrio: hay 0 filas en
`movimientos_stock` con referencia `pedido_portal:20:%`. La regla de CLAUDE.md
de no editar a mano es sobre `MovimientoStock`/`StockCongelado` -- aca no hay
ninguno que editar. `costo_unitario_snapshot` se queda en NULL: lo congela
`_snapshot_costos` cuando la entrega pase a `entregado`, y a esa altura ya
leera la receta correcta.

Los importes se recalculan leyendo `ProductoCatalogo.precio` igual que
`create_pedido` (`subtotal = round(cantidad * precio, 2)`, total = suma
redondeada), en vez de escribir 1590 a mano, para que no haya una segunda
definicion del precio de una linea.

Aborta sin escribir si cualquier premisa falla: que el pedido siga en
`pendiente`, que no tenga movimientos, y que la linea siga siendo Pan NY (si
alguien ya la corrigio a mano, no hay nada que hacer).

Dry-run por defecto; --apply para escribir.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    LineaPedidoCliente,
    MovimientoStock,
    PedidoCliente,
    ProductoCatalogo,
)

PEDIDO_ID = 20
LINEA_ID = 141
PRODUCTO_MAL = 11  # Pan NY
PRODUCTO_BIEN = 14  # Pan 1kg Blanco


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="escribir los cambios")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        pedido = db.get(PedidoCliente, PEDIDO_ID)
        if pedido is None:
            print(f"ABORTA: no existe el pedido {PEDIDO_ID}")
            return 1
        if pedido.estado != "pendiente":
            print(f"ABORTA: el pedido {PEDIDO_ID} esta en '{pedido.estado}', no en 'pendiente'.")
            print("  Si ya se entrego, dedujo stock y hay que revertir antes de tocar las lineas.")
            return 1

        movs = (
            db.query(func.count(MovimientoStock.id))
            .filter(MovimientoStock.referencia_origen.like(f"pedido_portal:{PEDIDO_ID}:%"))
            .scalar()
        )
        if movs:
            print(f"ABORTA: el pedido {PEDIDO_ID} tiene {movs} movimiento(s) de stock.")
            return 1

        linea = db.get(LineaPedidoCliente, LINEA_ID)
        if linea is None or linea.pedido_cliente_id != PEDIDO_ID:
            print(f"ABORTA: la linea {LINEA_ID} no existe o no es del pedido {PEDIDO_ID}")
            return 1
        if linea.producto_id != PRODUCTO_MAL:
            actual = db.get(ProductoCatalogo, linea.producto_id)
            print(f"ABORTA: la linea {LINEA_ID} ya no es Pan NY, es '{actual.nombre if actual else linea.producto_id}'.")
            return 1

        nuevo = db.get(ProductoCatalogo, PRODUCTO_BIEN)
        if nuevo is None or not nuevo.disponible:
            print(f"ABORTA: el producto {PRODUCTO_BIEN} no existe o no esta disponible")
            return 1

        viejo = db.get(ProductoCatalogo, PRODUCTO_MAL)
        subtotal_nuevo = round(linea.cantidad * nuevo.precio, 2)

        print(f"Pedido {PEDIDO_ID} - Creme - entrega {pedido.fecha_entrega} ({pedido.estado})")
        print(f"  linea {LINEA_ID}: '{viejo.nombre}' -> '{nuevo.nombre}'")
        print(f"     cantidad          {linea.cantidad:g} (sin cambios)")
        print(f"     precio unitario   {linea.precio_unitario_snapshot:>10,.2f} -> {nuevo.precio:>10,.2f}")
        print(f"     subtotal          {linea.subtotal:>10,.2f} -> {subtotal_nuevo:>10,.2f}")

        otras = (
            db.query(func.coalesce(func.sum(LineaPedidoCliente.subtotal), 0.0))
            .filter(
                LineaPedidoCliente.pedido_cliente_id == PEDIDO_ID,
                LineaPedidoCliente.id != LINEA_ID,
            )
            .scalar()
        )
        total_nuevo = round(otras + subtotal_nuevo, 2)
        print(f"  total del pedido     {pedido.total:>10,.2f} -> {total_nuevo:>10,.2f}")

        if not args.apply:
            print("\nDRY-RUN: no se escribio nada. Repetir con --apply.")
            return 0

        linea.producto_id = PRODUCTO_BIEN
        linea.precio_unitario_snapshot = nuevo.precio
        linea.subtotal = subtotal_nuevo
        pedido.total = total_nuevo
        db.commit()

        db.refresh(pedido)
        db.refresh(linea)
        print("\nAplicado. Estado final:")
        for l in sorted(pedido.lineas, key=lambda x: x.id):
            p = db.get(ProductoCatalogo, l.producto_id)
            print(f"  {l.id}  {p.nombre:<22} x{l.cantidad:g}  @{l.precio_unitario_snapshot:>9,.2f}  = {l.subtotal:>10,.2f}")
        print(f"  total {pedido.total:,.2f}   estado {pedido.estado}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
