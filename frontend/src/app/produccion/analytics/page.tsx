"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

/* ─── Types ────────────────────────────────────────────────────────── */

interface Resumen {
  total_planificadas: number;
  total_completadas: number;
  porcentaje_cumplimiento: number;
  dias_registrados: number;
}

interface DiaStat {
  fecha: string;
  dia_nombre: string;
  planificadas: number;
  completadas: number;
  porcentaje: number;
}

interface TareaStat {
  tarea_id: number;
  titulo: string;
  cantidad_planificada: number | null;
  unidad_cantidad: string | null;
  duracion_planificada: number | null;
  veces_planificada: number;
  veces_completada: number;
  cantidad_promedio: number | null;
  duracion_promedio: number | null;
}

interface AnalyticsData {
  resumen: Resumen;
  por_dia: DiaStat[];
  por_tarea: TareaStat[];
}

/* ─── Helpers ──────────────────────────────────────────────────────── */

function toLocalISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getMonday(d: Date): Date {
  const copy = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = copy.getDay();
  // Sunday = 0, Monday = 1, etc.
  const diff = day === 0 ? 6 : day - 1;
  copy.setDate(copy.getDate() - diff);
  return copy;
}

function displayDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

type Preset = "esta_semana" | "semana_pasada" | "este_mes" | "mes_pasado" | "custom";

function getPresetRange(preset: Exclude<Preset, "custom">): { desde: string; hasta: string } {
  const today = new Date();
  switch (preset) {
    case "esta_semana": {
      const monday = getMonday(today);
      return { desde: toLocalISO(monday), hasta: toLocalISO(today) };
    }
    case "semana_pasada": {
      const thisMonday = getMonday(today);
      const prevMonday = new Date(thisMonday);
      prevMonday.setDate(prevMonday.getDate() - 7);
      const prevSunday = new Date(thisMonday);
      prevSunday.setDate(prevSunday.getDate() - 1);
      return { desde: toLocalISO(prevMonday), hasta: toLocalISO(prevSunday) };
    }
    case "este_mes": {
      const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
      return { desde: toLocalISO(firstDay), hasta: toLocalISO(today) };
    }
    case "mes_pasado": {
      const firstDayPrev = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const lastDayPrev = new Date(today.getFullYear(), today.getMonth(), 0);
      return { desde: toLocalISO(firstDayPrev), hasta: toLocalISO(lastDayPrev) };
    }
  }
}

/* ─── Component ────────────────────────────────────────────────────── */

