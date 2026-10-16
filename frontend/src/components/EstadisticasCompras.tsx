"use client";

/* Estadisticas de compras, al pie de la pestaña Activos de /pedidos.
 *
 * Lo ve CUALQUIER empleado, a diferencia de EstadisticasMensuales (inicio, solo
 * admin): no muestra facturacion, margen ni clientes, solo en que se gasta. La
 * misma pantalla ya le muestra a cualquiera el total en pesos de cada pedido.
 *
 * El gasto sale de GET /api/dashboard/compras-mensual, que comparte
 * resumen_compras_mensual() con /api/dashboard/mensual: el total de un mes aca
 * y en inicio es el mismo numero por construccion, no por coincidencia.
 *
 * El endpoint devuelve TODOS los meses de una, asi que cambiar de mes es
 * instantaneo y no vuelve a pedir nada.
 */

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import {
  Fila,
  Panel,
  SelectorMes,
  Tarjeta,
  type CambioPrecio,
  type ItemMonto,
} from "@/components/stats/common";

interface MesCompras {
  mes: string;
  es_parcial: boolean;
  dias_transcurridos: number;
  dias_totales: number;
  compras_total_ars: number;
  pedidos_recibidos: number;
  top_ingredientes: (ItemMonto & { ingrediente_id: number })[];
  por_proveedor: (ItemMonto & { proveedor_id: number })[];
  cambios_precio: CambioPrecio[];
  lineas_sin_precio: number;
}

interface ComprasData {
  periodo: { desde: string; hasta: string; meses: number };
  meses: MesCompras[];
}

export function EstadisticasCompras({
  pendiente,
}: {
  /* Valor de los pedidos ya enviados que todavia no llegaron. Se calcula en la
   * pantalla, con los pedidos que ya tiene cargados, y es un ESTIMADO: sale de
   * lo pedido por el precio esperado, porque un pedido sin recibir no tiene
   * cantidad recibida ni precio final. No es lo mismo que el gasto del mes, que
   * cuenta solo lo recibido. */
  pendiente: { pedidos: number; estimadoArs: number };
}) {
  const [data, setData] = useState<ComprasData | null>(null);
  const [idx, setIdx] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiFetch<ComprasData>("/api/dashboard/compras-mensual?meses=6")
      .then((d) => {
        setData(d);
        setIdx(Math.max(0, d.meses.length - 1)); // arranca en el mes en curso
      })
      .catch(() => setError(true));
  }, []);

  // Si falla, la pestaña de pedidos sigue sirviendo igual.
  if (error) return null;
  if (!data) {
    return (
      <div className="bg-card rounded-xl border border-cream-dark p-4 text-center text-warm-gray text-sm">
        Cargando...
      </div>
    );
  }

  const m = data.meses[idx];
  if (!m) return null;

  return (
    <div>
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <h2 className="titulo text-lg text-brot">Compras del mes</h2>
        <SelectorMes meses={data.meses.map((x) => x.mes)} idx={idx} onSelect={setIdx} />
      </div>

      {m.es_parcial && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 mb-3 inline-block">
          Mes en curso: {m.dias_transcurridos} de {m.dias_totales} días. No es comparable
          con un mes cerrado.
        </p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <Tarjeta
          label="Comprado"
          valor={formatARS(m.compras_total_ars)}
          detalle="por fecha de recepción"
          aviso={
            m.lineas_sin_precio
              ? `${m.lineas_sin_precio} línea${m.lineas_sin_precio !== 1 ? "s" : ""} sin precio`
              : undefined
          }
        />
        <Tarjeta
          label="Pedidos recibidos"
          valor={String(m.pedidos_recibidos)}
          detalle={
            m.pedidos_recibidos
              ? `${formatARS(m.compras_total_ars / m.pedidos_recibidos)} promedio`
              : undefined
          }
        />
        {/* Fuera del mes elegido a proposito: es una foto de hoy, no cambia al
            cambiar de mes. El detalle lo dice para que no parezca un error. */}
        <Tarjeta
          label="Pendiente de recibir"
          valor={formatARS(pendiente.estimadoArs)}
          detalle={
            pendiente.pedidos === 0
              ? "nada en camino"
              : `${pendiente.pedidos} pedido${pendiente.pedidos !== 1 ? "s" : ""} enviado${
                  pendiente.pedidos !== 1 ? "s" : ""
                } · estimado, a hoy`
          }
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel titulo="Gasto por proveedor" vacio={!m.por_proveedor.length}>
          {m.por_proveedor.map((p) => (
            <Fila key={p.proveedor_id} nombre={p.nombre} derecha={formatARS(p.monto_ars)} />
          ))}
        </Panel>

        <Panel titulo="En qué más gastamos" nota="ingredientes" vacio={!m.top_ingredientes.length}>
          {m.top_ingredientes.map((i) => (
            <Fila key={i.ingrediente_id} nombre={i.nombre} derecha={formatARS(i.monto_ars)} />
          ))}
        </Panel>

        {/* Ancho completo: son tres paneles en una grilla de dos, asi el ultimo
            no deja media fila vacia al lado. */}
        <div className="md:col-span-2">
          <Panel
            titulo="Cambios de precio"
            nota="ingredientes"
            vacio={!m.cambios_precio.length}
          >
            {m.cambios_precio.map((c, i) => (
              <Fila
                key={`${c.ingrediente_id}-${i}`}
                nombre={c.nombre}
                sub={`${formatARS(c.precio_anterior)} → ${formatARS(c.precio_nuevo)}`}
                derecha={
                  c.variacion_pct !== null
                    ? `${c.variacion_pct > 0 ? "+" : ""}${c.variacion_pct.toFixed(1)}%`
                    : "—"
                }
              />
            ))}
          </Panel>
        </div>
      </div>

      <p className="text-xs text-warm-gray mt-3">
        Solo cuenta lo recibido, por su fecha de recepción: un pedido enviado todavía no es
        gasto. Las líneas sin precio cargado quedan afuera del total en vez de contarse como
        cero, y se avisan aparte.
      </p>
    </div>
  );
}
