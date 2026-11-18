"""One-off: cargar el conteo semanal del 2026-11-12, que llego seis dias tarde.

Felipe lo paso por WhatsApp el 17/11. Es el conteo del miercoles de siempre
(la serie va 24/09, 01/10, 08/10, 15/10, 22/10, 29/10, 05/11 y faltaba el
12/11), pero entre el 12 y hoy hay SEIS dias de produccion y entregas ya
cargados, y eso cambia por completo que se puede escribir y que no.

LO QUE DICE EL CONTEO
---------------------
Casi nada, y eso es la noticia buena: el calculado del ledger al 12/11
coincide al dedillo con lo contado en 44 de los 47 congelados y en 22 de 22
ingredientes salvo centesimas. Las unicas diferencias reales son
Cinnamon Roll Cocinado 18 contra 44 (faltan 26), Medialunas -1,
Pan de Choco -1, Harina Salvado -2,2 kg, Harina Integral +1 kg y Sal -0,49 kg.

MATERIA PRIMA: se carga normal, fechada el 12/11
------------------------------------------------
Via `create_inventario` (`POST /api/inventario`), que es lo que manda la
pantalla Registrar. Un `InventarioRegistro` backdateado es inofensivo:
`get_saldo_materia_prima` (el camino de escritura) se queda con la fila de
`fecha_registro` mas alta, y para casi todos los ingredientes ya hay filas del
13 al 17, asi que el conteo no pasa a ser la punta de la cadena. Y
`get_saldos_materia_prima` (la lectura) va por el ledger, que re-ancla al dia
SIGUIENTE del conteo: el stock de hoy pasa a ser "lo contado + lo que se movio
desde el 13". No hay lotes, asi que no hay nada que inflar.

CONGELADO: NO se puede cargar fechado el 12/11 como un lote normal
------------------------------------------------------------------
Medido con una simulacion con rollback antes de escribir nada: cargarlo por
`add_stock_congelado` **infla la estanteria en 874 unidades** -- Medialunas
254 -> 524, Croissant 193 -> 383, Ensaimada Amasada 91 -> 159.

El motivo: `reconciliar_lotes_tras_conteo` barre los lotes anteriores al
conteo, pero lo consumido entre el 13 y el 17 ya se saco por FIFO de esos
mismos lotes viejos. Al barrerlos y poner el conteo entero encima, ese consumo
desaparece de la estanteria aunque siga en el ledger. Es la cara opuesta del
incidente del 13/10 que CLAUDE.md documenta ("NUNCA reaplicar produccion
historica si ya existe un conteo posterior"), y se arregla igual de mal: solo
contando otra vez.

Asi que el conteo de congelado se escribe como REGISTRO, no como lote:
`cantidad=0`, `cantidad_original=lo contado`, `is_active=False`. Esa no es una
forma nueva -- es exactamente la forma que tienen HOY las 47 filas del conteo
del 05/11, porque un lote de conteo termina en 0 e inactivo en cuanto el FIFO
se lo come. Lo unico distinto es que este nace asi, que es la verdad: su stock
lleva seis dias consumido.

Lo que eso logra, y es todo lo que un conteo de hace seis dias puede lograr:
- queda en el historial, con su (contado) en el pivot del 12/11;
- `conteos_manuales_por_fecha` NO filtra por `is_active`, asi que el calculado
  re-ancla igual al dia siguiente -- Cinnamon Roll pasa a -47 contra una
  estanteria de -21, o sea que los 26 que faltan quedan a la vista en vez de
  perderse;
- la estanteria fisica no se mueve ni un gramo. Re-anclarla es lo que hace el
  conteo del miercoles que viene, que es el mecanismo que existe para eso.

    DATABASE_URL=... python scripts/cargar_conteo_1211.py --parte mp
    DATABASE_URL=... python scripts/cargar_conteo_1211.py --parte mp --apply
    DATABASE_URL=... python scripts/cargar_conteo_1211.py --parte congelado --apply
"""

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Ingrediente,
    InventarioRegistro,
    MovimientoStock,
    ProductoCongelado,
    StockCongelado,
    User,
)
from app.routers.inventario import create_inventario  # noqa: E402
from app.schemas import InventarioRegistroCreate  # noqa: E402
from app.services.stock import (  # noqa: E402
    es_conteo_manual,
    get_saldos_congelado,
    get_saldos_materia_prima,
)

FECHA = date(2026, 11, 12)