export default function ProduccionAnalytics() {
  const defaultRange = getPresetRange("esta_semana");
  const [desde, setDesde] = useState(defaultRange.desde);
  const [hasta, setHasta] = useState(defaultRange.hasta);
  const [activePreset, setActivePreset] = useState<Preset>("esta_semana");
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await apiFetch<AnalyticsData>(
        `/api/produccion/analytics?desde=${desde}&hasta=${hasta}`
      );
      setData(result);
    } catch {
      toast("Error cargando analytics", "error");
    } finally {
      setLoading(false);
    }
  }, [desde, hasta, toast]);

  useEffect(() => {
    load();
  }, [load]);

  function applyPreset(preset: Exclude<Preset, "custom">) {
    const range = getPresetRange(preset);
    setDesde(range.desde);
    setHasta(range.hasta);
    setActivePreset(preset);
  }

  function handleDesdeChange(val: string) {
    setDesde(val);
    setActivePreset("custom");
  }

  function handleHastaChange(val: string) {
    setHasta(val);
    setActivePreset("custom");
  }

  /* ─── Cumplimiento color ─────────────────────────────────────────── */

  function cumplimientoColor(pct: number): string {
    if (pct >= 80) return "text-green-600";
    if (pct >= 60) return "text-amber-500";
    return "text-red-500";
  }

  function cumplimientoBg(pct: number): string {
    if (pct >= 80) return "bg-green-50 border-green-200";
    if (pct >= 60) return "bg-amber-50 border-amber-200";
    return "bg-red-50 border-red-200";
  }

  /* ─── Quantity arrow ─────────────────────────────────────────────── */

  function quantityIndicator(avg: number | null, plan: number | null) {
    if (avg === null || plan === null || plan === 0) return null;
    const diff = avg - plan;
    const pct = (diff / plan) * 100;
    if (Math.abs(pct) < 1) return null;
    const isUp = diff > 0;
    return (
      <span className={`text-xs font-medium ${isUp ? "text-green-600" : "text-red-500"}`}>
        {isUp ? "↑" : "↓"} {Math.abs(pct).toFixed(0)}%
      </span>
    );
  }

  /* ─── Render ─────────────────────────────────────────────────────── */

  const presets: { key: Exclude<Preset, "custom">; label: string }[] = [
    { key: "esta_semana", label: "Esta semana" },
    { key: "semana_pasada", label: "Semana pasada" },
    { key: "este_mes", label: "Este mes" },
    { key: "mes_pasado", label: "Mes pasado" },
  ];

  return (
    <div>
      {/* Back link + Header */}
      <div className="flex items-center gap-3 mb-4">
        <Link
          href="/produccion"
          className="flex items-center justify-center w-10 h-10 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-lg text-gray-600 shrink-0"
          style={{ touchAction: "manipulation" }}
        >
          &lsaquo;
        </Link>
        <h1 className="font-[family-name:var(--font-garamond)] text-2xl text-gray-900">
          Analytics de Produccion
        </h1>
      </div>

      {/* Date range picker */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        {/* Preset buttons */}
        <div className="flex flex-wrap gap-2 mb-3">
          {presets.map((p) => (
            <button
              key={p.key}
              onClick={() => applyPreset(p.key)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activePreset === p.key
                  ? "bg-[#004225] text-white"
                  : "border border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
              style={{ touchAction: "manipulation", minHeight: 44 }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Custom date inputs */}
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <label className="text-xs text-gray-400 block mb-1">Desde</label>
            <input
              type="date"
              value={desde}
              onChange={(e) => handleDesdeChange(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
              style={{ minHeight: 44 }}
            />
          </div>
          <div className="flex-1">
            <label className="text-xs text-gray-400 block mb-1">Hasta</label>
            <input
              type="date"
              value={hasta}
              onChange={(e) => handleHastaChange(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
              style={{ minHeight: 44 }}
            />
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          {displayDate(desde)} - {displayDate(hasta)}
        </p>
      </div>

      {/* Loading */}
      {loading && (
        <p className="text-center py-12 text-gray-500">Cargando...</p>
      )}

      {/* Content */}
      {!loading && data && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
            {/* Completadas */}
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                Completadas
              </p>
              <p className="text-3xl font-bold text-gray-900">
                {data.resumen.total_completadas}
                <span className="text-lg font-normal text-gray-400">
                  {" "}/ {data.resumen.total_planificadas}
                </span>
              </p>
            </div>

            {/* Cumplimiento */}
            <div
              className={`rounded-xl border p-4 ${cumplimientoBg(
                data.resumen.porcentaje_cumplimiento
              )}`}
            >
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                Cumplimiento
              </p>
              <p
                className={`text-3xl font-bold ${cumplimientoColor(
                  data.resumen.porcentaje_cumplimiento
                )}`}
              >
                {data.resumen.porcentaje_cumplimiento.toFixed(1)}%
              </p>
            </div>

            {/* Dias registrados */}
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                Dias registrados
              </p>
              <p className="text-3xl font-bold text-gray-900">
                {data.resumen.dias_registrados}
              </p>
            </div>
          </div>

          {/* Daily chart */}
          {data.por_dia.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
              <h2 className="font-[family-name:var(--font-garamond)] text-lg text-gray-900 mb-4">
                Por dia
              </h2>
              <div className="space-y-2">
                {data.por_dia.map((dia) => {
                  const pct = dia.planificadas > 0
                    ? (dia.completadas / dia.planificadas) * 100
                    : 0;
                  return (
                    <div key={dia.fecha} className="flex items-center gap-3">
                      {/* Day label */}
                      <div className="w-20 shrink-0 text-right">
                        <p className="text-sm font-medium text-gray-700 leading-tight">
                          {dia.dia_nombre.slice(0, 3)}
                        </p>
                        <p className="text-[10px] text-gray-400">
                          {displayDate(dia.fecha)}
                        </p>
                      </div>

                      {/* Bar */}
                      <div className="flex-1 h-7 bg-gray-100 rounded-md overflow-hidden relative">
                        <div
                          className="h-full bg-[#004225] rounded-md transition-all duration-300"
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                        {/* Count overlay */}
                        <span className="absolute inset-0 flex items-center px-2 text-xs font-medium">
                          <span
                            className={
                              pct > 40 ? "text-white" : "text-gray-600"
                            }
                          >
                            {dia.completadas}/{dia.planificadas}
                          </span>
                        </span>
                      </div>

                      {/* Percentage */}
                      <span
                        className={`w-12 text-right text-sm font-semibold ${cumplimientoColor(
                          dia.porcentaje
                        )}`}
                      >
                        {dia.porcentaje.toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Per-task breakdown */}
          {data.por_tarea.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
              <h2 className="font-[family-name:var(--font-garamond)] text-lg text-gray-900 mb-4">
                Por tarea
              </h2>

              {/* Desktop table */}
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-left text-xs text-gray-400 uppercase tracking-wide">
                      <th className="pb-2 pr-4 font-medium">Tarea</th>
                      <th className="pb-2 pr-4 font-medium text-center">Completadas</th>
                      <th className="pb-2 pr-4 font-medium text-right">Cant. Promedio</th>
                      <th className="pb-2 pr-4 font-medium text-right">Cant. Plan</th>
                      <th className="pb-2 pr-4 font-medium text-right">Tiempo Promedio</th>
                      <th className="pb-2 font-medium text-right">Tiempo Plan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.por_tarea.map((tarea) => {
                      const completionRate =
                        tarea.veces_planificada > 0
                          ? (tarea.veces_completada / tarea.veces_planificada) * 100
                          : 0;
                      const isGood = completionRate >= 80;
                      return (
                        <tr
                          key={tarea.tarea_id}
                          className="border-b border-gray-100 last:border-0"
                        >
                          <td className="py-2.5 pr-4 font-medium text-gray-900">
                            {tarea.titulo}
                          </td>
                          <td className="py-2.5 pr-4 text-center">
                            <span
                              className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                                isGood
                                  ? "bg-green-50 text-green-700"
                                  : "bg-red-50 text-red-600"
                              }`}
                            >
                              {tarea.veces_completada}/{tarea.veces_planificada}
                            </span>
                          </td>
                          <td className="py-2.5 pr-4 text-right text-gray-700">
                            <span className="flex items-center justify-end gap-1">
                              {tarea.cantidad_promedio !== null
                                ? `${tarea.cantidad_promedio.toFixed(1)} ${tarea.unidad_cantidad || ""}`
                                : "-"}
                              {quantityIndicator(
                                tarea.cantidad_promedio,
                                tarea.cantidad_planificada
                              )}
                            </span>
                          </td>
                          <td className="py-2.5 pr-4 text-right text-gray-400">
                            {tarea.cantidad_planificada !== null
                              ? `${tarea.cantidad_planificada} ${tarea.unidad_cantidad || ""}`
                              : "-"}
                          </td>
                          <td className="py-2.5 pr-4 text-right text-gray-700">
                            {tarea.duracion_promedio !== null
                              ? `${tarea.duracion_promedio} min`
                              : "-"}
                          </td>
                          <td className="py-2.5 text-right text-gray-400">
                            {tarea.duracion_planificada !== null
                              ? `${tarea.duracion_planificada} min`
                              : "-"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden space-y-3">
                {data.por_tarea.map((tarea) => {
                  const completionRate =
                    tarea.veces_planificada > 0
                      ? (tarea.veces_completada / tarea.veces_planificada) * 100
                      : 0;
                  const isGood = completionRate >= 80;
                  return (
                    <div
                      key={tarea.tarea_id}
                      className="border border-gray-200 rounded-lg p-3"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <p className="text-sm font-medium text-gray-900">
                          {tarea.titulo}
                        </p>
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-semibold shrink-0 ml-2 ${
                            isGood
                              ? "bg-green-50 text-green-700"
                              : "bg-red-50 text-red-600"
                          }`}
                        >
                          {tarea.veces_completada}/{tarea.veces_planificada}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <p className="text-gray-400">Cant. Promedio</p>
                          <p className="text-gray-700 font-medium flex items-center gap-1">
                            {tarea.cantidad_promedio !== null
                              ? `${tarea.cantidad_promedio.toFixed(1)} ${tarea.unidad_cantidad || ""}`
                              : "-"}
                            {quantityIndicator(
                              tarea.cantidad_promedio,
                              tarea.cantidad_planificada
                            )}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-400">Cant. Plan</p>
                          <p className="text-gray-700 font-medium">
                            {tarea.cantidad_planificada !== null
                              ? `${tarea.cantidad_planificada} ${tarea.unidad_cantidad || ""}`
                              : "-"}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-400">Tiempo Promedio</p>
                          <p className="text-gray-700 font-medium">
                            {tarea.duracion_promedio !== null
                              ? `${tarea.duracion_promedio} min`
                              : "-"}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-400">Tiempo Plan</p>
                          <p className="text-gray-700 font-medium">
                            {tarea.duracion_planificada !== null
                              ? `${tarea.duracion_planificada} min`
                              : "-"}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Empty state */}
          {data.por_dia.length === 0 && data.por_tarea.length === 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              Sin datos de produccion en este periodo
            </div>
          )}
        </>
      )}
    </div>
  );
}
