"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface CalendarioRaw {
  fecha: string;
  day_of_week: number;
  producto_id: number;
  planned_qty: number | null;
  actual_qty: number | null;
}

interface Producto {
  id: number;
  nombre: string;
  unidad: string;
}

interface ProductRow {
  producto_id: number;
  nombre: string;
  planificado: number;
  producido: number;
  diferencia: number;
  cumplimiento: number | null;
}

interface DayBar {
  fecha: string;
  label: string;
  total: number;
}

type RangePreset = "this_week" | "last_week" | "this_month" | "last_month" | "custom";

const PRESET_LABELS: Record<RangePreset, string> = {
  this_week: "Esta semana",
  last_week: "Semana pasada",
  this_month: "Este mes",
  last_month: "Mes pasado",
  custom: "Personalizado",
};

const DAY_SHORT = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function getRangeForPreset(preset: RangePreset): { desde: string; hasta: string } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  switch (preset) {
    case "this_week": {
      const monday = getMonday(today);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      return { desde: formatDate(monday), hasta: formatDate(sunday) };
    }
    case "last_week": {
      const thisMonday = getMonday(today);
      const lastMonday = new Date(thisMonday);
      lastMonday.setDate(thisMonday.getDate() - 7);
      const lastSunday = new Date(lastMonday);
      lastSunday.setDate(lastMonday.getDate() + 6);
      return { desde: formatDate(lastMonday), hasta: formatDate(lastSunday) };
    }
    case "this_month": {
      const from = new Date(today.getFullYear(), today.getMonth(), 1);
      const to = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      return { desde: formatDate(from), hasta: formatDate(to) };
    }
    case "last_month": {
      const from = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const to = new Date(today.getFullYear(), today.getMonth(), 0);
      return { desde: formatDate(from), hasta: formatDate(to) };
    }
    default: {
      const monday = getMonday(today);
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      return { desde: formatDate(monday), hasta: formatDate(sunday) };
    }
  }
}