# Tal cual lo paso Felipe. Clave = nombre exacto del Ingrediente.
MATERIA_PRIMA = {
    "Harina 000": 851.0,
    "Harina 0000": 206.3,
    "Harina 00 Pizza": 598.0,
    "Harina Integral": 52.0,
    "Harina Salvado": 37.8,
    "Semolín": 246.7,
    "Levadura": 7.2,
    "Azúcar": 33.8,
    "Sal": 24.7,
    "Huevos": 3.8,
    "Manteca": 7.5,
    "Miel": 0.25,
    "Vinagre Blanco": 0.4,
    "Aceite Girasol": 1.2,
    "Aceite Oliva": 2.3,
    "Crema Pastelera": 0.15,   # "PASTELERA"
    "Chocolate": 5.6,
    "Grasa de Cerdo": 0.8,
    "Leche": 12.5,
    "Canela": 0.18,
    "Tomate": 2.0,
    "Papa Deshidratada": 0.0,  # "PURE DESHIDRATADO"
}

# Clave = nombre exacto del ProductoCongelado. Lo que Felipe no nombro va en 0
# (misma regla que el conteo del 15/10: "lo que no hay es todo 0").
CONGELADO = {
    "Medialunas Cocinado": 329.0,
    "Croissant Cocinado": 229.0,
    "Cinnamon Roll Cocinado": 18.0,       # "Cinamon roll"
    "Pan Suizo Cocinado": 37.0,           # "Pan suisse"
    "Ensaimadas Cocinado": 7.0,
    "Cruffin Cocinado": 20.0,
    "Moño Cocinado": 55.0,
    "Pan de Choco Cocinado": 26.0,
    "Palmerita Cocinado": 83.0,
    "Sacramento Cocinado": 6.0,
    "Pan NY Cocinado": 9.0,
    "Banda Cocinado": 7.0,
    "Cremadet Cocinado": 37.0,
    "Pan 1kg Blanco Cocinado": 11.0,
    "Pan 500g Blanco Cocinado": 22.0,
    "Pan 1kg Integral Cocinado": 4.0,
    "Pan 500g Integral Cocinado": 21.0,
    "Barra Blanca Cocinado": 45.0,
    "Barra Negra Cocinado": 18.0,         # "Barra negra"
    "Pizza Cocinado": 5.0,
    "Pan Lomo Cocinado": 18.0,
    "Focaccia Cocinado": 0.0,
    # semi elaborados
    "Manteca Laminado": 4.0,              # "Manteca para laminar"
    "Baston Croissant": 4.0,
    "Baston Medialuna": 3.0,
    "Baston Cinnamon Roll": 1.0,
    "Baston Hojaldre": 2.0,
    "Ensaimada Amasada": 159.0,
    "Masa Pan Blanco": 2.0,               # "2 masas pan blanco"
}


def delta_desde_corte(db, tipo_stock):
    """Movimiento neto por producto DESPUES del 12/11, segun el ledger."""
    out = defaultdict(float)
    for m in (
        db.query(MovimientoStock)
        .filter(MovimientoStock.tipo_stock == tipo_stock, MovimientoStock.fecha > FECHA)
        .all()
    ):
        out[m.referencia_producto_id] += m.cantidad
    return out


# ----------------------------------------------------------------- materia prima
def cargar_materia_prima(db, aplicar):
    ings = {i.nombre: i for i in db.query(Ingrediente).all()}
    faltan = [n for n in MATERIA_PRIMA if n not in ings]
    if faltan:
        print(f"  ABORTADO: ingredientes que no existen: {faltan}")
        return False

    ya = [
        r
        for r in db.query(InventarioRegistro)
        .filter(InventarioRegistro.fecha_registro == FECHA)
        .all()
        if es_conteo_manual("materia_prima", r.notas)
    ]
    if ya:
        print(f"  ABORTADO: ya hay {len(ya)} conteos manuales de materia prima el {FECHA}.")
        return False

    ids = [i.id for i in ings.values()]
    antes = get_saldos_materia_prima(db, ids)
    delta = delta_desde_corte(db, "materia_prima")

    print(f"{'APLICANDO' if aplicar else 'DRY RUN'} -- materia prima, conteo del {FECHA}")
    print(f"  {'ingrediente':24} {'contado':>9} {'stock hoy':>10} {'quedara':>10}")
    esperado = {}
    for nombre, cant in MATERIA_PRIMA.items():
        ing = ings[nombre]
        esperado[ing.id] = cant + delta[ing.id]
        print(
            f"  {nombre:24} {cant:>9.2f} {antes.get(ing.id, 0.0):>10.2f} "
            f"{esperado[ing.id]:>10.2f}"
        )

    if not aplicar:
        print("\n  dry run: no se escribio nada. Agregar --apply.")
        return True

    admin = db.query(User).filter(User.role == "admin").first()
    create_inventario(
        [
            InventarioRegistroCreate(
                ingrediente_id=ings[n].id,
                cantidad=c,
                unidad=ings[n].unidad_uso,
                fecha_registro=FECHA,
            )
            for n, c in MATERIA_PRIMA.items()
        ],
        user=admin,
        db=db,
    )

    despues = get_saldos_materia_prima(db, ids)
    malos = [
        (n, despues.get(ings[n].id), esperado[ings[n].id])
        for n in MATERIA_PRIMA
        if abs((despues.get(ings[n].id) or 0.0) - esperado[ings[n].id]) > 0.05
    ]
    print(f"\n  {len(MATERIA_PRIMA)} conteos cargados.")
    if malos:
        print("  OJO, estos no quedaron donde se predijo:")
        for n, real, esp in malos:
            print(f"    {n:24} real {real} esperado {esp:.2f}")
        return False
    print("  todos los saldos quedaron exactamente en lo predicho (contado + movimientos desde el 13).")
    return True


