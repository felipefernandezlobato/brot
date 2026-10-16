"""One-off: cargar el conteo de congelado del 2026-10-15.

Lo contaron la noche del 15 y no lo apuntaron en la app (Felipe por WhatsApp,
2026-10-16). La materia prima de ese dia SI estaba cargada -- los 22
ingredientes, incluido el Azucar en 58,4 kg que en el mensaje venia sin numero
-- asi que este script solo carga el congelado, que estaba en cero filas.

POR QUE IMPORTA MAS QUE UN CONTEO NORMAL
----------------------------------------
Es lo que re-ancla la estanteria que quedo inflada el 13/10 (ver CLAUDE.md,
"NUNCA reaplicar produccion historica"): Pan 500g Integral marcaba 302 contra
21 reales, Pan 1kg Integral 210 contra 23. Un conteo fisico es el unico
mecanismo que corrige eso, y es justo para lo que existe
`reconciliar_lotes_tras_conteo`.

COMO
----
Via `POST /api/congelados` (`add_stock_congelado`), sin `fecha_vencimiento`:
esa es exactamente la forma que envia la pantalla Registrar, y es la condicion
con la que el endpoint llama a `reconciliar_lotes_tras_conteo`, que desactiva
los lotes anteriores para que el conteo SUPERSEDA en vez de sumarse.

"Lo que no hay es todo 0": los 47 productos congelados activos se cargan, los
25 que Felipe no nombro van en 0. Cargar los ceros es lo que de verdad limpia
la estanteria -- omitirlos dejaria sus lotes viejos vivos.

Ojo con el orden: `reconciliar_lotes_tras_conteo` barre por `id <`, asi que
cada producto se carga una sola vez. Si este script se corriera dos veces
quedarian dos conteos del mismo dia, y desde el 2026-10-01 el segundo SUPERSEDE
al primero (no se suman), asi que el saldo seguiria bien, pero ensucia.
Por eso aborta si ya hay conteos de congelado ese dia.

    DATABASE_URL=... python scripts/cargar_conteo_congelado_15_10.py           # dry run
    DATABASE_URL=... python scripts/cargar_conteo_congelado_15_10.py --apply
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import ProductoCongelado, StockCongelado, User  # noqa: E402
from app.routers.congelados import add_stock_congelado  # noqa: E402
from app.schemas import StockCongeladoCreate  # noqa: E402
from app.services.stock import es_conteo_manual, get_saldos_congelado  # noqa: E402

FECHA = date(2026, 10, 15)

# Tal cual lo paso Felipe. La clave es el nombre exacto del ProductoCongelado.
CONTADO = {
    # terminados
    "Medialunas Cocinado": 198, "Croissant Cocinado": 139,
    "Cinnamon Roll Cocinado": 38,          # "Caracolas" en la lista
    "Pan Suizo Cocinado": 5, "Ensaimadas Cocinado": 26, "Cruffin Cocinado": 53,
    "Moño Cocinado": 30, "Pan de Choco Cocinado": 20, "Palmerita Cocinado": 61,
    "Sacramento Cocinado": 22, "Pan NY Cocinado": 3, "Banda Cocinado": 13,
    "Cremadet Cocinado": 59, "Pan 1kg Blanco Cocinado": 24,
    "Pan 500g Blanco Cocinado": 29, "Pan 1kg Integral Cocinado": 9,
    "Pan 500g Integral Cocinado": 20, "Barra Blanca Cocinado": 19,
    "Barra Negra Cocinado": 16, "Pizza Cocinado": 8, "Pan Lomo Cocinado": 10,
    "Focaccia Cocinado": 2,
    # semi elaborados y masas
    "Baston Croissant": 0, "Baston Medialuna": 4, "Ensaimada Cruda": 285,
    "Baston Cinnamon Roll": 1, "Baston Hojaldre": 2, "Masa Pan Negro": 2,
    "Manteca Laminado": 2,   # venia en la lista de materia prima, pero es congelado
}


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print("  no hay usuario admin.")
            return

        ya = [l for l in db.query(StockCongelado).filter(StockCongelado.fecha_entrada == FECHA).all()
              if l.registro_produccion_id is None and es_conteo_manual("congelado", l.notas)]
        if ya:
            print(f"  ABORTADO: ya hay {len(ya)} conteos de congelado el {FECHA}. "
                  f"Revisar antes de volver a cargar.")
            return

        productos = db.query(ProductoCongelado).filter(ProductoCongelado.is_active.is_(True)).all()
        por_nombre = {p.nombre: p for p in productos}

        desconocidos = [n for n in CONTADO if n not in por_nombre]
        if desconocidos:
            print(f"  ABORTADO: nombres que no existen: {desconocidos}")
            return

        # Todo producto activo recibe un conteo. Los que Felipe no nombro van en
        # 0 ("lo que no hay es todo 0"), y son los que limpian la estanteria.
        plan = {p: float(CONTADO.get(p.nombre, 0)) for p in productos}
        nombrados = sum(1 for p in plan if p.nombre in CONTADO)

        saldos = get_saldos_congelado(db, [p.id for p in productos])
        print(f"{'APLICANDO' if aplicar else 'DRY RUN'} -- conteo del {FECHA}")
        print(f"  {len(plan)} productos: {nombrados} contados con stock, {len(plan)-nombrados} en 0\n")
        print(f"  {'producto':28} {'saldo app':>10} {'contado':>9} {'dif':>9}")
        for p in sorted(plan, key=lambda x: (x.nivel, x.nombre)):
            antes = saldos.get(p.id, 0.0)
            d = plan[p] - antes
            marca = "  <-- se corrige fuerte" if abs(d) >= 20 else ""
            print(f"  {p.nombre:28} {antes:>10.2f} {plan[p]:>9.0f} {d:>+9.2f}{marca}")

        if not aplicar:
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        for p in sorted(plan, key=lambda x: x.nombre):
            add_stock_congelado(
                StockCongeladoCreate(
                    producto_congelado_id=p.id,
                    cantidad=plan[p],
                    fecha_entrada=FECHA,
                ),
                user=admin, db=db,
            )

        finales = get_saldos_congelado(db, [p.id for p in productos])
        malos = [(p.nombre, finales.get(p.id, 0.0), plan[p])
                 for p in plan if abs(finales.get(p.id, 0.0) - plan[p]) > 0.005]
        print(f"\n  {len(plan)} conteos cargados.")
        if malos:
            print("  OJO, estos no quedaron en lo contado:")
            for n, real, esperado in malos:
                print(f"    {n:28} saldo {real:>9.2f} contado {esperado:>9.0f}")
        else:
            print("  todos los saldos quedaron exactamente en lo contado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
