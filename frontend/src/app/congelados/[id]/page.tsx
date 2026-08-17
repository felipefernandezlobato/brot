"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";
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

interface ProductoDetalle {
  id: number;
  nombre: string;
  categoria: string;
  unidad: string;
  nivel: string;
  cantidad_por_padre: number | null;
  stock_actual: number;
  ancestors: { id: number; nombre: string; nivel: string; unidad: string; receta_id?: number | null; cantidad_por_padre?: number | null }[];
  padre: { id: number; nombre: string; nivel: string; unidad: string; receta_id?: number | null } | null;
  hijos: { id: number; nombre: string; nivel: string; cantidad_por_padre: number | null; receta_id?: number | null; hijos?: any[] }[];
  receta: { id: number; nombre: string; porciones_por_lote: number; costo_total: number; costo_porcion: number; precio_venta: number | null; num_ingredientes: number } | null;
  stock_history: { fecha: string; cantidad: number }[];
  movimientos: { id: number; tipo_movimiento: string; cantidad: number; fecha: string; referencia_origen: string | null; nombre_origen: string | null; saldo_despues: number | null }[];
}

const NIVEL_COLORS: Record<string, string> = {
  masa: "bg-purple-100 text-purple-700 border-purple-200",
  semi: "bg-blue-100 text-blue-700 border-blue-200",
  crudo: "bg-amber-100 text-amber-700 border-amber-200",
  terminado: "bg-green-100 text-green-700 border-green-200",
};
const NIVEL_LABELS: Record<string, string> = { masa: "Masa", semi: "Semi", crudo: "Crudo", terminado: "Final" };
const MOV_LABELS: Record<string, string> = { produccion_salida: "Producido", produccion_consumo: "Consumido", entrega_b2b: "Entrega B2B", merma: "Merma" };

export default function CongeladoPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const [data, setData] = useState<ProductoDetalle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params?.id) return;
    apiFetch<ProductoDetalle>(`/api/congelados/productos/${params.id}/detalle`)
      .then((d) => {
        if (d.receta?.id) {
          router.replace(`/escandallos/${d.receta.id}`);
        } else {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => { toast("Error al cargar", "error"); setLoading(false); });
  }, [params?.id, router]);

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

  if (loading) return <div className="p-8 text-center text-warm-gray">Cargando...</div>;
  if (!data) return <div className="p-8 text-center text-warm-gray">Producto no encontrado.</div>;

  const chartData = data.stock_history
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
      <div className="flex items-center gap-3 mb-6">
        <Link href="/congelados" className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center">
          ← Stock Congelado
        </Link>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">{data.nombre}</h1>
        <span className={`text-xs px-2 py-0.5 rounded-full ${NIVEL_COLORS[data.nivel] || "bg-cream text-warm-gray"}`}>
          {NIVEL_LABELS[data.nivel] || data.nivel}
        </span>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <div className={`border rounded-xl p-4 ${data.stock_actual > 0 ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
          <p className="text-xs text-warm-gray">Stock actual</p>
          <p className="text-lg font-bold text-text">{data.stock_actual} {data.unidad}</p>
        </div>
        {data.padre && (
          <div className="bg-white border border-cream-dark rounded-xl p-4">
            <p className="text-xs text-warm-gray">Consume</p>
            <Link href={data.padre.receta_id ? `/escandallos/${data.padre.receta_id}` : `/congelados/${data.padre.id}`}
              className="text-sm font-medium text-brot hover:underline">{data.padre.nombre}</Link>
          </div>
        )}
        {data.hijos.length > 0 && (
          <div className="bg-white border border-cream-dark rounded-xl p-4">
            <p className="text-xs text-warm-gray">Produce</p>
            <p className="text-sm font-medium text-text">{data.hijos.map(h => h.nombre).join(", ")}</p>
          </div>
        )}
      </div>

      {/* Full chain as tree */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
        <p className="text-xs font-medium text-warm-gray mb-2">Cadena de produccion completa</p>
        <div className="flex items-start gap-1.5 overflow-x-auto pb-2">
          {data.ancestors.map((a) => (
            <div key={a.id} className="flex items-center gap-1.5 shrink-0">
              <Link href={a.receta_id ? `/escandallos/${a.receta_id}` : `/congelados/${a.id}`}
                className={`px-2.5 py-1 rounded-lg border text-xs hover:opacity-80 whitespace-nowrap ${NIVEL_COLORS[a.nivel] || "border-cream-dark"}`}>
                {a.nombre}
              </Link>
              <span className="text-warm-gray text-xs">→</span>
            </div>
          ))}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="px-2.5 py-1 rounded-lg bg-brot text-white font-medium text-xs whitespace-nowrap">{data.nombre}</span>
            {data.hijos.length > 0 && <span className="text-warm-gray text-xs">→</span>}
          </div>
          {data.hijos.length === 1 ? (
            <TreeNode node={data.hijos[0]} />
          ) : data.hijos.length > 1 ? (
            <div className="flex flex-col gap-1 border-l-2 border-cream-dark pl-2">
              {data.hijos.map((h) => <TreeNode key={h.id} node={h} />)}
            </div>
          ) : null}
        </div>
      </div>

      {/* Chart */}
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
      {data.movimientos.length > 0 && (
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
          <div className="px-4 py-3 border-b border-cream-dark">
            <p className="text-sm font-medium text-text">Movimientos recientes</p>
          </div>
          <div className="divide-y divide-cream-dark max-h-[250px] overflow-y-auto">
            {data.movimientos.map((m) => {
              let label = MOV_LABELS[m.tipo_movimiento] || m.tipo_movimiento;
              if (m.tipo_movimiento === "produccion_consumo" && m.nombre_origen) {
                label = `Consumido para ${m.nombre_origen}`;
              } else if (m.tipo_movimiento === "produccion_salida" && data.nombre.toLowerCase().includes("baston")) {
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
                    }`}>{m.cantidad > 0 ? "+" : ""}{m.cantidad}</span>
                    <span className="text-warm-gray">{label}</span>
                  </div>
                  <span className="text-xs text-warm-gray">{formatDate(m.fecha)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
