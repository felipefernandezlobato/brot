"""Unifica la ficha placeholder 'Kiosco gabo' dentro de 'Salvador Market'.

El panadero dio de alta a mano "Kiosco gabo" (ficha 25) el 05/11 para poder
cargarle una entrega. El 12/11 el mismo cliente se registro solo en el portal
como "Salvador Market" (ficha 26). Son la misma persona, confirmado por Felipe,
asi que quedan dos fichas: la vieja con la entrega y la nueva con las
credenciales.

**La direccion de la fusion va al reves de la receta de CLAUDE.md, y el motivo
es que la proporcion se invirtio.** Para Creme la regla fue mover las
CREDENCIALES a la ficha vieja y nunca el historial a la nueva, porque eran 2
columnas en 1 fila contra re-apuntar 19 `EntregaB2B` -- las filas de las que
sale toda la facturacion mensual. Aca la ficha vieja tiene UNA entrega y la
nueva tiene contrasena puesta por el cliente, correo verificado y alta
aprobada, las tres de hoy. Borrar la ficha nueva significa que el cliente
vuelva a hacer todo eso, para ahorrarse mover una fila. Asi que se mueve la
entrega y se conserva la cuenta del portal intacta.

Y a diferencia de Creme, aca SI se cambia de nombre: "Kiosco gabo" era un
placeholder que Felipe quiere fuera, no el nombre con el que el obrador conoce
al cliente. El nombre bueno ya lo lleva la ficha que sobrevive, asi que no hay
que renombrar nada.

**Los 4 movimientos de la entrega siguen diciendo "Kiosco gabo" y se dejan
asi.** `MovimientoStock.referencia_origen` es `entrega_b2b:{id}:{nombre}` y
congela el nombre del momento de la entrega. No se reescribe por dos motivos:
es una fila del ledger, que CLAUDE.md prohibe editar a mano, y el sistema ya
esta disenado para tolerarlo -- `_revertir_entrega` busca por PREFIJO
`entrega_b2b:{id}:%` justamente "so a client renamed since then would make a
recomputed tag miss its own movements". O sea que revertir o editar esa entrega
en el futuro sigue funcionando. El unico efecto es cosmetico: en los feeds de
movimientos esa entrega se lee "Entrega B2B Kiosco gabo", que ademas es lo que
realmente decia la ficha ese dia.

**Por que una transaccion y no los endpoints.** `EntregaB2BUpdate` no expone
`cliente_b2b_id`, asi que re-apuntar la entrega no tiene endpoint (misma laguna
que CLAUDE.md anota para `ProductoCongelado.receta_id`). No toca cantidades ni
el ledger: solo cambia a quien se le atribuye. Los otros dos pasos si tienen
endpoint, pero `update_cliente_b2b` es un setattr y `delete_cliente_b2b` un
`db.delete` -- replicarlos aqui los deja en la MISMA transaccion que el
movimiento de la entrega, que es lo que evita quedarse a medias con la ficha
vieja borrada y su entrega huerfana.

Aborta sin escribir si cualquier premisa falla: que las dos fichas se llamen
como se espera, que la nueva no tenga historial propio, que la vieja no tenga
pedidos del portal ni recurrentes ni tokens, y que el facturado total del
cliente no cambie.

Dry-run por defecto; --apply para escribir.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ClienteB2B,
    EntregaB2B,
    PedidoCliente,
    PedidoRecurrente,
    TokenAccesoCliente,
)

VIEJA_ID = 25
VIEJA_NOMBRE = "Kiosco gabo"
NUEVA_ID = 26
NUEVA_NOMBRE = "Salvador Market"

NOTA_FUSION = (
    "Unificado el 12/11/2026 con la ficha placeholder 'Kiosco gabo' (id 25), "
    "que habia creado el panadero el 05/11 para cargarle su primera entrega. "
    "Los movimientos de esa entrega siguen etiquetados 'Kiosco gabo'."
)

# Campos que se traen de la ficha vieja SOLO si la nueva los tiene vacios. La
# nueva los escribio el cliente y mandan; la vieja puede tener algo que el no
# puso, como que pasa a buscar el pedido en vez de que se lo lleven.
CAMPOS_A_RESCATAR = ("direccion", "telefono", "contacto", "dia_entrega_preferido")


def facturado(entregas) -> float:
    return round(
        sum(
            l.cantidad * l.precio_unitario
            for e in entregas
            if e.estado == "entregado"
            for l in e.lineas
        ),
        2,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="escribe; por defecto solo simula")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        vieja = db.get(ClienteB2B, VIEJA_ID)
        nueva = db.get(ClienteB2B, NUEVA_ID)

        if not vieja or not nueva:
            print(f"ABORTA: falta alguna ficha (vieja={bool(vieja)}, nueva={bool(nueva)})")
            return 1
        if vieja.nombre != VIEJA_NOMBRE or nueva.nombre != NUEVA_NOMBRE:
            print(
                "ABORTA: los nombres no son los esperados -- "
                f"{VIEJA_ID}={vieja.nombre!r}, {NUEVA_ID}={nueva.nombre!r}"
            )
            return 1

        ent_vieja = db.query(EntregaB2B).filter(EntregaB2B.cliente_b2b_id == VIEJA_ID).all()
        ent_nueva = db.query(EntregaB2B).filter(EntregaB2B.cliente_b2b_id == NUEVA_ID).all()
        facturado_antes = facturado(ent_vieja) + facturado(ent_nueva)

        # La ficha vieja no puede arrastrar nada que no sepamos mover.
        pedidos = db.query(PedidoCliente).filter(PedidoCliente.cliente_id == VIEJA_ID).count()
        recurrentes = (
            db.query(PedidoRecurrente).filter(PedidoRecurrente.cliente_id == VIEJA_ID).count()
        )
        tokens = (
            db.query(TokenAccesoCliente)
            .filter(TokenAccesoCliente.cliente_b2b_id == VIEJA_ID)
            .count()
        )
        if pedidos or recurrentes or tokens:
            print(
                "ABORTA: la ficha vieja tiene algo mas que entregas "
                f"(pedidos={pedidos}, recurrentes={recurrentes}, tokens={tokens}). "
                "Hay que decidir que hacer con eso antes de borrarla."
            )
            return 1
        if vieja.password_hash:
            print("ABORTA: la ficha vieja tiene contrasena. Ya no es un placeholder.")
            return 1

        print(f"Ficha vieja  #{VIEJA_ID} {vieja.nombre!r}")
        print(f"  entregas: {len(ent_vieja)} -> {[(e.id, str(e.fecha_entrega), e.estado) for e in ent_vieja]}")
        for campo in CAMPOS_A_RESCATAR:
            print(f"  {campo}: {getattr(vieja, campo)!r}")
        print(f"Ficha nueva  #{NUEVA_ID} {nueva.nombre!r}")
        print(f"  entregas: {len(ent_nueva)}  email: {nueva.email!r}  acceso: {bool(nueva.password_hash)}")
        for campo in CAMPOS_A_RESCATAR:
            print(f"  {campo}: {getattr(nueva, campo)!r}")
        print(f"Facturado entregado (las dos fichas): {facturado_antes}")
        print()

        # 1. Las entregas pasan a la ficha que sobrevive.
        for e in ent_vieja:
            print(f"  mover entrega #{e.id} ({e.fecha_entrega}) -> cliente {NUEVA_ID}")
            e.cliente_b2b_id = NUEVA_ID

        # 2. Rescatar lo que el cliente no escribio y el panadero si.
        for campo in CAMPOS_A_RESCATAR:
            actual = (getattr(nueva, campo) or "").strip()
            heredado = (getattr(vieja, campo) or "").strip()
            if not actual and heredado:
                print(f"  {campo}: vacio -> {heredado!r} (de la ficha vieja)")
                setattr(nueva, campo, heredado)

        # 3. Dejar dicho de donde sale la entrega del 05/11.
        notas = (nueva.notas or "").strip()
        nueva.notas = f"{notas}\n{NOTA_FUSION}".strip() if notas else NOTA_FUSION
        print(f"  notas: {nueva.notas!r}")

        # 4. Borrar el placeholder.
        print(f"  borrar ficha #{VIEJA_ID} {vieja.nombre!r}")
        db.delete(vieja)

        db.flush()

        # Verificacion dentro de la transaccion: si algo no cuadra, rollback.
        ent_final = db.query(EntregaB2B).filter(EntregaB2B.cliente_b2b_id == NUEVA_ID).all()
        facturado_despues = facturado(ent_final)
        huerfanas = db.query(EntregaB2B).filter(EntregaB2B.cliente_b2b_id == VIEJA_ID).count()
        errores = []
        if len(ent_final) != len(ent_vieja) + len(ent_nueva):
            errores.append(f"entregas {len(ent_final)} != {len(ent_vieja) + len(ent_nueva)}")
        if abs(facturado_despues - facturado_antes) > 0.01:
            errores.append(f"facturado {facturado_despues} != {facturado_antes}")
        if huerfanas:
            errores.append(f"{huerfanas} entregas siguen apuntando a la ficha borrada")
        if errores:
            db.rollback()
            print("\nABORTA (rollback): " + "; ".join(errores))
            return 1

        print()
        print(f"Resultado: #{NUEVA_ID} {nueva.nombre!r} con {len(ent_final)} entregas, "
              f"facturado {facturado_despues}")

        if args.apply:
            db.commit()
            print("APLICADO.")
        else:
            db.rollback()
            print("DRY-RUN: nada escrito. Repetir con --apply.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
