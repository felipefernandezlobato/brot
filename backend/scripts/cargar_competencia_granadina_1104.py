"""Actualiza La Granadina con su presupuesto del 04/11/2026.

Lo que cambia respecto de lo que habia cargado (del menu publico de ola.click,
29/09/2026):

1. **La factura BAJA de $1.100 a $791,67.** Las tres filas que ya existian
   (Medialuna, Sacramento, Cinnamon Roll) se ACTUALIZAN en vez de insertar una
   segunda fila: `comparar_competencia` devuelve todas las filas y
   `competencia/page.tsx` las mete en un `new Map()` por nombre de competidor,
   asi que de dos filas del mismo competidor y receta solo se ve UNA y la otra
   desaparece sin avisar. No hay vista historica de precios de competencia.

2. **El croissant ya es comparable.** El menu publico listaba "CROISSANT
   $8.000", que su propia descripcion revelaba como una bandeja de 2 croissants
   rellenos de jamon y queso -- CLAUDE.md anota que por eso NO se cargo. El
   presupuesto cotiza "Croissant / Unidad / $1.200", que si es el mismo
   producto que el nuestro.

3. **Primer precio de pan de La Granadina.** Su menu publicaba el pan con
   `availability` pero sin `price`, asi que no habia ninguno.

Mayorista o minorista: el presupuesto dice "Venta Mayorista / Minorista" sin
aclarar cual, y es justo la duda que invalido la comparacion con LE MAISON. Hay
un indicio fuerte de que es mayorista: la factura baja un 28% contra el menu
publico, casi exactamente la misma brecha (24%) que BRUTO tiene entre su
mostrador y su mayorista. Indicio, no confirmacion, y por eso va en la nota.

El pan se cotiza POR KILO, asi que solo se carga contra Pan Blanco 1kg y Pan
Integral 1kg. Contra los de medio kilo habria que partir el precio a la mitad,
que es un numero derivado y no cotizado -- y CLAUDE.md ya anota que nuestro
medio kilo lleva el 55,6% de la masa del kilo pero se vende a la mitad exacta,
asi que la division tampoco seria limpia del lado nuestro.

Notas IDENTICAS donde la salvedad es la misma: `numerarNotas()` agrupa las
notas al pie por TEXTO, asi que un texto distinto para el mismo aviso duplica
la nota en la leyenda. Por eso los dos panes comparten una sola nota que lleva
las dos salvedades (masa madre + salvado) en vez de una nota casi igual cada uno.

Dry-run por defecto; --apply para escribir.
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import PrecioCompetencia, Receta  # noqa: E402

FECHA = date(2026, 11, 4)
GRANADINA = "La Granadina"

# $9.500 la docena. Se guarda redondeado a 2 decimales como el 583,33 de
# Le Boulanger, que tambien venia de una docena.
FACTURA_UNIDAD = round(9500 / 12, 2)  # 791.67

BASE = (
    "Presupuesto de La Granadina del 04/11/2026, IVA incluido. Su condicion dice"
    " 'Mayorista / Minorista' sin aclarar cual: la factura baja un 28% contra los"
    " $1.100 de su menu publico, casi la misma brecha que BRUTO tiene entre"
    " mostrador y mayorista, asi que parece mayorista."
)
DOCENA = (
    BASE + " Lo cotizan como docena de facturas surtidas a $9.500; aqui va el"
    " precio por unidad."
)
PAN = (
    BASE + " Lo cotizan por kilo. Sin confirmar si su pan es de masa madre como"
    " el nuestro, ni si su integral es integral o de salvado."
)

# (receta_id, nombre esperado, precio, notas)
FILAS = [
    (11, "Medialuna", FACTURA_UNIDAD, DOCENA),
    (24, "Sacramento", FACTURA_UNIDAD, DOCENA),
    (34, "Cinnamon Roll", FACTURA_UNIDAD, DOCENA),
    (10, "Croissant", 1200.0, BASE),
    (4, "Pan Blanco 1kg", 3300.0, PAN),
    (6, "Pan Integral 1kg", 4000.0, PAN),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="escribir de verdad")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        errores: list[str] = []
        altas: list[PrecioCompetencia] = []
        cambios: list[tuple[PrecioCompetencia, float, str]] = []

        for receta_id, nombre_esperado, precio, notas in FILAS:
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

            existentes = (
                db.query(PrecioCompetencia)
                .filter(
                    PrecioCompetencia.competidor_nombre == GRANADINA,
                    PrecioCompetencia.receta_id == receta_id,
                )
                .order_by(PrecioCompetencia.id)
                .all()
            )
            if len(existentes) > 1:
                errores.append(
                    f"{receta.nombre}: ya hay {len(existentes)} filas de"
                    f" {GRANADINA}; hay que resolver a mano cual queda"
                )
                continue

            if existentes:
                fila = existentes[0]
                print(
                    f"  ~ {receta.nombre:<16} ${fila.precio:>9,.2f}"
                    f" -> ${precio:>9,.2f}   ({fila.fecha_registro} -> {FECHA})"
                )
                cambios.append((fila, precio, notas))
            else:
                print(f"  + {receta.nombre:<16} {'':>10}    ${precio:>9,.2f}   (nueva)")
                altas.append(
                    PrecioCompetencia(
                        receta_id=receta_id,
                        competidor_nombre=GRANADINA,
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

        print(f"\n{len(altas)} alta(s), {len(cambios)} actualizacion(es)")
        if not args.apply:
            print("(dry run -- pasar --apply para escribir)")
            return 0

        for fila, precio, notas in cambios:
            fila.precio = precio
            fila.fecha_registro = FECHA
            fila.notas = notas
        for alta in altas:
            db.add(alta)
        db.commit()
        print("ESCRITO")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
