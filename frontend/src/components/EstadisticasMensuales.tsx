"use client";

/* Estadisticas mensuales del panel de inicio.
 *
 * Solo admin: a diferencia del resto del panel, que es operativo, esto muestra
 * facturacion, margen y la concentracion de clientes. Se usa loadPermissions()
 * (ya cacheado) para leer el rol, asi que no suma un request.
 *
 * El endpoint devuelve TODOS los meses en una sola respuesta, asi que cambiar
 * de mes es instantaneo y no vuelve a pedir nada.
 */

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { loadPermissions } from "@/lib/permissions";

interface Ventas {
  total_ars: number;
  b2b_ars: number;
  portal_ars: number;
  unidades: number;
}
interface Margen {
  cogs_ars: number;
  bruto_ars: number;
  bruto_pct: number | null;
  ventas_costeadas_ars: number;
  cobertura_pct: number | null;
  lineas_sin_costo: number;
}
interface Mermas {
  total_ars: number;
  registros: number;
  pct_sobre_ventas: number | null;
}
interface ItemMonto {
  nombre: string;
  monto_ars: number;
}
interface TopProducto extends ItemMonto {
  producto_id: number;
  unidades: number;
}
interface PorCliente extends ItemMonto {
  cliente_id: number;
  pct: number | null;
}
interface CambioPrecio {
  ingrediente_id: number;
  nombre: string;
  precio_anterior: number;
  precio_nuevo: number;
  fecha_cambio: string;
  variacion_pct: number | null;
}
interface Mes {
  mes: string;
  es_parcial: boolean;
  dias_transcurridos: number;
  dias_totales: number;
  ventas: Ventas;
  compras_total_ars: number;
  margen: Margen;
  mermas: Mermas;
  top_productos: TopProducto[];
  top_ingredientes: (ItemMonto & { ingrediente_id: number })[];
  por_cliente: PorCliente[];
  por_proveedor: (ItemMonto & { proveedor_id: number })[];
  cambios_precio: CambioPrecio[];
  avisos: { lineas_precio_cero: number; lineas_compra_sin_precio: number };
}
interface MensualData {
  periodo: { desde: string; hasta: string; meses: number };
  meses: Mes[];
}

const NOMBRE_MES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

function etiquetaMes(clave: string): string {
  const [a, m] = clave.split("-").map(Number);
  return `${NOMBRE_MES[m - 1]} ${a}`;
}

function Tarjeta({
  label,
  valor,
  detalle,
  aviso,
}: {
  label: string;
  valor: string;
  detalle?: string;
  aviso?: string;
}) {
  return (
    <div className="bg-card border border-cream-dark rounded-xl p-4">
      <p className="text-xs text-warm-gray">{label}</p>
      <p className="text-xl font-bold text-text tabular-nums">{valor}</p>
      {detalle && <p className="text-xs text-warm-gray mt-0.5">{detalle}</p>}
      {aviso && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-1.5 py-0.5 mt-1 inline-block">
          {aviso}
        </p>
      )}
    </div>
  );
}

function Panel({
  titulo,
  nota,
  vacio,
  children,
}: {
  titulo: string;
  nota?: string;
  vacio: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-cream-dark rounded-xl p-4">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="font-medium text-text text-sm">{titulo}</h3>
        {nota && <span className="text-xs text-warm-gray">{nota}</span>}
      </div>
      {vacio ? (
        <p className="text-xs text-warm-gray">Sin datos este mes</p>
      ) : (
        <div className="space-y-1.5 max-h-[280px] overflow-y-auto">{children}</div>
      )}
    </div>
  );
}

function Fila({ nombre, derecha, sub }: { nombre: string; derecha: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between text-sm gap-3">
      <span className="text-text truncate">{nombre}</span>
      <span className="text-warm-gray tabular-nums whitespace-nowrap">
        {sub && <span className="text-xs mr-2">{sub}</span>}
        {derecha}
      </span>
    </div>
  );
}

