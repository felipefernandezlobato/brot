"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatARS, formatDate } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

// ── Types ────────────────────────────────────────────────────────────────────

interface LineaRecetaOut {
  id: number;
  ingrediente_id: number | null;
  subreceta_id: number | null;
  cantidad: number;
  unidad: string;
  nombre: string;
  costo_linea: number;
}

interface RecetaOut {
  id: number;
  nombre: string;
  categoria_id: number;
  categoria_nombre: string;
  porciones_por_lote: number;
  precio_venta: number | null;
  es_subreceta: boolean;
  unidad_rendimiento: string | null;
  notas: string | null;
  costo_total: number;
  costo_por_porcion: number;
  margen: number | null;
  multi: number | null;
  lineas: LineaRecetaOut[];
}

interface ProductoInfo {
  id: number;
  nombre: string;
  nivel: string;
  categoria: string;
  unidad: string;
  cantidad_por_padre: number | null;
}

interface CompletoData {
  receta: RecetaOut;
  producto: ProductoInfo | null;
  stock_actual: number;
  stock_history: { fecha: string; cantidad: number }[];
  movimientos: {
    id: number;
    tipo_movimiento: string;
    cantidad: number;
    fecha: string;
    referencia_origen: string | null;
    nombre_origen: string | null;
    saldo_despues: number | null;
  }[];
  ancestors: { id: number; nombre: string; nivel: string; receta_id: number | null; cantidad_por_padre: number | null }[];
  padre: { id: number; nombre: string; nivel: string; receta_id: number | null } | null;
  hijos: { id: number; nombre: string; nivel: string; cantidad_por_padre: number | null; receta_id: number | null; hijos?: any[] }[];
  usado_en: { id: number; nombre: string }[];
  consume_productos: { id: number; nombre: string; nivel: string; cantidad: number | null; receta_id: number | null }[];
}

const NIVEL_COLORS: Record<string, string> = {
  masa: "bg-purple-100 text-purple-700 border-purple-200",
  semi: "bg-blue-100 text-blue-700 border-blue-200",
  crudo: "bg-amber-100 text-amber-700 border-amber-200",
  terminado: "bg-green-100 text-green-700 border-green-200",
};
const NIVEL_LABELS: Record<string, string> = {
  masa: "Masa", semi: "Semi", crudo: "Crudo", terminado: "Final",
};
const MOV_LABELS: Record<string, string> = {
  produccion_salida: "Producido", produccion_consumo: "Consumido",
  entrega_b2b: "Entrega B2B", merma: "Merma", carga_inicial: "Carga inicial",
};

