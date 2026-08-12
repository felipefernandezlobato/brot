"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS, formatDate } from "@/lib/format";
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
  padre: { id: number; nombre: string; nivel: string; unidad: string } | null;
  hijos: { id: number; nombre: string; nivel: string; cantidad_por_padre: number | null }[];
  receta: {
    id: number;
    nombre: string;
    porciones_por_lote: number;
    costo_total: number;
    costo_porcion: number;
    precio_venta: number | null;
    num_ingredientes: number;
  } | null;
  stock_history: { fecha: string; cantidad: number }[];
  movimientos: {
    id: number;
    tipo_movimiento: string;
    cantidad: number;
    fecha: string;
    referencia_origen: string | null;
    saldo_despues: number | null;
  }[];
}

const NIVEL_LABELS: Record<string, string> = {
  masa: "Masa",
  semi: "Semi-elaborado",
  crudo: "Crudo",
  terminado: "Terminado",
};

const NIVEL_COLORS: Record<string, string> = {
  masa: "bg-purple-100 text-purple-700",
  semi: "bg-blue-100 text-blue-700",
  crudo: "bg-amber-100 text-amber-700",
  terminado: "bg-green-100 text-green-700",
};

const MOV_LABELS: Record<string, string> = {
  produccion_salida: "Producido",
  produccion_consumo: "Consumido",
  entrega_b2b: "Entrega B2B",
  merma: "Merma",
};

