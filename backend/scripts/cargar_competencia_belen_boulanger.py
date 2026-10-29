"""Carga los precios de Panaderia Belen y Le Boulanger (presupuestos del 28/10/2026).

Las dos cotizaciones son MAYORISTAS -- confirmado con Felipe: "el que nos harian
como obrador todo" -- asi que son comparables con nuestro PVP B2B, a diferencia
del lio que hubo con BRUTO, donde lo cargado era mostrador contra nuestro B2B.

Tres cosas que NO son comparables como-con-como y por eso llevan nota:

1. El pan de chocolate y el cinnamon roll de Le Boulanger son TAMANO MEDIALUNA
   (lo dice su propia nota). Los nuestros son mas grandes. A $583 contra los
   $1.500 del pan de chocolate de Belen, la diferencia es de tamano y no de
   precio. Felipe pidio cargarlos igual, con la salvedad visible.
2. No sabemos si el pan de ninguna de las dos es de masa madre como el nuestro.
   Es justo lo que invalido la comparacion con LE MAISON.
3. Las medialunas (y los dos de arriba) se cotizan por docena; aqui va el
   precio por unidad, que es la base del resto de la tabla.

El Cinnamon Roll de Belen NO se carga: su lista dice "a cotizar", no hay precio.

Las notas que comparten salvedad son IDENTICAS a proposito: `numerarNotas()` en
competencia/page.tsx agrupa las notas al pie por TEXTO, asi que un texto
distinto para el mismo aviso duplica la nota en la leyenda.

Dry-run por defecto; --apply para escribir.
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import PrecioCompetencia, Receta  # noqa: E402

FECHA = date(2026, 10, 28)

BELEN = "Panaderia Belen"
BOULANGER = "Le Boulanger"

BELEN_BASE = (
    "Mayorista de Panaderia Belen, presupuesto del 28/10/2026: "
    "comparable con nuestro PVP B2B."
)
BELEN_DOCENA = BELEN_BASE + " Lo cotizan por docena a $6.000; aqui va el precio por unidad."
BELEN_PAN = BELEN_BASE + " Sin confirmar si su pan es de masa madre como el nuestro."

BOUL_BASE = (
    "Mayorista de Le Boulanger, cotizacion del 28/10/2026, reparto incluido: "
    "comparable con nuestro PVP B2B."
)
BOUL_DOCENA = BOUL_BASE + " Lo cotizan por docena a $7.000; aqui va el precio por unidad."
BOUL_TAMANO = (
    BOUL_BASE + " Lo cotizan por docena a $7.000 y su nota aclara que es TAMANO"
    " MEDIALUNA; el nuestro es mas grande, asi que no es el mismo producto."
)
BOUL_PAN = (
    BOUL_BASE + " Es una hogaza de 500 g. Sin confirmar si su pan es de masa"
    " madre como el nuestro."
)

# (competidor, receta_id, nombre esperado, precio, notas)
FILAS = [
    (BELEN, 10, "Croissant", 900.0, BELEN_BASE),
    (BELEN, 11, "Medialuna", 500.0, BELEN_DOCENA),
    (BELEN, 12, "Pan de Choco Cocinado", 1500.0, BELEN_BASE),
    (BELEN, 4, "Pan Blanco 1kg", 4500.0, BELEN_PAN),
    (BELEN, 6, "Pan Integral 1kg", 4800.0, BELEN_PAN),
    (BOULANGER, 10, "Croissant", 1100.0, BOUL_BASE),
    (BOULANGER, 11, "Medialuna", 583.33, BOUL_DOCENA),
    (BOULANGER, 12, "Pan de Choco Cocinado", 583.33, BOUL_TAMANO),
    (BOULANGER, 34, "Cinnamon Roll", 583.33, BOUL_TAMANO),
    (BOULANGER, 5, "Pan Blanco 0.5kg", 1300.0, BOUL_PAN),
    (BOULANGER, 22, "Pan Integral 0.5kg", 1800.0, BOUL_PAN),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="escribir de verdad")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        errores: list[str] = []
        a_crear: list[PrecioCompetencia] = []

        for competidor, receta_id, nombre_esperado, precio, notas in FILAS:
            receta = db.get(Receta, receta_id)
            if receta is None:
                errores.append(f"Receta {receta_id} no existe")
                continue
            # Los ids van escritos a mano: si alguno apunta a otra receta,
            # cargariamos el precio contra el producto equivocado en silencio.
            if receta.nombre != nombre_esperado:
                errores.append(
                    f"Receta {receta_id} se llama {receta.nombre!r}, "
                    f"se esperaba {nombre_esperado!r}"
                )
                continue

            ya = (
                db.query(PrecioCompetencia)
                .filter(
                    PrecioCompetencia.competidor_nombre == competidor,
                    PrecioCompetencia.receta_id == receta_id,
                )
                .first()
            )
            if ya:
                print(f"  ya existe, se salta: {competidor} / {receta.nombre} (id {ya.id})")
                continue

            print(f"  + {competidor:<16} {receta.nombre:<24} ${precio:>9,.2f}")
            a_crear.append(
                PrecioCompetencia(
                    receta_id=receta_id,
                    competidor_nombre=competidor,
                    precio=precio,
                    fecha_registro=FECHA,
                    notas=notas,
                )
            )

        if errores:
            print("\nERRORES, no se escribe nada:")
            for e in errores:
                print(f"  - {e}")
            return 1

        print(f"\n{len(a_crear)} filas a crear.")
        if not args.apply:
            print("Dry-run. Usar --apply para escribir.")
            return 0

        for obj in a_crear:
            db.add(obj)
        db.commit()
        print("Escrito.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
