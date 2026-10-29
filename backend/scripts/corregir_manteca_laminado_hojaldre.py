"""One-off: mueve la manteca de laminado del hojaldre de la masa al baston.

Es el mismo fallo que `corregir_manteca_laminado.py` arreglo en Croissant y
Medialuna el dia que se escribio; Hojaldre se quedo fuera de aquel arreglo.

`Masa de Hojaldre` (receta 3) lleva Manteca DOS veces: 900 g (la de la masa,
correcta) y 3000 g, que en realidad son 3 kg de MANTECA LAMINADA y se usan al
laminar el baston, no al amasar. Confirmado con Felipe el 29/10/2026.
3000 g / 3 bastones por lote = 1 kg de Manteca Laminado por baston, exactamente
el mismo numero que Baston Croissant y Baston Medialuna.

  * Masa de Hojaldre (receta 3):  se borra la linea de 3000 g Manteca (id 25).
  * Baston Hojaldre (receta 31):  se anade 1 kg de Manteca Laminado
    (subreceta 23), copia exacta de la linea 152 de Baston Croissant.

=============================================================================
POR QUE EL HISTORICO NO SE REPROCESA CON revertir_efectos + aplicar_efectos
=============================================================================
Porque seria destructivo, y aqui esta medido en vez de supuesto. Los dos
registros a corregir son el 463 (24/10, Masa de Hojaldre) y el 471 (26/10,
Baston Hojaldre), y los CUATRO productos implicados tienen un conteo fisico
del 29/10, posterior a ambos:

    Masa Hojaldre    PC 23  lote 2174  29/10
    Baston Hojaldre  PC 31  lote 2182  29/10 (4 u)
    Manteca Laminado PC 28  lote 2179  29/10 (5 u)
    Manteca          ing 10 IR 1959    29/10 (7,2 kg)

Reaplicar crea un lote de salida NUEVO con id alto y fecha vieja, que
`reconciliar_lotes_tras_conteo` ya no puede barrer porque filtra por `id <`.
El saldo acabaria sumando el conteo MAS la produccion que ese conteo ya
reflejaba: +1 lote de Masa Hojaldre y +3 de Baston Hojaldre. Es el incidente
del 13/10/2026 que CLAUDE.md documenta ("NUNCA reaplicar produccion
historica"), el que dejo Pan 1kg Integral en 187 contra un real de 23.

Asi que esto es SOLO LEDGER, el mismo regimen que `ajustar_consumo_padre` usa
cuando `_conteo_posterior` da true: ningun `StockCongelado` se toca. El conteo
del 29/10 ya re-anclo la estanteria, de modo que no hay efecto fisico que
corregir -- solo la historia entre el 22 y el 29.

El movimiento que se anade lleva `NOTA_SIN_LOTES` por la misma razon que
explica `ajustar_consumo_padre`: sin el tag, un revert completo posterior del
registro llega a `_restaurar_lotes` sin filas `ConsumoFifoDetalle` y fabrica un
lote nuevo, activo y backdateado por el monto entero -- el mismo inflado
irreversible por la puerta de atras.

Salvaguarda: se snapshotea la tabla `StockCongelado` entera y los saldos de los
cuatro items antes de escribir, y se hace ROLLBACK si alguno se mueve. No
deberia moverse ninguno: el conteo del 29/10 manda sobre todo lo anterior.

Dry-run por defecto; --apply para escribir.
"""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    InventarioRegistro,
    LineaReceta,
    MovimientoStock,
    Receta,
    StockCongelado,
)
from app.services.stock import (  # noqa: E402
    NOTA_SIN_LOTES,
    get_saldo_congelado,
    get_saldo_materia_prima,
    get_saldos_materia_prima,
    registrar_movimiento,
)

MASA_HOJALDRE = 3
BASTON_HOJALDRE = 31
MANTECA_LAMINADO_RECETA = 23
MANTECA_LAMINADO_PC = 28
MANTECA_ING = 10

LINEA_A_BORRAR = 25  # Masa de Hojaldre, 3000 g Manteca
CANTIDAD_ESPERADA = 3000.0

# reg 463: la masa del 24/10 que dedujo los 3 kg de Manteca que no tocaban.
REG_MASA = 463
MOV_MANTECA_SOBRANTE = 4092
# reg 471: los 3 bastones del 26/10 que debieron consumir 3 u de Manteca Laminado.
REG_BASTON = 471
FECHA_BASTON = date(2026, 10, 26)
CONSUMO_BASTON = 3.0