function MargenBadge({ margen }: { margen: number | null }) {
  if (margen === null) return <span className="text-warm-gray">--</span>;
  const color = margen >= 60 ? "text-green-600" : margen >= 40 ? "text-amber-600" : "text-red-600";
  return <span className={`font-medium ${color}`}>{margen.toFixed(1)}%</span>;
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function RecetaCompletoPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const [data, setData] = useState<CompletoData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params?.id) return;
    apiFetch<CompletoData>(`/api/recetas/${params.id}/completo`)
      .then(setData)
      .catch(() => toast("Error al cargar", "error"))
      .finally(() => setLoading(false));
  }, [params?.id]);

  if (loading) return <div className="p-8 text-center text-warm-gray">Cargando...</div>;
  if (!data) return <div className="p-8 text-center text-warm-gray">Receta no encontrada.</div>;

  const { receta, producto, stock_actual, stock_history, movimientos, ancestors, padre, hijos, usado_en, consume_productos } = data;

  function TreeNode({ node }: { node: { id: number; nombre: string; nivel: string; cantidad_por_padre?: number | null; receta_id?: number | null; hijos?: any[] } }) {
    const color = NIVEL_COLORS[node.nivel] || "border-cream-dark";
    const children = node.hijos || [];
    return (
      <div className="flex items-start gap-1.5">
        <Link href={node.receta_id ? `/escandallos/${node.receta_id}` : `/congelados/${node.id}`}
          className={`px-2.5 py-1 rounded-lg border text-xs hover:opacity-80 whitespace-nowrap shrink-0 ${color}`}>
          {node.nombre}
          {node.cantidad_por_padre && <span className="opacity-60 ml-1">({node.cantidad_por_padre}u)</span>}
        </Link>
        {children.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-warm-gray text-xs shrink-0">→</span>
            {children.length === 1 ? (
              <TreeNode node={children[0]} />
            ) : (
              <div className="flex flex-col gap-1 border-l-2 border-cream-dark pl-2">
                {children.map((c: any) => (
                  <TreeNode key={c.id} node={c} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  const chartData = stock_history
    .sort((a, b) => a.fecha.localeCompare(b.fecha))
    .map((s, i, arr) => {
      let consumo = 0;
      if (i > 0) {
        const prev = arr[i - 1];
        const dias = (new Date(s.fecha).getTime() - new Date(prev.fecha).getTime()) / (1000 * 60 * 60 * 24);
        if (dias > 0) consumo = Math.max(0, Math.round(((prev.cantidad - s.cantidad) / dias) * 7 * 10) / 10);
      }
      return { fecha: s.fecha, stock: s.cantidad, consumo };
    });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push("/escandallos")} className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center">
            ← Escandallos
          </button>
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">{receta.nombre}</h1>
          {receta.es_subreceta && <span className="text-xs text-brot bg-brot/10 px-2 py-0.5 rounded-full">subreceta</span>}
          {producto && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${NIVEL_COLORS[producto.nivel] || "bg-cream text-warm-gray"}`}>
              {NIVEL_LABELS[producto.nivel] || producto.nivel}
            </span>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Costo / porcion</p>
          <p className="text-lg font-bold text-brot">{formatARS(receta.costo_por_porcion)}</p>
          <p className="text-xs text-warm-gray">{receta.porciones_por_lote} porciones/lote</p>
        </div>
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">PVP</p>
          <p className="text-lg font-bold text-text">{receta.precio_venta ? formatARS(receta.precio_venta) : "--"}</p>
        </div>
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Multi</p>
          <p className="text-lg font-bold text-text">{receta.multi ? `${receta.multi.toFixed(1)}x` : "--"}</p>
          <MargenBadge margen={receta.margen} />
        </div>
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Costo lote</p>
          <p className="text-lg font-bold text-text">{formatARS(receta.costo_total)}</p>
        </div>
        {producto && (
          <div className={`border rounded-xl p-4 ${stock_actual > 0 ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
            <p className="text-xs text-warm-gray">Stock actual</p>
            <p className="text-lg font-bold text-text">{stock_actual} {producto.unidad}</p>
          </div>
        )}
      </div>

      {/* Production chain */}
      {(ancestors.length > 0 || hijos.length > 0 || consume_productos.length > 0) && (
        <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
          <p className="text-xs font-medium text-warm-gray mb-3">Cadena de produccion completa</p>

          {/* Full chain visualization as tree */}
          <div className="flex items-start gap-1.5 overflow-x-auto pb-2 mb-3">
            {ancestors.map((a) => (
              <div key={a.id} className="flex items-center gap-1.5 shrink-0">
                <Link href={a.receta_id ? `/escandallos/${a.receta_id}` : `/congelados/${a.id}`}
                  className={`px-2.5 py-1 rounded-lg border text-xs hover:opacity-80 whitespace-nowrap ${NIVEL_COLORS[a.nivel] || "border-cream-dark"}`}>
                  {a.nombre}
                </Link>
                <span className="text-warm-gray text-xs">→</span>
              </div>
            ))}
            {producto && (
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="px-2.5 py-1 rounded-lg bg-brot text-white font-medium text-xs whitespace-nowrap">{producto.nombre}</span>
                {hijos.length > 0 && <span className="text-warm-gray text-xs">→</span>}
              </div>
            )}
            {hijos.length === 1 ? (
              <TreeNode node={hijos[0]} />
            ) : hijos.length > 1 ? (
              <div className="flex flex-col gap-1 border-l-2 border-cream-dark pl-2">
                {hijos.map((h) => <TreeNode key={h.id} node={h} />)}
              </div>
            ) : null}
          </div>

          {/* What it consumes from stock */}
          {(receta.lineas.filter(l => l.ingrediente_id).length > 0 || consume_productos.length > 0) && (
            <div className="pt-3 border-t border-cream-dark">
              <p className="text-xs text-warm-gray mb-1">Consume de stock</p>
              <div className="flex flex-wrap gap-1.5">
                {receta.lineas.filter(l => l.ingrediente_id).map((l) => (
                  <Link key={l.id} href={`/ingredientes/${l.ingrediente_id}`}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs hover:opacity-80">
                    {l.nombre} <span className="opacity-60">{l.cantidad}{l.unidad}</span>
                  </Link>
                ))}
                {consume_productos.map((p) => (
                  <Link key={p.id} href={p.receta_id ? `/escandallos/${p.receta_id}` : `/congelados/${p.id}`}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs hover:opacity-80 ${NIVEL_COLORS[p.nivel] || "bg-cream text-text border-cream-dark"}`}>
                    {p.nombre} {p.cantidad && <span className="opacity-60">{p.cantidad}u</span>}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {usado_en.length > 0 && (
            <div className="pt-3 border-t border-cream-dark">
              <p className="text-xs text-warm-gray mb-1">Usado en</p>
              <div className="flex flex-wrap gap-1.5">
                {usado_en.map((r) => (
                  <Link key={r.id} href={`/escandallos/${r.id}`}
                    className="px-2 py-0.5 rounded-lg bg-brot/10 border border-brot/20 text-brot text-xs hover:opacity-80">
                    {r.nombre}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Ingredients table */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
        <div className="px-4 py-3 border-b border-cream-dark">
          <h2 className="font-medium text-text text-sm">Ingredientes / Lineas de receta</h2>
        </div>
        {receta.lineas.length === 0 ? (
          <p className="p-4 text-center text-warm-gray text-sm">Sin ingredientes.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-cream-dark bg-cream/50">
                <th className="text-left px-4 py-2 font-medium text-warm-gray">Ingrediente</th>
                <th className="text-right px-3 py-2 font-medium text-warm-gray">Cantidad</th>
                <th className="text-left px-3 py-2 font-medium text-warm-gray">Unidad</th>
                <th className="text-right px-4 py-2 font-medium text-warm-gray">Costo</th>
              </tr>
            </thead>
            <tbody>
              {receta.lineas.map((l, idx) => (
                <tr key={l.id} className={idx < receta.lineas.length - 1 ? "border-b border-cream-dark" : ""}>
                  <td className="px-4 py-2">
                    {l.ingrediente_id ? (
                      <Link href={`/ingredientes/${l.ingrediente_id}`} className="text-text hover:text-brot hover:underline">{l.nombre}</Link>
                    ) : l.subreceta_id ? (
                      <Link href={`/escandallos/${l.subreceta_id}`} className="text-brot hover:underline">{l.nombre} <span className="text-xs text-warm-gray">(subreceta)</span></Link>
                    ) : l.nombre}
                  </td>
                  <td className="text-right px-3 py-2 text-text tabular-nums">{l.cantidad}</td>
                  <td className="px-3 py-2 text-warm-gray">{l.unidad}</td>
                  <td className="text-right px-4 py-2 text-text tabular-nums">{formatARS(l.costo_linea)}</td>
                </tr>
              ))}
              <tr className="border-t border-cream-dark bg-cream/30">
                <td colSpan={3} className="px-4 py-2 font-medium text-text">Total lote</td>
                <td className="text-right px-4 py-2 font-bold text-text">{formatARS(receta.costo_total)}</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      {/* Stock chart */}
      {chartData.length > 1 && (
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4">
          <h2 className="font-medium text-text mb-3">Evolucion de stock y consumo</h2>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8DFD3" />
              <XAxis dataKey="fecha" tick={{ fontSize: 11, fill: "#6B5E52" }}
                tickFormatter={(v: string) => new Date(v + "T00:00:00").toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" })} />
              <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#6B5E52" }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "#dc2626" }} />
              <Tooltip labelFormatter={(v) => formatDate(String(v))}
                contentStyle={{ borderRadius: "8px", border: "1px solid #E8DFD3", fontSize: "13px" }} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Bar yAxisId="right" dataKey="consumo" name="Consumo/sem" fill="#dc2626" opacity={0.3} barSize={16} />
              <Line yAxisId="left" type="monotone" dataKey="stock" name="Stock" stroke="#004225" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Movements */}
      {movimientos.length > 0 && (
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
          <div className="px-4 py-3 border-b border-cream-dark">
            <p className="text-sm font-medium text-text">Movimientos recientes</p>
          </div>
          <div className="divide-y divide-cream-dark max-h-[250px] overflow-y-auto">
            {movimientos.map((m) => {
              let label = MOV_LABELS[m.tipo_movimiento] || m.tipo_movimiento;
              if (m.tipo_movimiento === "produccion_consumo" && m.nombre_origen) {
                label = `Consumido para ${m.nombre_origen}`;
              } else if (m.tipo_movimiento === "produccion_salida" && producto?.nombre.toLowerCase().includes("baston")) {
                // "u" isn't a word — name what was actually produced when we know it.
                label = "bastones producidos";
              } else if (m.referencia_origen) {
                const parts = m.referencia_origen.split(":");
                if (parts[0] === "entrega_b2b" && parts.length >= 3) {
                  label = `Entrega B2B ${parts.slice(2).join(":")}`;
                } else if (parts[0] === "entrega_b2b") {
                  label = `Entrega B2B #${parts[1]}`;
                }
              }
              return (
                <div key={m.id} className="px-4 py-2 flex items-center justify-between gap-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium tabular-nums ${
                      m.cantidad > 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                    }`}>
                      {m.cantidad > 0 ? "+" : ""}{m.cantidad}
                    </span>
                    <span className="text-warm-gray">{label}</span>
                  </div>
                  <span className="text-xs text-warm-gray">{formatDate(m.fecha)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Notes */}
      {receta.notas && (
        <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
          <p className="text-xs font-medium text-warm-gray mb-1">Notas</p>
          <p className="text-sm text-text whitespace-pre-line">{receta.notas}</p>
        </div>
      )}

      {/* Delete */}
      <PermissionGate module="recetas" action="delete">
        <div className="bg-white rounded-xl border border-cream-dark p-4">
          <p className="text-xs text-warm-gray">Zona de peligro</p>
          <button
            onClick={() => {
              if (confirm(`¿Eliminar ${receta.nombre}?`)) {
                apiFetch(`/api/recetas/${receta.id}`, { method: "DELETE" })
                  .then(() => { toast("Receta eliminada"); router.push("/escandallos"); })
                  .catch(() => toast("Error al eliminar", "error"));
              }
            }}
            className="mt-2 px-4 py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-sm min-h-[44px]"
          >
            Eliminar receta
          </button>
        </div>
      </PermissionGate>
    </div>
  );
}
