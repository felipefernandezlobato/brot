"""One-off: reorganise the weekly production plan (Felipe, 2026-10-15).

`dia_semana` is `isoweekday()`: **1=Lunes ... 7=Domingo**, NOT 0-based. Reading
it as 0-based shifts every task one day and silently moves work to the wrong
day -- check this first in anything that touches the plan.

WHAT CHANGES
------------
Mover (ninguna tiene registros, asi que el cambio es limpio):
  * Amasar Pan Negro        Mie -> Mar, a las 12:00 (amasa el martes, se cocina
    el miercoles; las 07:00 del martes ya las ocupa Pan Blanco cocinar)
  * Pan Negro cocinar 1kg   Jue -> Mie 07:00  (slot que deja libre el amasado)
  * Pan Negro cocinar 0.5kg Jue -> Mie 08:00

Desactivar, NO borrar -- `RegistroProduccion.tarea_id` es una FK real y todas
tienen historial (LLEVAR PEDIDO 9 registros cada una, Guardar + Armar Pedido 6).
`GET /dia` y `GET /calendario` filtran `is_active == True`, asi que desaparecen
de la pantalla y del calendario conservando lo ya registrado:
  * Guardar + Armar Pedido (Jue), Armar Pedido (Sab), LLEVAR PEDIDO (Sab),
    LLEVAR PEDIDO (Mie)  -> los reemplaza una sola casilla
  * Sacramento Crudo (Mie), Sacramento Cocinar (Jue), Banda Manzana (Jue)
    -> se hacen de vez en cuando, pasan a cargarse como produccion extra
  * Limpieza (Vie) -> la limpieza queda lunes, martes y sabado

Crear:
  * "Armar + Llevar Pedido" Mie 17:00 y Sab 15:00 (tipo entrega: la casilla
    cubre tambien la entrega, que es lo que hacia LLEVAR PEDIDO)
  * "Stock Materia Prima" Jue 16:00 y "Stock Congelado" Jue 16:30 -- el
    inventario semanal se lleva bastante tiempo y no se registraba en ningun
    lado. Dos casillas y no una: son dos recorridos distintos (deposito vs
    camara) y asi cada uno cronometra su propio rato.
  * "Limpieza" Mar 13:00 y Sab 17:00 (el lunes ya la tiene)

Las tres casillas nuevas que no son produccion van sin `cantidad_planificada`,
igual que Limpieza: `GET /dia` pide duracion en vez de cantidad para esas.

Todo via los endpoints reales (`create_tarea` / `update_tarea`). El calendario
semanal no necesita nada: `GET /api/produccion/calendario` lee estas mismas
filas, asi que se refleja solo.

    DATABASE_URL=... python scripts/reorganizar_plan_semanal_2026_10.py           # dry run
    DATABASE_URL=... python scripts/reorganizar_plan_semanal_2026_10.py --apply
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import RegistroProduccion, TareaProduccion, User  # noqa: E402
from app.routers.produccion import create_tarea, update_tarea  # noqa: E402
from app.schemas import TareaProduccionCreate, TareaProduccionUpdate  # noqa: E402

LUN, MAR, MIE, JUE, VIE, SAB = 1, 2, 3, 4, 5, 6
DIAS = {1: "Lunes", 2: "Martes", 3: "Miercoles", 4: "Jueves", 5: "Viernes", 6: "Sabado"}

# (id, titulo esperado, dia nuevo, hora nueva)
MOVER = [
    (69, "Amasar Pan Negro", MAR, "12:00"),
    (77, "Pan Negro cocinar 1kg", MIE, "07:00"),
    (78, "Pan Negro cocinar 0.5kg", MIE, "08:00"),
]

# (id, titulo esperado, motivo)
DESACTIVAR = [
    (88, "Guardar + Armar Pedido", "reemplazada por la casilla unica"),
    (105, "Armar Pedido", "reemplazada por la casilla unica"),
    (106, "LLEVAR PEDIDO", "reemplazada por la casilla unica"),
    (89, "LLEVAR PEDIDO", "reemplazada por la casilla unica"),
    (75, "Sacramento Crudo", "pasa a produccion extra"),
    (87, "Sacramento Cocinar", "pasa a produccion extra"),
    (81, "Banda Manzana", "pasa a produccion extra"),
    (96, "Limpieza", "la limpieza queda lunes, martes y sabado"),
]

CREAR = [
    TareaProduccionCreate(dia_semana=MIE, hora="17:00", titulo="Armar + Llevar Pedido",
                          tipo="entrega", posicion=0),
    TareaProduccionCreate(dia_semana=SAB, hora="15:00", titulo="Armar + Llevar Pedido",
                          tipo="entrega", posicion=0),
    # Dos casillas separadas, no una de "inventario": son dos recorridos
    # distintos (deposito vs camara) y asi cada uno cronometra su propio rato.
    TareaProduccionCreate(dia_semana=JUE, hora="16:00", titulo="Stock Materia Prima",
                          tipo="admin", posicion=0),
    TareaProduccionCreate(dia_semana=JUE, hora="16:30", titulo="Stock Congelado",
                          tipo="admin", posicion=0),
    TareaProduccionCreate(dia_semana=MAR, hora="13:00", titulo="Limpieza",
                          tipo="limpieza", posicion=0),
    TareaProduccionCreate(dia_semana=SAB, hora="17:00", titulo="Limpieza",
                          tipo="limpieza", posicion=0),
]


def plan_actual(db):
    return (
        db.query(TareaProduccion)
        .filter(TareaProduccion.is_active.is_(True))
        .order_by(TareaProduccion.dia_semana, TareaProduccion.hora, TareaProduccion.id)
        .all()
    )


def imprimir_plan(db, etiqueta: str) -> None:
    print(f"\n  === {etiqueta} ===")
    for dia in sorted(DIAS):
        tareas = [t for t in plan_actual(db) if t.dia_semana == dia]
        print(f"    {DIAS[dia]} ({len(tareas)})")
        for t in tareas:
            print(f"      {t.hora or '--:--':6} [{t.tipo:10}] {t.titulo}")


def main() -> None:
    aplicar = "--apply" in sys.argv
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print("  no hay usuario admin.")
            return

        # Verificar que cada id sigue siendo lo que creemos antes de tocarlo:
        # un plan se edita a mano desde la app, los ids no son garantia.
        problemas = []
        for tid, titulo, dia, hora in MOVER:
            t = db.get(TareaProduccion, tid)
            if not t or t.titulo != titulo:
                problemas.append(f"mover {tid}: esperaba '{titulo}', hay '{t.titulo if t else 'nada'}'")
        for tid, titulo, _m in DESACTIVAR:
            t = db.get(TareaProduccion, tid)
            if not t or t.titulo != titulo:
                problemas.append(f"desactivar {tid}: esperaba '{titulo}', hay '{t.titulo if t else 'nada'}'")
        if problemas:
            print("  ABORTADO, el plan no es el esperado:")
            for p in problemas:
                print(f"    {p}")
            return

        print(f"{'APLICANDO' if aplicar else 'DRY RUN'}\n")
        print("  MOVER:")
        for tid, titulo, dia, hora in MOVER:
            t = db.get(TareaProduccion, tid)
            print(f"    {titulo:28} {DIAS[t.dia_semana]} {t.hora} -> {DIAS[dia]} {hora}")
        print("\n  DESACTIVAR:")
        for tid, titulo, motivo in DESACTIVAR:
            t = db.get(TareaProduccion, tid)
            n = db.query(RegistroProduccion).filter(RegistroProduccion.tarea_id == tid).count()
            print(f"    {titulo:28} {DIAS[t.dia_semana]:10} ({n} registros se conservan) -- {motivo}")
        print("\n  CREAR:")
        for c in CREAR:
            print(f"    {c.titulo:28} {DIAS[c.dia_semana]:10} {c.hora} [{c.tipo}]")

        if not aplicar:
            imprimir_plan(db, "plan ACTUAL (sin cambios)")
            print("\n  dry run: no se escribio nada. Agregar --apply.")
            return

        for tid, _titulo, dia, hora in MOVER:
            update_tarea(tid, TareaProduccionUpdate(dia_semana=dia, hora=hora), user=admin, db=db)
        for tid, _titulo, _motivo in DESACTIVAR:
            update_tarea(tid, TareaProduccionUpdate(is_active=False), user=admin, db=db)
        for c in CREAR:
            create_tarea(c, user=admin, db=db)

        imprimir_plan(db, "plan NUEVO")
    finally:
        db.close()


if __name__ == "__main__":
    main()