def saldos(db):
    """Los numeros que NO se pueden mover."""
    return {
        "pc23_masa_hojaldre": get_saldo_congelado(db, 23),
        "pc31_baston_hojaldre": get_saldo_congelado(db, BASTON_HOJALDRE),
        "pc28_manteca_laminado": get_saldo_congelado(db, MANTECA_LAMINADO_PC),
        "ing10_manteca_ledger": get_saldos_materia_prima(db, [MANTECA_ING]).get(MANTECA_ING),
        "lotes_total": db.query(StockCongelado).count(),
        "lotes_suma": sum(l.cantidad for l in db.query(StockCongelado).all()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        antes = saldos(db)
        print("Saldos ANTES (ninguno debe moverse):")
        for k, v in antes.items():
            print(f"    {k:<24} {v}")
        print()

        # --- comprobaciones previas: el script no es idempotente, asi que se
        # --- niega a correr dos veces en vez de duplicar el arreglo.
        linea = db.get(LineaReceta, LINEA_A_BORRAR)
        if linea is None or linea.receta_id != MASA_HOJALDRE:
            print(f"ABORTA: la linea {LINEA_A_BORRAR} no esta en la receta {MASA_HOJALDRE}.")
            return 1
        if linea.ingrediente_id != MANTECA_ING or linea.cantidad != CANTIDAD_ESPERADA:
            print(
                f"ABORTA: la linea {LINEA_A_BORRAR} es "
                f"ing={linea.ingrediente_id} {linea.cantidad} {linea.unidad}, "
                f"se esperaba ing={MANTECA_ING} {CANTIDAD_ESPERADA} g."
            )
            return 1
        if db.query(LineaReceta).filter(
            LineaReceta.receta_id == BASTON_HOJALDRE,
            LineaReceta.subreceta_id == MANTECA_LAMINADO_RECETA,
        ).first():
            print("ABORTA: Baston Hojaldre ya tiene la linea de Manteca Laminado.")
            return 1

        mov = db.get(MovimientoStock, MOV_MANTECA_SOBRANTE)
        if mov is None or mov.referencia_origen != f"registro_produccion:{REG_MASA}":
            print(
                f"ABORTA: el movimiento {MOV_MANTECA_SOBRANTE} no esta vivo bajo "
                f"registro_produccion:{REG_MASA} (ref={mov.referencia_origen!r} "
                f"si existe). Puede que ya se corrigiera."
            )
            return 1
        if mov.referencia_producto_id != MANTECA_ING or mov.cantidad != -CANTIDAD_ESPERADA / 1000:
            print(f"ABORTA: el movimiento {MOV_MANTECA_SOBRANTE} no es el de -3 kg de Manteca.")
            return 1
        if db.query(MovimientoStock).filter(
            MovimientoStock.referencia_origen == f"registro_produccion:{REG_BASTON}",
            MovimientoStock.referencia_producto_id == MANTECA_LAMINADO_PC,
            MovimientoStock.tipo_stock == "congelado",
        ).first():
            print("ABORTA: el registro 471 ya consume Manteca Laminado.")
            return 1

        print("PASO 1 - receta (afecta a la produccion futura y al costo):")
        print(f"    - borrar linea {LINEA_A_BORRAR}: Masa de Hojaldre, {linea.cantidad} g Manteca")
        print(f"    + anadir a Baston Hojaldre: 1.0 kg Manteca Laminado (subreceta {MANTECA_LAMINADO_RECETA})")
        print()
        print("PASO 2 - historico desde el 22/10 (SOLO LEDGER, los lotes no se tocan):")
        print(f"    reg {REG_MASA} ({mov.fecha}): anular mov {mov.id} de {mov.cantidad} kg Manteca")
        print(f"    reg {REG_BASTON} ({FECHA_BASTON}): anadir -{CONSUMO_BASTON} u de Manteca Laminado")
        print()

        if not args.apply:
            print("Dry-run. Usar --apply para escribir.")
            return 0

        # ---------- PASO 1: receta ----------
        db.delete(linea)
        db.add(LineaReceta(
            receta_id=BASTON_HOJALDRE,
            subreceta_id=MANTECA_LAMINADO_RECETA,
            cantidad=1.0,
            unidad="kg",
        ))
        db.flush()

        # ---------- PASO 2a: anular los 3 kg de Manteca del reg 463 ----------
        # Misma forma que revertir_consumos (retag + compensacion), pero sobre
        # UN movimiento y no sobre todo el registro: el resto de los efectos del
        # 463 (los 0,9 kg de manteca, la harina, el lote de salida) son correctos
        # y no se tocan.
        ref_masa = f"registro_produccion:{REG_MASA}"
        rev_ref = f"{ref_masa}:rev"
        devuelto = -mov.cantidad
        saldo_mp = get_saldo_materia_prima(db, MANTECA_ING) + devuelto
        db.add(InventarioRegistro(
            ingrediente_id=MANTECA_ING,
            cantidad=saldo_mp,
            unidad=mov.unidad,
            fecha_registro=mov.fecha,
            notas=f"Reversion de {ref_masa} (+{devuelto:.3f})",
        ))
        registrar_movimiento(
            db, mov.tipo_stock, MANTECA_ING, devuelto, mov.unidad,
            mov.tipo_movimiento, rev_ref, saldo_mp, None,
            notas=f"Reversion de {ref_masa} (la manteca de laminado pasa al baston)",
            fecha=mov.fecha,
        )
        mov.referencia_origen = rev_ref
        db.flush()

        # ---------- PASO 2b: el consumo de Manteca Laminado del reg 471 ----------
        registrar_movimiento(
            db, "congelado", MANTECA_LAMINADO_PC, -CONSUMO_BASTON, "u",
            "produccion_consumo", f"registro_produccion:{REG_BASTON}",
            get_saldo_congelado(db, MANTECA_LAMINADO_PC), None,
            notas=f"{NOTA_SIN_LOTES}manteca de laminado movida de la masa al baston "
                  f"(conteo posterior: los lotes no se tocan)",
            fecha=FECHA_BASTON,
        )
        db.flush()

        # ---------- verificacion ----------
        despues = saldos(db)
        movidos = {k: (antes[k], despues[k]) for k in antes
                   if abs((antes[k] or 0) - (despues[k] or 0)) > 1e-9}
        if movidos:
            db.rollback()
            print("ROLLBACK: algun saldo se movio y no deberia:")
            for k, (a, d) in movidos.items():
                print(f"    {k}: {a} -> {d}")
            return 1

        db.commit()
        print("Escrito. Ningun saldo fisico se movio, como estaba previsto.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
