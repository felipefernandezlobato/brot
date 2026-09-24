"""One-off: poner el PVP a las lineas de entrega B2B que se guardaron con precio 0.

El formulario de Nueva Entrega deja guardar una linea sin precio y no avisa, asi
que 160 de las 232 lineas entregadas (4.032 de 6.000 unidades, del 15/08 al
20/09) tienen `precio_unitario = 0`. No son regalos: son dias enteros cargados
sin precios -- el 15/08, 19/08, 22/08, 05/09, 09/09, 12/09, 15/09 y 20/09 estan
a cero de punta a punta, mientras el 26/08, 27/08, 29/08 y 03/09 estan completos.

Eso hacia que cualquier informe de ventas leyera un tercio de la realidad: el mes
15/08-15/09 aparecia con $1.850.454 facturados cuando a PVP son $5.691.532, y
comparado contra el coste de materia prima daba un margen del 0,4% en vez del 68%
real.

Aplicar el precio de catalogo hacia atras es seguro porque no hubo cambios de
precio en el periodo: cada producto que SI tiene lineas valoradas usa un unico
precio en todas ellas, y coincide exactamente con su `ProductoCatalogo.precio`
(Croissant $1.541 en sus 8 lineas, Medialunas $1.129 en 4, etc.). No hay ninguna
linea con un precio distinto al de catalogo que pudiera indicar una tarifa
especial por cliente o una subida a mitad de periodo.

Solo toca `lineas_entrega_b2b.precio_unitario`. Ni el stock ni los movimientos se
rozan: el precio de una linea de venta no interviene en ningun descuento de
inventario.

"Pan lomo" es el unico producto sin precio en el catalogo (se creo sin `precio`,
el mismo hueco que su `receta_id`); se le pone el `precio_venta` de su receta
(46, $875) antes de valorar sus lineas.

Solo rellena lineas que valgan exactamente 0. Una linea con precio puesto no se
toca nunca, asi que es idempotente y no puede pisar un descuento real.

Sin flag hace dry run.

    DATABASE_URL=... python scripts/rellenar_precios_entregas_b2b.py
    DATABASE_URL=... python scripts/rellenar_precios_entregas_b2b.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (  # noqa: E402
    ClienteB2B,
    EntregaB2B,
    LineaEntregaB2B,
    ProductoCatalogo,
    Receta,
)
from app.database import SessionLocal  # noqa: E402

CATALOGO_PAN_LOMO = "Pan lomo"


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        # El unico producto entregado sin precio de catalogo.
        pan_lomo = (
            db.query(ProductoCatalogo)
            .filter(ProductoCatalogo.nombre == CATALOGO_PAN_LOMO)
            .first()
        )
        if pan_lomo and not pan_lomo.precio and pan_lomo.receta_id:
            receta = db.query(Receta).filter(Receta.id == pan_lomo.receta_id).first()
            if receta and receta.precio_venta:
                print(f"catalogo '{pan_lomo.nombre}': precio {pan_lomo.precio} -> "
                      f"{receta.precio_venta} (PVP de la receta {receta.id})")
                if apply:
                    pan_lomo.precio = receta.precio_venta
                    db.flush()

        lineas = (
            db.query(LineaEntregaB2B, EntregaB2B, ClienteB2B, ProductoCatalogo)
            .join(EntregaB2B, EntregaB2B.id == LineaEntregaB2B.entrega_id)
            .join(ClienteB2B, ClienteB2B.id == EntregaB2B.cliente_b2b_id)
            .join(ProductoCatalogo, ProductoCatalogo.id == LineaEntregaB2B.producto_id)
            .filter(LineaEntregaB2B.precio_unitario == 0)
            .order_by(EntregaB2B.fecha_entrega, EntregaB2B.id, LineaEntregaB2B.id)
            .all()
        )
        if not lineas:
            print("No hay lineas con precio 0. Nada que hacer.")
            return

        total = 0.0
        sin_precio = []
        por_cliente: dict[str, float] = {}
        for linea, entrega, cliente, producto in lineas:
            precio = producto.precio or 0.0
            if not precio:
                sin_precio.append((entrega.fecha_entrega, cliente.nombre,
                                   producto.nombre, linea.cantidad))
                continue
            importe = linea.cantidad * precio
            total += importe
            por_cliente[cliente.nombre] = por_cliente.get(cliente.nombre, 0.0) + importe
            if apply:
                linea.precio_unitario = precio

        print(f"\n{len(lineas) - len(sin_precio)} lineas a valorar:")
        for nombre, importe in sorted(por_cliente.items(), key=lambda kv: -kv[1]):
            print(f"  {nombre:<20} $ {importe:>14,.0f}")
        print(f"  {'TOTAL':<20} $ {total:>14,.0f}")

        if sin_precio:
            print("\nSin precio de catalogo, se quedan en 0:")
            for fecha, cliente, producto, cantidad in sin_precio:
                print(f"  {fecha} {cliente:<18} {producto:<20} {cantidad:>6.0f} u")

        if apply:
            db.commit()
            print("\nAplicado.")
        else:
            print("\nDry run -- usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