export default function ProductoDetallePage() {
  const params = useParams<{ id: string }>();
  const { toast } = useToast();
  const [data, setData] = useState<ProductoDetalle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params?.id) return;
    apiFetch<ProductoDetalle>(`/api/congelados/productos/${params.id}/detalle`)
      .then(setData)
      .catch(() => toast("Error al cargar producto", "error"))
      .finally(() => setLoading(false));
  }, [params?.id]);

  if (loading) return <div className="p-8 text-center text-warm-gray">Cargando...</div>;
  if (!data) return <div className="p-8 text-center text-warm-gray">Producto no encontrado.</div>;

  const chartData = data.stock_history
    .sort((a, b) => a.fecha.localeCompare(b.fecha))
    .map((s, i, arr) => {
      let consumo = 0;
      if (i > 0) {
        const prev = arr[i - 1];
        const dias = (new Date(s.fecha).getTime() - new Date(prev.fecha).getTime()) / (1000 * 60 * 60 * 24);
        if (dias > 0) {
          const diff = prev.cantidad - s.cantidad;
          consumo = Math.max(0, Math.round((diff / dias) * 7 * 10) / 10);
        }
      }
      return { fecha: s.fecha, stock: s.cantidad, consumo };
    });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          href="/congelados"
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Stock Congelado
        </Link>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          {data.nombre}
        </h1>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${NIVEL_COLORS[data.nivel] || "bg-cream text-warm-gray"}`}>
          {NIVEL_LABELS[data.nivel] || data.nivel}
        </span>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Stock actual</p>
          <p className="text-lg font-bold text-text">{data.stock_actual} {data.unidad}</p>
        </div>
        {data.receta && (
          <>
            <div className="bg-white border border-brot/30 rounded-xl p-4">
              <p className="text-xs text-warm-gray">Costo / {data.unidad}</p>
              <p className="text-lg font-bold text-brot">{formatARS(data.receta.costo_porcion)}</p>
            </div>
            {data.receta.precio_venta && (
              <div className="bg-white border border-cream-dark rounded-xl p-4">
                <p className="text-xs text-warm-gray">PVP</p>
                <p className="text-lg font-bold text-text">{formatARS(data.receta.precio_venta)}</p>
              </div>
            )}
            {data.receta.precio_venta && data.receta.costo_porcion > 0 && (
              <div className="bg-white border border-cream-dark rounded-xl p-4">
                <p className="text-xs text-warm-gray">Multiplicador</p>
                <p className="text-lg font-bold text-text">x{(data.receta.precio_venta / data.receta.costo_porcion).toFixed(1)}</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Chain: padre -> this -> hijos */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
        <p className="text-xs font-medium text-warm-gray mb-3">Cadena de produccion</p>
        <div className="flex items-center gap-2 flex-wrap text-sm">
          {data.padre && (
            <>
              <Link href={`/congelados/${data.padre.id}`} className="px-3 py-1.5 rounded-lg border border-cream-dark hover:border-brot hover:text-brot transition-colors">
                {data.padre.nombre}
                <span className="text-xs text-warm-gray ml-1">({NIVEL_LABELS[data.padre.nivel]})</span>
              </Link>
              <span className="text-warm-gray">→</span>
              {data.cantidad_por_padre && (
                <span className="text-xs text-warm-gray">{data.cantidad_por_padre}u</span>
              )}
              <span className="text-warm-gray">→</span>
            </>
          )}
          <span className="px-3 py-1.5 rounded-lg bg-brot text-white font-medium">
            {data.nombre}
          </span>
          {data.hijos.length > 0 && (
            <>
              <span className="text-warm-gray">→</span>
              {data.hijos.map((h) => (
                <Link key={h.id} href={`/congelados/${h.id}`} className="px-3 py-1.5 rounded-lg border border-cream-dark hover:border-brot hover:text-brot transition-colors">
                  {h.nombre}
                  {h.cantidad_por_padre && <span className="text-xs text-warm-gray ml-1">({h.cantidad_por_padre}u)</span>}
                </Link>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Recipe */}
      {data.receta && (
        <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text">Receta: {data.receta.nombre}</p>
              <p className="text-xs text-warm-gray">
                {data.receta.porciones_por_lote} porciones/lote · {data.receta.num_ingredientes} ingredientes · Costo total: {formatARS(data.receta.costo_total)}
              </p>
            </div>
            <Link href={`/escandallos/${data.receta.id}`} className="text-sm text-brot hover:text-brot-dark transition-colors">
              Ver receta →
            </Link>
          </div>
        </div>
      )}

      {/* Stock chart */}
      {chartData.length > 1 && (
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4">
          <h2 className="font-medium text-text mb-3">Evolucion de stock y consumo</h2>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8DFD3" />
              <XAxis
                dataKey="fecha"
                tick={{ fontSize: 11, fill: "#6B5E52" }}
                tickFormatter={(v: string) => {
                  const d = new Date(v + "T00:00:00");
                  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
                }}
              />
              <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#6B5E52" }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "#dc2626" }} />
              <Tooltip
                labelFormatter={(v) => formatDate(String(v))}
                contentStyle={{ borderRadius: "8px", border: "1px solid #E8DFD3", fontSize: "13px" }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Bar yAxisId="right" dataKey="consumo" name="Consumo/sem" fill="#dc2626" opacity={0.3} barSize={16} />
              <Line yAxisId="left" type="monotone" dataKey="stock" name="Stock" stroke="#004225" strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recent movements */}
      {data.movimientos.length > 0 && (
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
          <div className="px-4 py-3 border-b border-cream-dark">
            <p className="text-sm font-medium text-text">Movimientos recientes</p>
          </div>
          <div className="divide-y divide-cream-dark max-h-[300px] overflow-y-auto">
            {data.movimientos.map((m) => (
              <div key={m.id} className="px-4 py-2.5 flex items-center justify-between gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                    m.cantidad > 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                  }`}>
                    {m.cantidad > 0 ? "+" : ""}{m.cantidad}
                  </span>
                  <span className="text-warm-gray">{MOV_LABELS[m.tipo_movimiento] || m.tipo_movimiento}</span>
                </div>
                <span className="text-xs text-warm-gray">{formatDate(m.fecha)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.movimientos.length === 0 && data.stock_history.length <= 1 && (
        <div className="bg-white rounded-xl border border-cream-dark p-6 text-center text-warm-gray text-sm">
          No hay movimientos registrados para este producto.
        </div>
      )}
    </div>
  );
}