export function EstadisticasMensuales() {
  const [esAdmin, setEsAdmin] = useState<boolean | null>(null);
  const [data, setData] = useState<MensualData | null>(null);
  const [idx, setIdx] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    loadPermissions()
      .then((p) => setEsAdmin(p.role === "admin"))
      .catch(() => setEsAdmin(false));
  }, []);

  useEffect(() => {
    if (!esAdmin) return;
    apiFetch<MensualData>("/api/dashboard/mensual?meses=6")
      .then((d) => {
        setData(d);
        setIdx(Math.max(0, d.meses.length - 1)); // arranca en el mes en curso
      })
      .catch(() => setError(true));
  }, [esAdmin]);

  if (!esAdmin) return null;
  if (error) return null; // el panel operativo sigue sirviendo igual
  if (!data) {
    return (
      <div className="bg-card rounded-xl border border-cream-dark p-4 mb-4 text-center text-warm-gray text-sm">
        Cargando...
      </div>
    );
  }

  const m = data.meses[idx];
  if (!m) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <h2 className="titulo text-lg text-brot">Resumen mensual</h2>
        <div className="flex gap-1 flex-wrap">
          {data.meses.map((x, i) => (
            <button
              key={x.mes}
              onClick={() => setIdx(i)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors min-h-[36px] ${
                i === idx ? "bg-brot text-white" : "bg-cream text-warm-gray hover:text-brot"
              }`}
            >
              {etiquetaMes(x.mes)}
            </button>
          ))}
        </div>
      </div>

      {m.es_parcial && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 mb-3 inline-block">
          Mes en curso: {m.dias_transcurridos} de {m.dias_totales} días. No es comparable
          con un mes cerrado.
        </p>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Tarjeta
          label="Ventas del mes"
          valor={formatARS(m.ventas.total_ars)}
          detalle={`B2B ${formatARS(m.ventas.b2b_ars)} · portal ${formatARS(m.ventas.portal_ars)}`}
          aviso={
            m.avisos.lineas_precio_cero
              ? `${m.avisos.lineas_precio_cero} líneas sin precio`
              : undefined
          }
        />
        <Tarjeta
          label="Compras del mes"
          valor={formatARS(m.compras_total_ars)}
          detalle="por fecha de recepción"
          aviso={
            m.avisos.lineas_compra_sin_precio
              ? `${m.avisos.lineas_compra_sin_precio} líneas sin precio`
              : undefined
          }
        />
        <Tarjeta
          label="Margen bruto"
          valor={m.margen.bruto_pct === null ? "—" : `${m.margen.bruto_pct.toFixed(1)}%`}
          detalle={
            m.margen.bruto_pct === null
              ? undefined
              : `${formatARS(m.margen.bruto_ars)} sobre costo ${formatARS(m.margen.cogs_ars)}`
          }
          /* El margen se mide solo sobre las ventas que se pudieron costear.
             Si no cubre todo el mes hay que decirlo: un 67% que en realidad
             describe el 90% de las ventas no es el margen del mes. */
          aviso={
            m.margen.cobertura_pct !== null && m.margen.cobertura_pct < 99.5
              ? `cubre ${m.margen.cobertura_pct.toFixed(0)}% de las ventas · ${m.margen.lineas_sin_costo} líneas sin costo`
              : undefined
          }
        />
        <Tarjeta
          label="Mermas del mes"
          valor={formatARS(m.mermas.total_ars)}
          detalle={
            m.mermas.pct_sobre_ventas !== null
              ? `${m.mermas.pct_sobre_ventas.toFixed(2)}% de las ventas · ${m.mermas.registros} registros`
              : `${m.mermas.registros} registros`
          }
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel titulo="Más vendidos" nota="unidades · $" vacio={!m.top_productos.length}>
          {m.top_productos.map((p) => (
            <Fila
              key={p.producto_id}
              nombre={p.nombre}
              sub={`${p.unidades.toLocaleString("es-AR")} u`}
              derecha={formatARS(p.monto_ars)}
            />
          ))}
        </Panel>

        <Panel titulo="En qué más gastamos" nota="ingredientes" vacio={!m.top_ingredientes.length}>
          {m.top_ingredientes.map((i) => (
            <Fila key={i.ingrediente_id} nombre={i.nombre} derecha={formatARS(i.monto_ars)} />
          ))}
        </Panel>

        <Panel titulo="Ventas por cliente" vacio={!m.por_cliente.length}>
          {m.por_cliente.map((c) => (
            <Fila
              key={c.cliente_id}
              nombre={c.nombre}
              sub={c.pct !== null ? `${c.pct.toFixed(1)}%` : undefined}
              derecha={formatARS(c.monto_ars)}
            />
          ))}
        </Panel>

        <Panel titulo="Gasto por proveedor" vacio={!m.por_proveedor.length}>
          {m.por_proveedor.map((p) => (
            <Fila key={p.proveedor_id} nombre={p.nombre} derecha={formatARS(p.monto_ars)} />
          ))}
        </Panel>

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
              derecha={c.variacion_pct !== null ? `${c.variacion_pct > 0 ? "+" : ""}${c.variacion_pct.toFixed(1)}%` : "—"}
            />
          ))}
        </Panel>
      </div>

      <p className="text-xs text-warm-gray mt-3">
        Las ventas son solo B2B y portal: el mostrador no se registra en el sistema, así
        que el total real es mayor. El margen usa el costo congelado al entregar y, para
        las ventas anteriores, el precio de cada ingrediente a esa fecha.
      </p>
    </div>
  );
}
