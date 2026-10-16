"""One-off: la cadena de la Ensaimada estaba mal nombrada y mal costeada.

EL PROBLEMA
-----------
Felipe vio en Escandallos "Ensaimada Cruda" a 202,20 y "Ensaimadas" a 181,00 y
pregunto por que. La diferencia son los 4 g de Grasa de Cerdo (5.300/kg =
21,20) que lleva la armada y no la masa: 181,00 + 21,20 = 202,20. No era un
error, pero destapo dos que si lo son.

1. **La receta llamada "Ensaimadas" es en realidad la masa.** Su
   ProductoCongelado es "Ensaimada Amasada" (nivel semi). Buscar "Ensaimadas"
   en Escandallos devolvia la masa. Es el mismo problema que CLAUDE.md ya
   documenta para Pizza/Focaccia ("Recipe names follow the product"), con esta
   cadena quedandose fuera de aquel renombrado.

2. **El catalogo cobraba contra el costo de la masa.** `ProductoCatalogo`
   "Ensaimadas" ($540) apuntaba a la Receta 17, asi que su costo y su
   multiplicador salian de 181,00 en vez de los 202,20 reales: 2,98x aparente
   contra 2,67x real. Con la politica de x3 el precio deberia ser 610.

NO era un problema: que "Ensaimadas Cocinado" no tenga receta propia es
deliberado (hornear no agrega ingredientes) y `deducir_congelado_por_catalogo`
ya lo contempla -- su comentario nombra esta cadena explicitamente y usa
`_unico_terminado_descendiente` para bajar hasta el terminado. El stock
siempre se descontó bien.

EL ARREGLO
----------
  * Receta 17 -> "Ensaimada Amasada" (el nombre de su propio producto),
    es_subreceta=True y sin precio_venta: es una etapa, no algo que se vende.
  * Receta 43 "Ensaimada Cruda" -> "Ensaimadas", es_subreceta=False,
    precio_venta=610. Es la ultima receta de la cadena y la unica que lleva el
    costo completo.
  * El catalogo pasa a apuntar a la Receta 43 y su precio a 610.

**El descuento de stock sigue cayendo en el terminado**: verificado antes de
aplicar, `_unico_terminado_descendiente` llega a "Ensaimadas Cocinado" tanto
desde la amasada como desde la cruda. Y la 43 no la usa nadie como subreceta ni
tenia item de catalogo, asi que reutilizarla es seguro.

`ProductoCatalogo.receta_id` no esta expuesto en su schema de Update (gotcha ya
documentado en CLAUDE.md), asi que ese campo se escribe sobre el modelo. Es
dato de catalogo, no del ledger.

LOS COSTOS YA CONGELADOS
------------------------
`scripts/cambiar_harinas_masas_2026_10.py` congelo ayer el costo de 19 lineas
de venta de Ensaimadas, y lo hizo resolviendo por la Receta 17: quedaron en
171,25 y 181,00, sin la grasa. Se limpian y se vuelven a congelar con la
cadena ya corregida, a la fecha de cada venta. Son las unicas lineas que se
tocan, y el motivo es que las congelo mal este mismo script hace un dia.

    DATABASE_URL=... python scripts/arreglar_cadena_ensaimada.py           # dry run
    DATABASE_URL=... python scripts/arreglar_cadena_ensaimada.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    EntregaB2B,
    LineaEntregaB2B,
    LineaPedidoCliente,
    PedidoCliente,
    ProductoCatalogo,
    ProductoCongelado,
    Receta,
    User,
)
from app.routers.catalogo_admin import update_producto  # noqa: E402
from app.routers.entregas_b2b import _snapshot_costos  # noqa: E402
from app.routers.recetas import update_receta  # noqa: E402
from app.schemas import ProductoCatalogoUpdate, RecetaUpdate  # noqa: E402
from app.services.costes import costo_receta  # noqa: E402
from app.services.stock import _unico_terminado_descendiente  # noqa: E402

R_MASA = 17       # "Ensaimadas" -> pasa a "Ensaimada Amasada"
R_PRODUCTO = 43   # "Ensaimada Cruda" -> pasa a "Ensaimadas"
MULTIPLICADOR = 3.0


def redondear_a_diez(x: float) -> int:
    return int(round(x / 10.0) * 10)


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        masa = db.get(Receta, R_MASA)
        producto = db.get(Receta, R_PRODUCTO)
        cat = db.query(ProductoCatalogo).filter(ProductoCatalogo.receta_id == R_MASA).first()
        if not (admin and masa and producto and cat):
            print("  ABORTADO: falta alguna de las piezas esperadas.")
            return

        costo = costo_receta(producto, db)[1]
        nuevo_precio = redondear_a_diez(costo * MULTIPLICADOR)

        print(f"{'APLICANDO' if aplicar else 'DRY RUN'}\n")
        print(f"  Receta {masa.id}  '{masa.nombre}' -> 'Ensaimada Amasada'"
              f"  (es_subreceta {masa.es_subreceta} -> True, precio {masa.precio_venta} -> None)")
        print(f"  Receta {producto.id}  '{producto.nombre}' -> 'Ensaimadas'"
              f"  (es_subreceta {producto.es_subreceta} -> False, precio {producto.precio_venta} -> {nuevo_precio})")
        print(f"  Catalogo {cat.id} '{cat.nombre}': receta {cat.receta_id} -> {R_PRODUCTO},"
              f" precio {cat.precio:g} -> {nuevo_precio}")
        print(f"\n  costo real por unidad {costo:.2f} x{MULTIPLICADOR:g} = {costo*MULTIPLICADOR:.2f} -> {nuevo_precio}")

        lineas_b2b = db.query(LineaEntregaB2B).filter(LineaEntregaB2B.producto_id == cat.id).all()
        lineas_portal = db.query(LineaPedidoCliente).filter(LineaPedidoCliente.producto_id == cat.id).all()
        congeladas = [l for l in lineas_b2b + lineas_portal if l.costo_unitario_snapshot is not None]
        print(f"\n  costos congelados a recalcular: {len(congeladas)}"
              f"  (valores actuales {sorted({round(l.costo_unitario_snapshot, 2) for l in congeladas})})")

        if not aplicar:
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        update_receta(masa.id, RecetaUpdate(
            nombre="Ensaimada Amasada", es_subreceta=True, precio_venta=None), user=admin, db=db)
        update_receta(producto.id, RecetaUpdate(
            nombre="Ensaimadas", es_subreceta=False, precio_venta=float(nuevo_precio)), user=admin, db=db)

        # receta_id no esta en ProductoCatalogoUpdate (gotcha de CLAUDE.md).
        cat.receta_id = R_PRODUCTO
        db.flush()
        update_producto(cat.id, ProductoCatalogoUpdate(precio=float(nuevo_precio)), db=db, admin=admin)

        for l in congeladas:
            l.costo_unitario_snapshot = None
        db.flush()
        for e in db.query(EntregaB2B).filter(EntregaB2B.estado == "entregado").all():
            _snapshot_costos(db, [l for l in e.lineas if l.producto_id == cat.id], e.fecha_entrega)
        for p in db.query(PedidoCliente).filter(PedidoCliente.estado == "entregado").all():
            _snapshot_costos(db, [l for l in p.lineas if l.producto_id == cat.id], p.fecha_entrega)
        db.commit()

        rehechas = [l.costo_unitario_snapshot for l in
                    db.query(LineaEntregaB2B).filter(LineaEntregaB2B.producto_id == cat.id).all()
                    + db.query(LineaPedidoCliente).filter(LineaPedidoCliente.producto_id == cat.id).all()
                    if l.costo_unitario_snapshot is not None]
        print(f"\n  listo. costos recongelados: {len(rehechas)}"
              f"  valores {sorted({round(v, 2) for v in rehechas})}")
        db.refresh(cat)
        print(f"  catalogo '{cat.nombre}' -> receta {cat.receta_id}, precio {cat.precio:g}")
        origen = db.query(ProductoCongelado).filter(
            ProductoCongelado.receta_id == R_PRODUCTO).first()
        destino = _unico_terminado_descendiente(db, origen) if origen else None
        print(f"  el stock se descuenta de: {destino.nombre if destino else 'NO RESUELVE -- revisar'}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