# -------------------------------------------------------------------- congelado
def cargar_congelado(db, aplicar):
    """Escribe el conteo como REGISTRO historico, sin tocar la estanteria.

    Ver el docstring del modulo: cargarlo como lote activo infla 874 unidades
    y no hay forma de deshacerlo salvo contando de nuevo.
    """
    prods = db.query(ProductoCongelado).filter(ProductoCongelado.is_active.is_(True)).all()
    por_nombre = {p.nombre: p for p in prods}
    faltan = [n for n in CONGELADO if n not in por_nombre]
    if faltan:
        print(f"  ABORTADO: productos que no existen: {faltan}")
        return False

    ya = [
        l
        for l in db.query(StockCongelado).filter(StockCongelado.fecha_entrada == FECHA).all()
        if l.registro_produccion_id is None and es_conteo_manual("congelado", l.notas)
    ]
    if ya:
        print(f"  ABORTADO: ya hay {len(ya)} conteos de congelado el {FECHA}.")
        return False

    ids = [p.id for p in prods]
    antes = get_saldos_congelado(db, ids)
    delta = delta_desde_corte(db, "congelado")

    print(f"{'APLICANDO' if aplicar else 'DRY RUN'} -- congelado, conteo del {FECHA}")
    print(f"  {len(prods)} productos: {len(CONGELADO)} contados, {len(prods)-len(CONGELADO)} en 0")
    print(f"\n  {'producto':28} {'contado':>8} {'estanteria hoy':>15} {'calculado quedara':>18}")
    for p in sorted(prods, key=lambda x: (x.nivel, x.nombre)):
        cant = CONGELADO.get(p.nombre, 0.0)
        print(f"  {p.nombre:28} {cant:>8.0f} {antes.get(p.id, 0.0):>15.2f} {cant + delta[p.id]:>18.2f}")

    if not aplicar:
        print("\n  dry run: no se escribio nada. Agregar --apply.")
        return True

    for p in sorted(prods, key=lambda x: x.nombre):
        db.add(
            StockCongelado(
                producto_congelado_id=p.id,
                cantidad=0.0,
                cantidad_original=float(CONGELADO.get(p.nombre, 0.0)),
                fecha_entrada=FECHA,
                is_active=False,
            )
        )
    db.flush()

    despues = get_saldos_congelado(db, ids)
    movidos = [
        (p.nombre, antes.get(p.id, 0.0), despues.get(p.id, 0.0))
        for p in prods
        if abs(despues.get(p.id, 0.0) - antes.get(p.id, 0.0)) > 0.005
    ]
    if movidos:
        db.rollback()
        print("\n  ROLLBACK: la estanteria se movio y no debia moverse:")
        for n, a, d in movidos:
            print(f"    {n:28} {a:.2f} -> {d:.2f}")
        return False

    db.commit()
    print(f"\n  {len(prods)} conteos registrados. La estanteria no se movio en ningun producto.")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parte", choices=["mp", "congelado", "todo"], default="todo")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        ok = True
        if args.parte in ("mp", "todo"):
            ok = cargar_materia_prima(db, args.apply) and ok
            print()
        if args.parte in ("congelado", "todo"):
            ok = cargar_congelado(db, args.apply) and ok
        sys.exit(0 if ok else 1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
