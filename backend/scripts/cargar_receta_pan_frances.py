"""One-off: cargar la receta del Pan Frances (el "pan bollito") y renombrar
la receta 49, que existia vacia como marcador desde el 2026-09-30.

Felipe la paso el 18/11 en porcentajes de panadero sobre 1 kg de harina:
agua 50%, sal 2,5%, azucar 1%, levadura 1%, aceite 2%. El aceite es Girasol
(el de las cuatro masas de pan y las dos de barra), confirmado por el.

QUE SE ESCRIBE
--------------
1. Receta nueva **"Masa de Pan Frances"**: el lote con sus seis lineas,
   `porciones_por_lote=1`, `unidad_rendimiento="u"`, categoria Panes.
2. La 49 pasa de "Pan Bollito" a **"Pan Frances"**, que es el nombre que
   quiere Felipe, y se le deja en `notas` que falta el rinde.

EL RINDE NO SE SABE TODAVIA, Y POR ESO LA 49 QUEDA SIN LINEA
------------------------------------------------------------
Nunca lo hornearon, asi que no hay cuantos panes salen de un lote. El lote da
1.565 g de masa y cuesta 981,33, o sea que el costo por pan depende entero de
ese numero (a 65 g son 24 panes y 40,76 c/u; a 100 g son 16 y 62,70).

Darle igual la linea de subreceta a la 49 con `porciones_por_lote=1` seria
peor que dejarla vacia: Escandallos mostraria "un Pan Frances cuesta 981,33",
que es el precio del LOTE. Asi que la 49 se queda sin linea hasta el primer
horneado; entonces es un solo PUT con porciones + linea + PVP.

POR QUE LA MASA SI VA MARCADA `es_subreceta=True`
--------------------------------------------------
CLAUDE.md anota como defecto que Masa Barra Blanca/Integral, Masa de Pan Lomo
y Masa de Pizza NO estan marcadas, y por eso aparecen en la lista de
Escandallos como si fueran vendibles. Esta nace bien marcada.

LAS UNIDADES NO SON LAS DEL PAPEL, Y ES OBLIGATORIO
----------------------------------------------------
`convertir()` revienta si la linea usa una familia distinta (peso vs volumen)
de la `unidad_uso` del ingrediente, y revienta recien al producir, no al
guardar. Agua y Aceite Girasol se stockean en litros, asi que los "500 gr" y
los "20" del mensaje van como 0,5 y 0,02 litro. Solidos en g, igual que todas
las demas masas.

    DATABASE_URL=... python scripts/cargar_receta_pan_frances.py
    DATABASE_URL=... python scripts/cargar_receta_pan_frances.py --apply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Ingrediente, Receta, User  # noqa: E402
from app.routers.recetas import create_receta, update_receta  # noqa: E402
from app.schemas import LineaRecetaIn, RecetaCreate, RecetaUpdate  # noqa: E402
from app.services.costes import costo_receta  # noqa: E402

CATEGORIA_PANES = 1
RECETA_MARCADOR = 49          # "Pan Bollito", creada vacia el 2026-09-30
NOMBRE_MASA = "Masa de Pan Francés"
NOMBRE_PRODUCTO = "Pan Francés"

# (nombre del ingrediente, cantidad, unidad de la linea)
LINEAS = [
    ("Harina 000", 1000.0, "g"),
    ("Agua", 0.5, "litro"),          # "500 gr" -> el agua se stockea en litros
    ("Sal", 25.0, "g"),
    ("Azúcar", 10.0, "g"),
    ("Levadura", 10.0, "g"),
    ("Aceite Girasol", 0.02, "litro"),  # "20" g -> se stockea en litros
]

COSTO_ESPERADO = 981.33  # verificado antes de escribir; tolerancia 0,50


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print("  ABORTADO: no hay usuario admin.")
            sys.exit(1)

        ings = {i.nombre: i for i in db.query(Ingrediente).all()}
        faltan = [n for n, _, _ in LINEAS if n not in ings]
        if faltan:
            print(f"  ABORTADO: ingredientes que no existen: {faltan}")
            sys.exit(1)

        if db.query(Receta).filter(Receta.nombre == NOMBRE_MASA).first():
            print(f"  ABORTADO: ya existe una receta '{NOMBRE_MASA}'.")
            sys.exit(1)

        marcador = db.query(Receta).filter(Receta.id == RECETA_MARCADOR).first()
        if not marcador:
            print(f"  ABORTADO: no existe la receta {RECETA_MARCADOR}.")
            sys.exit(1)
        if marcador.lineas:
            print(f"  ABORTADO: la receta {RECETA_MARCADOR} ya tiene lineas, revisar a mano.")
            sys.exit(1)

        print(f"{'APLICANDO' if args.apply else 'DRY RUN'}")
        print(f"\n  nueva receta '{NOMBRE_MASA}' (subreceta, 1 lote, categoria Panes):")
        for nombre, cant, unidad in LINEAS:
            print(f"    {nombre:18} {cant:>8} {unidad}")
        print(f"\n  receta {RECETA_MARCADOR}: '{marcador.nombre}' -> '{NOMBRE_PRODUCTO}'")
        print("    (sin linea todavia: falta el rinde, ver el docstring)")

        if not args.apply:
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        creada = create_receta(
            RecetaCreate(
                nombre=NOMBRE_MASA,
                categoria_id=CATEGORIA_PANES,
                porciones_por_lote=1,
                unidad_rendimiento="u",
                es_subreceta=True,
                precio_venta=None,
                notas=(
                    "Formula sobre 1 kg de harina (agua 50%, sal 2,5%, azucar 1%, "
                    "levadura 1%, aceite 2%). El amasado real es mayor: se cargan "
                    "tantos lotes como kilos de harina."
                ),
                lineas=[
                    LineaRecetaIn(ingrediente_id=ings[n].id, cantidad=c, unidad=u)
                    for n, c, u in LINEAS
                ],
            ),
            user=admin, db=db,
        )
        rec_masa = db.query(Receta).filter(Receta.id == creada["id"]).first()

        update_receta(
            RECETA_MARCADOR,
            RecetaUpdate(
                nombre=NOMBRE_PRODUCTO,
                notas=(
                    "Falta el rinde: nunca se horneo, no se sabe cuantos panes salen "
                    f"de un lote. Hasta saberlo queda sin linea -- la masa esta en "
                    f"'{NOMBRE_MASA}'. Cuando se sepa: porciones_por_lote = los panes "
                    "por lote, una linea de 1 u de esa masa, y PVP = costo/u x3 "
                    "redondeado a 10. OJO: los precios de competencia guardados aca "
                    "son POR KILO de masa, no por unidad."
                ),
            ),
            user=admin, db=db,
        )

        # --- verificacion ---
        db.refresh(rec_masa, ["lineas"])
        total, por_porcion = costo_receta(rec_masa, db)
        marcador = db.query(Receta).filter(Receta.id == RECETA_MARCADOR).first()

        problemas = []
        if len(rec_masa.lineas) != len(LINEAS):
            problemas.append(f"la masa quedo con {len(rec_masa.lineas)} lineas y no {len(LINEAS)}")
        if abs(total - COSTO_ESPERADO) > 0.50:
            problemas.append(f"el lote costo {total:.2f} y se esperaba {COSTO_ESPERADO:.2f}")
        if not rec_masa.es_subreceta:
            problemas.append("la masa no quedo marcada como subreceta")
        if marcador.nombre != NOMBRE_PRODUCTO:
            problemas.append(f"la {RECETA_MARCADOR} se llama '{marcador.nombre}'")

        print(f"\n  receta {rec_masa.id} '{rec_masa.nombre}' creada con "
              f"{len(rec_masa.lineas)} lineas, lote = ${total:.2f}")
        print(f"  receta {marcador.id} renombrada a '{marcador.nombre}'")
        if problemas:
            print("\n  OJO:")
            for p in problemas:
                print(f"    - {p}")
            sys.exit(1)
        print("\n  verificado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
