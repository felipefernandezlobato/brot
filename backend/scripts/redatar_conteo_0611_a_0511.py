"""Re-fecha al 05/11 el inventario que se contó el 05/11 y se cargó el 06/11.

Mueve SOLO los conteos manuales. Quedan fuera, a proposito:
- Los lotes `StockCongelado` con `registro_produccion_id` (la salida de la
  produccion de hoy) y las filas `InventarioRegistro` con nota automatica (el
  consumo de hoy). Esos no son conteos: la produccion se hizo hoy de verdad, y
  los dos endpoints los rechazan igualmente con un 409.
- `cantidad` y `cantidad_original`: solo se manda `fecha`, asi que
  `update_stock_congelado` no toca `cantidad_original`. Importa porque tres
  lotes de conteo ya fueron consumidos hoy por FIFO (Masa Pan Blanco 0,5 de 2;
  Baston Croissant 4 de 7; Baston Medialuna 1 de 2) y reescribirles el original
  resucitaria stock ya gastado.

**El congelado no se mueve y la materia prima SI, y eso es lo correcto.** El
saldo de congelado es la suma de `cantidad` de los lotes activos, que no mira
fechas. Pero `get_saldos_materia_prima` superpone "un conteo de HOY manda sobre
el ledger" (existe para que contar-y-pedir el mismo dia no lea numeros que el
conteo acaba de reemplazar), y mientras el conteo estuviera fechado hoy ese
overlay devolvia el conteo crudo, **tapando lo que la produccion de hoy ya
habia gastado**: Harina 000 leia 980 cuando la cadena de `InventarioRegistro`
ya decia 957. Al pasar el conteo al 05, el ledger aplica encima el consumo del
06 y la lectura cae a 957. La primera version de este script abortaba por eso,
con un invariante equivocado.

Asi que la verificacion es: el congelado no se mueve (si se mueve, se
restaura), y la materia prima tiene que terminar coincidiendo con la punta de
la cadena de `InventarioRegistro`, que es una fuente independiente del ledger.

Lo otro que cambia, y es el objetivo, es el calculado:
`historial_movimientos_acumulado` re-ancla al dia SIGUIENTE del conteo, asi que
con el conteo en el 05 el calculado del 06 pasa a ser "lo contado + lo que se
movio hoy" en vez de arrastrar la trayectoria previa.

Va por los endpoints reales (`update_inventario` / `update_stock_congelado`),
no por SQL. Snapshot de las fechas originales a un JSON antes de escribir y
**restauracion automatica si algun saldo se mueve** (regla de CLAUDE.md tras el
incidente del 13/10). Dry-run por defecto; --apply para escribir.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Ingrediente,
    InventarioRegistro,
    ProductoCongelado,
    StockCongelado,
    User,
)
from app.routers.congelados import update_stock_congelado  # noqa: E402
from app.routers.inventario import update_inventario  # noqa: E402
from app.schemas import InventarioRegistroUpdate, StockCongeladoUpdate  # noqa: E402
from app.services.stock import (  # noqa: E402
    es_conteo_manual,
    get_saldos_congelado,
    get_saldos_materia_prima,
)

DESDE = date(2026, 11, 6)
HASTA = date(2026, 11, 5)
TOLERANCIA = 0.0001


def saldos(db):
    ids_mp = [i.id for i in db.query(Ingrediente).all()]
    return get_saldos_materia_prima(db, ids_mp), get_saldos_congelado(db)


def comparar(antes, despues, etiqueta, db, modelo, campo):
    movidos = []
    for key in set(antes) | set(despues):
        a, d = antes.get(key), despues.get(key)
        if a is None or d is None or abs(a - d) > TOLERANCIA:
            obj = db.get(modelo, key)
            movidos.append((getattr(obj, campo, key), a, d))
    if movidos:
        print(f"\n  !! {etiqueta}: {len(movidos)} saldo(s) se movieron")
        for nombre, a, d in movidos:
            print(f"     {nombre}: {a} -> {d}")
    return movidos


def punta_de_cadena(db, ingrediente_id):
    """Ultimo `InventarioRegistro` del ingrediente: el total absoluto que la
    propia tabla arrastra, independiente del ledger."""
    fila = (
        db.query(InventarioRegistro)
        .filter(InventarioRegistro.ingrediente_id == ingrediente_id)
        .order_by(InventarioRegistro.fecha_registro.desc(), InventarioRegistro.id.desc())
        .first()
    )
    return fila.cantidad if fila else None


# La suma del ledger y el total guardado difieren en centesimas por redondeo
# de floats (Sal: 2,03 contra 2,04). Un descuadre real es de otra magnitud.
TOLERANCIA_CADENA = 0.05


def verificar_materia_prima(db, despues, ids):
    """Cada saldo nuevo tiene que coincidir con la punta de la cadena.

    Solo los ingredientes que este script re-fecho: el chequeo global pescaba
    de paso descuadres viejos ajenos al cambio (Agua, que no tiene conteo y no
    se toco aca, da ledger -923,84 contra cadena -860,87) y abortaba por algo
    que este script no causo ni arregla.
    """
    malos = []
    for ing_id in ids:
        saldo = despues.get(ing_id)
        if saldo is None:
            continue
        tip = punta_de_cadena(db, ing_id)
        if tip is not None and abs(saldo - tip) > TOLERANCIA_CADENA:
            malos.append((db.get(Ingrediente, ing_id).nombre, saldo, tip))
    if malos:
        print(f"\n  !! {len(malos)} saldo(s) no coinciden con InventarioRegistro")
        for nombre, saldo, tip in malos:
            print(f"     {nombre}: ledger {saldo} vs cadena {tip}")
    return malos


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="escribir de verdad")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            print("No hay usuario admin")
            return 1

        mp = [
            r
            for r in db.query(InventarioRegistro)
            .filter(InventarioRegistro.fecha_registro == DESDE)
            .order_by(InventarioRegistro.id)
            .all()
            if es_conteo_manual("materia_prima", r.notas)
        ]
        cg = [
            l
            for l in db.query(StockCongelado)
            .filter(StockCongelado.fecha_entrada == DESDE)
            .order_by(StockCongelado.id)
            .all()
            if l.registro_produccion_id is None and es_conteo_manual("congelado", l.notas)
        ]
        print(f"Conteos manuales del {DESDE} -> {HASTA}:")
        print(f"  materia prima : {len(mp)} filas  (ids {mp[0].id}-{mp[-1].id})" if mp else "  materia prima : 0")
        print(f"  congelado     : {len(cg)} lotes  (ids {cg[0].id}-{cg[-1].id})" if cg else "  congelado     : 0")
        if not mp and not cg:
            print("Nada que hacer.")
            return 0

        snapshot = {
            "generado": datetime.now().isoformat(),
            "inventario": [{"id": r.id, "fecha_registro": r.fecha_registro.isoformat()} for r in mp],
            "congelado": [{"id": l.id, "fecha_entrada": l.fecha_entrada.isoformat()} for l in cg],
        }
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot_redatar_0611.json")

        if not args.apply:
            print("\n(dry run -- pasar --apply para escribir)")
            return 0

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        print(f"\nSnapshot de fechas originales: {ruta}")

        mp_antes, cg_antes = saldos(db)

        for r in mp:
            update_inventario(r.id, InventarioRegistroUpdate(fecha_registro=HASTA), user=admin, db=db)
        for l in cg:
            update_stock_congelado(l.id, StockCongeladoUpdate(fecha_entrada=HASTA), user=admin, db=db)
        print(f"Re-fechadas {len(mp)} filas de materia prima y {len(cg)} lotes de congelado")

        db.expire_all()
        mp_despues, cg_despues = saldos(db)

        # El congelado no puede moverse; la materia prima si, por el overlay
        # del conteo de hoy, y por eso se valida contra la cadena en su lugar.
        problemas = comparar(cg_antes, cg_despues, "congelado", db, ProductoCongelado, "nombre")
        problemas += verificar_materia_prima(db, mp_despues, {r.ingrediente_id for r in mp})

        bajadas = [
            (db.get(Ingrediente, k).nombre, mp_antes[k], mp_despues[k])
            for k in mp_antes
            if k in mp_despues and abs(mp_antes[k] - mp_despues[k]) > TOLERANCIA
        ]
        if bajadas:
            print(f"\n  {len(bajadas)} lectura(s) de materia prima ahora descuentan el consumo de hoy:")
            for nombre, a, d in sorted(bajadas):
                print(f"     {nombre:<20} {a:>9,.2f} -> {d:>9,.2f}   ({d - a:+,.2f})")

        if problemas:
            print("\n  RESTAURANDO las fechas originales (ningun saldo debia moverse)")
            for fila in snapshot["inventario"]:
                db.get(InventarioRegistro, fila["id"]).fecha_registro = date.fromisoformat(fila["fecha_registro"])
            for fila in snapshot["congelado"]:
                db.get(StockCongelado, fila["id"]).fecha_entrada = date.fromisoformat(fila["fecha_entrada"])
            db.commit()
            print("  restaurado, no quedo ningun cambio aplicado")
            return 1

        print("Verificado: el congelado no se movio y la materia prima coincide con la cadena.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
