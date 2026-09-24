"""One-off: el catalogo "Pizza" apunta a la masa, no al producto terminado.

`ProductoCatalogo` id 21 "Pizza" tiene `receta_id=7` ("Pizza 350g", la MASA,
`porciones_por_lote=1`) cuando le corresponde la 44 ("Formar y Cocinar Pizza",
`porciones_por_lote=20`, que consume la 7 como subreceta). Dos consecuencias:

  * el costo unitario se lee como el lote entero, $6.524 en vez de $326. En el
    analisis de margen del 15/08-15/09 eso metia -$146.945 de perdida ficticia
    sobre 24 pizzas vendidas;
  * `deducir_congelado_por_catalogo()` resuelve el congelado por `cat.receta_id`,
    asi que una entrega B2B con Pizza descontaba "Masa de Pizza" (PC 46) en vez
    de "Pizza Cocinado" (PC 20).

Es el hueco ya documentado en CLAUDE.md: `ProductoCatalogoCreate/Update` no
exponen `receta_id`, asi que no hay endpoint que pueda corregirlo y hay que
escribir la fila directamente. Es dato de catalogo, no del ledger.

Sin flag hace dry run.

    DATABASE_URL=... python scripts/corregir_receta_catalogo_pizza.py
    DATABASE_URL=... python scripts/corregir_receta_catalogo_pizza.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import ProductoCatalogo, Receta  # noqa: E402
from app.database import SessionLocal  # noqa: E402

RECETA_MASA = 7        # Pizza 350g
RECETA_TERMINADO = 44  # Formar y Cocinar Pizza


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        cat = (
            db.query(ProductoCatalogo)
            .filter(ProductoCatalogo.nombre == "Pizza")
            .first()
        )
        if not cat:
            print("catalogo 'Pizza' no encontrado")
            return
        if cat.receta_id == RECETA_TERMINADO:
            print("Pizza: ya apunta a la receta del terminado, nada que hacer")
            return
        if cat.receta_id != RECETA_MASA:
            print(f"Pizza: apunta a receta {cat.receta_id}, no a la {RECETA_MASA} "
                  "esperada -- reviso a mano antes de tocar")
            return

        nueva = db.query(Receta).filter(Receta.id == RECETA_TERMINADO).first()
        vieja = db.query(Receta).filter(Receta.id == RECETA_MASA).first()
        print(f"catalogo {cat.id} 'Pizza': receta {vieja.id} '{vieja.nombre}' "
              f"({vieja.porciones_por_lote:.0f} porc) -> "
              f"{nueva.id} '{nueva.nombre}' ({nueva.porciones_por_lote:.0f} porc)")

        if apply:
            cat.receta_id = RECETA_TERMINADO
            db.commit()
            print("\nAplicado.")
        else:
            print("\nDry run -- usa --apply para escribir.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