export default function ProduccionAnalyticsPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [preset, setPreset] = useState<RangePreset>("this_week");
  const initial = getRangeForPreset("this_week");
  const [fechaDesde, setFechaDesde] = useState(initial.desde);
  const [fechaHasta, setFechaHasta] = useState(initial.hasta);
  const [loading, setLoading] = useState(true);

  const [rows, setRows] = useState<ProductRow[]>([]);
  const [dayBars, setDayBars] = useState<DayBar[]>([]);
  const [totalProducido, setTotalProducido] = useState(0);
  const [totalPlanificado, setTotalPlanificado] = useState(0);

  function applyPreset(p: RangePreset) {
    setPreset(p);
    if (p !== "custom") {
      const range = getRangeForPreset(p);
      setFechaDesde(range.desde);
      setFechaHasta(range.hasta);
    }
  }

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [rawEntries, productos] = await Promise.all([
        apiFetch<CalendarioRaw[]>(
          `/api/produccion/calendario?fecha_desde=${fechaDesde}&fecha_hasta=${fechaHasta}`
        ),
        apiFetch<Producto[]>("/api/produccion/productos"),
      ]);

      const prodMap = new Map(productos.map((p) => [p.id, p]));

      // Per-product aggregation
      const productAgg = new Map<number, { planificado: number; producido: number }>();
      for (const entry of rawEntries) {
        if (!productAgg.has(entry.producto_id)) {
          productAgg.set(entry.producto_id, { planificado: 0, producido: 0 });
        }
        const agg = productAgg.get(entry.producto_id)!;
        agg.planificado += entry.planned_qty ?? 0;
        agg.producido += entry.actual_qty ?? 0;
      }

      const productRows: ProductRow[] = Array.from(productAgg.entries())
        .map(([id, agg]) => {
          const prod = prodMap.get(id);
          const diferencia = agg.producido - agg.planificado;
          const cumplimiento =
            agg.planificado > 0
              ? Math.round((agg.producido / agg.planificado) * 100)
              : null;
          return {
            producto_id: id,
            nombre: prod?.nombre ?? `Producto ${id}`,
            planificado: agg.planificado,
            producido: agg.producido,
            diferencia,
            cumplimiento,
          };
        })
        .sort((a, b) => b.producido - a.producido);

      setRows(productRows);

      // Per-day aggregation for bar chart
      const dayAgg = new Map<string, number>();
      for (const entry of rawEntries) {
        const prev = dayAgg.get(entry.fecha) ?? 0;
        dayAgg.set(entry.fecha, prev + (entry.actual_qty ?? 0));
      }

      // Generate all dates in the selected range
      const bars: DayBar[] = [];
      const start = new Date(fechaDesde + "T00:00:00");
      const end = new Date(fechaHasta + "T00:00:00");
      for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const dateStr = formatDate(d);
        const dow = d.getDay(); // 0=Sun
        const dayIdx = dow === 0 ? 6 : dow - 1; // 0=Mon … 6=Sun
        bars.push({
          fecha: dateStr,
          label: DAY_SHORT[dayIdx] + " " + d.getDate(),
          total: dayAgg.get(dateStr) ?? 0,
        });
      }

      setDayBars(bars);

      const totPlan = productRows.reduce((s, r) => s + r.planificado, 0);
      const totProd = productRows.reduce((s, r) => s + r.producido, 0);
      setTotalPlanificado(totPlan);
      setTotalProducido(totProd);
    } catch {
      toast("Error al cargar el análisis de producción", "error");
    } finally {
      setLoading(false);
    }
  }, [fechaDesde, fechaHasta]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const cumplimientoGlobal =
    totalPlanificado > 0
      ? Math.round((totalProducido / totalPlanificado) * 100)
      : null;

  const maxDayTotal = dayBars.length > 0 ? Math.max(...dayBars.map((b) => b.total), 1) : 1;

  function cumplimientoColor(pct: number | null): string {
    if (pct === null) return "text-warm-gray";
    if (pct >= 90) return "text-green-600";
    if (pct >= 70) return "text-amber-600";
    return "text-red-600";
  }

  function cumplimientoBarColor(pct: number | null): string {
    if (pct === null) return "bg-warm-gray";
    if (pct >= 90) return "bg-green-500";
    if (pct >= 70) return "bg-amber-400";
    return "bg-red-400";
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <button
          onClick={() => router.push("/produccion")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <div className="flex-1">
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Análisis de Producción
          </h1>
          <p className="text-sm text-warm-gray mt-0.5">
            Planificado vs. producido por período
          </p>
        </div>
      </div>

      {/* Date range selector */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-6">
        <div className="flex gap-2 flex-wrap mb-3">
          {(["this_week", "last_week", "this_month", "last_month"] as RangePreset[]).map(
            (p) => (
              <button
                key={p}
                onClick={() => applyPreset(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors min-h-[34px] ${
                  preset === p
                    ? "bg-brot text-white border-brot"
                    : "bg-white border-cream-dark text-warm-gray hover:bg-cream hover:text-text"
                }`}
              >
                {PRESET_LABELS[p]}
              </button>
            )
          )}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Desde
            </label>
            <input
              type="date"
              value={fechaDesde}
              onChange={(e) => {
                setFechaDesde(e.target.value);
                setPreset("custom");
              }}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Hasta
            </label>
            <input
              type="date"
              value={fechaHasta}
              onChange={(e) => {
                setFechaHasta(e.target.value);
                setPreset("custom");
              }}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] text-sm"
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-warm-gray">Cargando...</div>
      ) : (
        <div className="space-y-6">
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <p className="text-xs font-medium text-warm-gray uppercase tracking-wide mb-1">
                Producido
              </p>
              <p className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
                {totalProducido.toLocaleString("es-AR")}
              </p>
              <p className="text-xs text-warm-gray mt-0.5">unidades</p>
            </div>
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <p className="text-xs font-medium text-warm-gray uppercase tracking-wide mb-1">
                Planificado
              </p>
              <p className="font-[family-name:var(--font-garamond)] text-3xl text-text">
                {totalPlanificado.toLocaleString("es-AR")}
              </p>
              <p className="text-xs text-warm-gray mt-0.5">unidades</p>
            </div>
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <p className="text-xs font-medium text-warm-gray uppercase tracking-wide mb-1">
                Cumplimiento
              </p>
              <p
                className={`font-[family-name:var(--font-garamond)] text-3xl ${cumplimientoColor(cumplimientoGlobal)}`}
              >
                {cumplimientoGlobal !== null ? `${cumplimientoGlobal}%` : "—"}
              </p>
              <p className="text-xs text-warm-gray mt-0.5">actual / plan</p>
            </div>
          </div>

          {/* Daily bar chart */}
          {dayBars.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <h2 className="font-medium text-text mb-4">Producción por día</h2>
              <div className="overflow-x-auto">
                <div className="flex items-end gap-1.5 min-w-max">
                  {dayBars.map((bar) => {
                    const pct =
                      maxDayTotal > 0 ? (bar.total / maxDayTotal) * 100 : 0;
                    return (
                      <div
                        key={bar.fecha}
                        className="flex flex-col items-center"
                        style={{ width: "40px" }}
                      >
                        <span className="text-[10px] text-warm-gray mb-0.5 h-4 flex items-center justify-center">
                          {bar.total > 0 ? bar.total : ""}
                        </span>
                        {/* Bar track */}
                        <div
                          className="w-full rounded-t-sm bg-cream-dark"
                          style={{
                            height: "80px",
                            display: "flex",
                            flexDirection: "column",
                            justifyContent: "flex-end",
                          }}
                        >
                          <div
                            className="w-full rounded-t-sm bg-brot transition-all duration-500"
                            style={{
                              height: `${pct}%`,
                              minHeight: bar.total > 0 ? "2px" : "0",
                            }}
                          />
                        </div>
                        <p className="text-[10px] text-warm-gray text-center mt-0.5 leading-tight">
                          {bar.label}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* Per-product table */}
          <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
            <div className="px-5 py-4 border-b border-cream-dark">
              <h2 className="font-medium text-text">Por producto</h2>
            </div>
            {rows.length === 0 ? (
              <p className="text-warm-gray text-sm p-5">
                Sin datos para el período seleccionado.
              </p>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-cream-dark bg-cream/50">
                        <th className="text-left px-5 py-3 font-medium text-warm-gray">
                          Producto
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">
                          Planificado
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">
                          Producido
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">
                          Diferencia
                        </th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">
                          % Cumplimiento
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, idx) => (
                        <tr
                          key={row.producto_id}
                          className={
                            idx < rows.length - 1
                              ? "border-b border-cream-dark"
                              : ""
                          }
                        >
                          <td className="px-5 py-3 font-medium text-text">
                            {row.nombre}
                          </td>
                          <td className="px-4 py-3 text-right text-warm-gray">
                            {row.planificado}
                          </td>
                          <td className="px-4 py-3 text-right font-medium text-text">
                            {row.producido}
                          </td>
                          <td
                            className={`px-4 py-3 text-right font-medium ${
                              row.diferencia >= 0
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {row.diferencia > 0
                              ? `+${row.diferencia}`
                              : row.diferencia}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {row.cumplimiento !== null ? (
                              <span
                                className={`font-medium ${cumplimientoColor(row.cumplimiento)}`}
                              >
                                {row.cumplimiento}%
                              </span>
                            ) : (
                              <span className="text-warm-gray">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile list */}
                <div className="md:hidden divide-y divide-cream-dark">
                  {rows.map((row) => (
                    <div key={row.producto_id} className="px-4 py-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <p className="font-medium text-text text-sm">
                          {row.nombre}
                        </p>
                        {row.cumplimiento !== null ? (
                          <span
                            className={`text-sm font-medium ${cumplimientoColor(row.cumplimiento)}`}
                          >
                            {row.cumplimiento}%
                          </span>
                        ) : (
                          <span className="text-warm-gray text-sm">—</span>
                        )}
                      </div>
                      <div className="flex gap-4 text-xs text-warm-gray">
                        <span>
                          Plan:{" "}
                          <span className="text-text">{row.planificado}</span>
                        </span>
                        <span>
                          Real:{" "}
                          <span className="text-text">{row.producido}</span>
                        </span>
                        <span>
                          Dif:{" "}
                          <span
                            className={
                              row.diferencia >= 0
                                ? "text-green-600"
                                : "text-red-600"
                            }
                          >
                            {row.diferencia > 0
                              ? `+${row.diferencia}`
                              : row.diferencia}
                          </span>
                        </span>
                      </div>
                      {row.planificado > 0 && (
                        <div className="mt-2 h-1.5 rounded-full bg-cream-dark overflow-hidden">
                          <div
                            className={`h-full rounded-full ${cumplimientoBarColor(row.cumplimiento)}`}
                            style={{
                              width: `${Math.min(row.cumplimiento ?? 0, 100)}%`,
                            }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
