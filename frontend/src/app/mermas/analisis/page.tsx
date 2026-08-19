"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS } from "@/lib/format";
import DateRangeShortcuts from "@/components/DateRangeShortcuts";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type Motivo = "caducado" | "dañado" | "produccion" | "otro";
type Agrupacion = "semana" | "mes";

interface PorMotivo {
  motivo: Motivo;
  count: number;
  coste_total: number;
}

interface PorCategoria {
  categoria: string;
  count: number;
  coste_total: number;
}

interface PuntoEvolucion {
  periodo: string;
  count: number;
  coste_total: number;
}

interface TopItem {
  nombre: string;
  count: number;
  coste_total: number;
}

interface Analisis {
  coste_total_global: number;
  total_registros: number;
  por_motivo: PorMotivo[];
  por_categoria: PorCategoria[];
  evolucion: PuntoEvolucion[];
  top_items: TopItem[];
}

const MOTIVO_LABELS: Record<Motivo, string> = {
  caducado: "Caducado",
  dañado: "Dañado",
  produccion: "Producción",
  otro: "Otro",
};

const MOTIVO_COLORS: Record<Motivo, string> = {
  caducado: "bg-amber-400",
  dañado: "bg-red-500",
  produccion: "bg-blue-400",
  otro: "bg-warm-gray",
};

const MOTIVO_TEXT_COLORS: Record<Motivo, string> = {
  caducado: "text-amber-700",
  dañado: "text-red-700",
  produccion: "text-blue-700",
  otro: "text-warm-gray",
};

function getDefaultDates() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return {
    desde: from.toISOString().slice(0, 10),
    hasta: to.toISOString().slice(0, 10),
  };
}

export default function MermasAnalisisPage() {
  const router = useRouter();
  const { toast } = useToast();

  const defaults = getDefaultDates();
  const [analisis, setAnalisis] = useState<Analisis | null>(null);
  const [loading, setLoading] = useState(true);
  const [fechaDesde, setFechaDesde] = useState(defaults.desde);
  const [fechaHasta, setFechaHasta] = useState(defaults.hasta);
  const [agrupacion, setAgrupacion] = useState<Agrupacion>("semana");

  const fetchAnalisis = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (fechaDesde) params.set("fecha_desde", fechaDesde);
    if (fechaHasta) params.set("fecha_hasta", fechaHasta);
    params.set("agrupacion", agrupacion);
    apiFetch<Analisis>(`/api/mermas/analisis?${params}`)
      .then(setAnalisis)
      .catch(() => toast("Error al cargar análisis", "error"))
      .finally(() => setLoading(false));
  }, [fechaDesde, fechaHasta, agrupacion]);

  useEffect(() => {
    fetchAnalisis();
  }, [fetchAnalisis]);

  const maxCoste =
    analisis && analisis.por_motivo.length > 0
      ? Math.max(...analisis.por_motivo.map((m) => m.coste_total))
      : 1;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <button
          onClick={() => router.push("/mermas")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Análisis de Mermas
        </h1>
      </div>

      {/* Date range filter */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-6">
        <DateRangeShortcuts
          fechaDesde={fechaDesde}
          fechaHasta={fechaHasta}
          onChange={(desde, hasta) => {
            setFechaDesde(desde);
            setFechaHasta(hasta);
          }}
        />
      </div>

      {loading ? (
        <div className="p-8 text-center text-warm-gray">Cargando...</div>
      ) : analisis ? (
        <div className="space-y-6">
          {/* KPI cards */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <p className="text-xs font-medium text-warm-gray uppercase tracking-wide mb-1">
                Coste total
              </p>
              <p className="font-[family-name:var(--font-garamond)] text-3xl text-red-700">
                {formatARS(analisis.coste_total_global)}
              </p>
            </div>
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <p className="text-xs font-medium text-warm-gray uppercase tracking-wide mb-1">
                Registros
              </p>
              <p className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
                {analisis.total_registros}
              </p>
            </div>
          </div>

          {/* Evolucion — coste total por semana/mes */}
          <div className="bg-white rounded-xl border border-cream-dark p-5">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h2 className="font-medium text-text">Evolución</h2>
              <div className="flex gap-1 bg-cream rounded-lg p-1">
                {(["semana", "mes"] as Agrupacion[]).map((a) => (
                  <button
                    key={a}
                    onClick={() => setAgrupacion(a)}
                    className={`px-3 py-1 rounded-md text-xs font-medium transition-colors min-h-[32px] ${
                      agrupacion === a
                        ? "bg-brot text-white"
                        : "text-warm-gray hover:text-brot"
                    }`}
                  >
                    {a === "semana" ? "Semana" : "Mes"}
                  </button>
                ))}
              </div>
            </div>
            {analisis.evolucion.length === 0 ? (
              <p className="text-warm-gray text-sm">Sin datos</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={analisis.evolucion}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E8DFD3" vertical={false} />
                  <XAxis
                    dataKey="periodo"
                    tick={{ fontSize: 11, fill: "#6B5E52" }}
                    tickFormatter={(v: string) => {
                      const d = new Date(v + "T00:00:00");
                      return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
                    }}
                  />
                  <YAxis tick={{ fontSize: 11, fill: "#6B5E52" }} width={70} tickFormatter={(v) => formatARS(v)} />
                  <Tooltip
                    labelFormatter={(v) => {
                      const d = new Date(String(v) + "T00:00:00");
                      const prefijo = agrupacion === "semana" ? "Semana del " : "";
                      return prefijo + d.toLocaleDateString("es-AR", agrupacion === "mes" ? { month: "long", year: "numeric" } : { day: "2-digit", month: "2-digit", year: "numeric" });
                    }}
                    formatter={(value, _name, item: any) => [
                      `${formatARS(Number(value))} (${item?.payload?.count ?? 0} reg.)`,
                      "Coste",
                    ]}
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid #E8DFD3",
                      fontSize: "13px",
                    }}
                  />
                  <Bar dataKey="coste_total" fill="#004225" radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* By motivo — horizontal bar chart */}
          <div className="bg-white rounded-xl border border-cream-dark p-5">
            <h2 className="font-medium text-text mb-4">Por motivo</h2>
            {analisis.por_motivo.length === 0 ? (
              <p className="text-warm-gray text-sm">Sin datos</p>
            ) : (
              <div className="space-y-4">
                {analisis.por_motivo
                  .slice()
                  .sort((a, b) => b.coste_total - a.coste_total)
                  .map((pm) => {
                    const pct =
                      maxCoste > 0
                        ? Math.round((pm.coste_total / maxCoste) * 100)
                        : 0;
                    return (
                      <div key={pm.motivo}>
                        <div className="flex items-center justify-between mb-1.5">
                          <span
                            className={`text-sm font-medium ${
                              MOTIVO_TEXT_COLORS[pm.motivo]
                            }`}
                          >
                            {MOTIVO_LABELS[pm.motivo]}
                          </span>
                          <div className="text-right">
                            <span className="text-sm font-medium text-text">
                              {formatARS(pm.coste_total)}
                            </span>
                            <span className="text-xs text-warm-gray ml-2">
                              {pm.count} reg.
                            </span>
                          </div>
                        </div>
                        <div className="h-2.5 rounded-full bg-cream-dark overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              MOTIVO_COLORS[pm.motivo]
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}

            {/* Percentage breakdown */}
            {analisis.por_motivo.length > 0 &&
              analisis.coste_total_global > 0 && (
                <div className="mt-5 pt-4 border-t border-cream-dark">
                  <div className="flex gap-2 flex-wrap">
                    {analisis.por_motivo
                      .slice()
                      .sort((a, b) => b.coste_total - a.coste_total)
                      .map((pm) => {
                        const pct = Math.round(
                          (pm.coste_total / analisis.coste_total_global) * 100
                        );
                        return (
                          <div
                            key={pm.motivo}
                            className="flex items-center gap-1.5 text-xs text-warm-gray"
                          >
                            <span
                              className={`inline-block w-2.5 h-2.5 rounded-full ${MOTIVO_COLORS[pm.motivo]}`}
                            />
                            {MOTIVO_LABELS[pm.motivo]}: {pct}%
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
          </div>

          {/* By category — horizontal bar chart, one hue (ranked magnitude, not a
              fixed enum like motivo, so no per-category color assignment) */}
          <div className="bg-white rounded-xl border border-cream-dark p-5">
            <h2 className="font-medium text-text mb-4">Por categoría</h2>
            {analisis.por_categoria.length === 0 ? (
              <p className="text-warm-gray text-sm">Sin datos</p>
            ) : (
              <div className="space-y-4">
                {(() => {
                  const maxCosteCategoria = Math.max(...analisis.por_categoria.map((c) => c.coste_total));
                  return analisis.por_categoria.map((pc) => {
                    const pct = maxCosteCategoria > 0 ? Math.round((pc.coste_total / maxCosteCategoria) * 100) : 0;
                    return (
                      <div key={pc.categoria}>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-sm font-medium text-text">{pc.categoria}</span>
                          <div className="text-right">
                            <span className="text-sm font-medium text-text">{formatARS(pc.coste_total)}</span>
                            <span className="text-xs text-warm-gray ml-2">{pc.count} reg.</span>
                          </div>
                        </div>
                        <div className="h-2.5 rounded-full bg-cream-dark overflow-hidden">
                          <div
                            className="h-full rounded-full bg-brot transition-all duration-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            )}
          </div>

          {/* Top items */}
          <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
            <div className="px-5 py-4 border-b border-cream-dark">
              <h2 className="font-medium text-text">Top ítems con más merma</h2>
            </div>
            {analisis.top_items.length === 0 ? (
              <p className="text-warm-gray text-sm p-5">Sin datos</p>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-cream-dark bg-cream/50">
                        <th className="text-left px-5 py-3 font-medium text-warm-gray">
                          #
                        </th>
                        <th className="text-left px-4 py-3 font-medium text-warm-gray">
                          Ítem
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">
                          Registros
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">
                          Coste total
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {analisis.top_items.map((item, idx) => (
                        <tr
                          key={item.nombre}
                          className={
                            idx < analisis.top_items.length - 1
                              ? "border-b border-cream-dark"
                              : ""
                          }
                        >
                          <td className="px-5 py-3 text-warm-gray text-xs">
                            {idx + 1}
                          </td>
                          <td className="px-4 py-3 font-medium text-text">
                            {item.nombre}
                          </td>
                          <td className="px-4 py-3 text-right text-warm-gray">
                            {item.count}
                          </td>
                          <td className="px-4 py-3 text-right font-medium text-red-700">
                            {item.coste_total > 0
                              ? formatARS(item.coste_total)
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile list */}
                <div className="md:hidden divide-y divide-cream-dark">
                  {analisis.top_items.map((item, idx) => (
                    <div key={item.nombre} className="px-5 py-4">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-warm-gray w-5">
                              {idx + 1}.
                            </span>
                            <p className="font-medium text-text">{item.nombre}</p>
                          </div>
                          <p className="text-xs text-warm-gray mt-0.5 ml-7">
                            {item.count} reg.
                          </p>
                        </div>
                        <p className="text-sm font-medium text-red-700 shrink-0">
                          {item.coste_total > 0
                            ? formatARS(item.coste_total)
                            : "—"}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="p-8 text-center text-warm-gray">
          No se pudo cargar el análisis.
        </div>
      )}
    </div>
  );
}
