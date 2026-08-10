"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface Tarea {
  id: number;
  dia_semana: number;
  hora: string | null;
  titulo: string;
  descripcion: string | null;
  duracion_minutos: number | null;
  cantidad_planificada: number | null;
  unidad_cantidad: string | null;
  tipo: string;
  posicion: number;
  is_active: boolean;
}

interface DiaCalendario {
  nombre: string;
  tareas: Tarea[];
}

type CalendarioData = Record<string, DiaCalendario>;

const TIME_SLOTS = [
  "07:00",
  "08:00",
  "09:00",
  "10:00",
  "11:00",
  "12:00",
  "13:00",
  "14:00",
];

const TIPO_COLORS: Record<
  string,
  { dot: string; bg: string; border: string }
> = {
  produccion: {
    dot: "bg-[#004225]",
    bg: "bg-green-50",
    border: "border-green-200",
  },
  limpieza: {
    dot: "bg-amber-500",
    bg: "bg-amber-50",
    border: "border-amber-200",
  },
  nota: {
    dot: "bg-blue-500",
    bg: "bg-blue-50",
    border: "border-blue-200",
  },
  entrega: {
    dot: "bg-purple-500",
    bg: "bg-purple-50",
    border: "border-purple-200",
  },
  admin: {
    dot: "bg-gray-500",
    bg: "bg-gray-100",
    border: "border-gray-300",
  },
};

const DAY_LABELS: Record<string, string> = {
  "1": "Lun",
  "2": "Mar",
  "3": "Mie",
  "4": "Jue",
  "5": "Vie",
  "6": "Sab",
};

const DAY_KEYS = ["1", "2", "3", "4", "5", "6"];

function toLocalISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getNextWeekday(dayOfWeek: number): string {
  const today = new Date();
  const todayJsDay = today.getDay(); // 0=Sun, 1=Mon ... 6=Sat
  let diff = dayOfWeek - todayJsDay;
  if (diff < 0) diff += 7;
  const target = new Date(today);
  target.setDate(today.getDate() + diff);
  return toLocalISO(target);
}

function formatMinutes(totalMin: number): string {
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours > 0 && mins > 0) return `${hours}h ${mins}m`;
  if (hours > 0) return `${hours}h`;
  return `${mins}m`;
}

export default function CalendarioProduccion() {
  const [data, setData] = useState<CalendarioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeDay, setActiveDay] = useState("1");
  const { toast } = useToast();
  const router = useRouter();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch<CalendarioData>("/api/produccion/calendario");
      setData(d);
    } catch {
      toast("Error cargando calendario", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [load]);

  function navigateToDay(dayNum: string) {
    const fecha = getNextWeekday(parseInt(dayNum));
    router.push(`/produccion?fecha=${fecha}`);
  }

  function getTotalMinutes(tareas: Tarea[]): number {
    return tareas
      .filter((t) => t.is_active)
      .reduce((sum, t) => sum + (t.duracion_minutos || 0), 0);
  }

  function getTasksForSlot(tareas: Tarea[], hora: string): Tarea[] {
    return tareas.filter((t) => t.hora === hora && t.is_active);
  }

  function getNoteTasks(tareas: Tarea[]): Tarea[] {
    return tareas.filter((t) => t.hora === null && t.is_active);
  }

  if (loading) {
    return <p className="text-center py-12 text-gray-500">Cargando...</p>;
  }

  if (!data) {
    return (
      <div>
        <Link
          href="/produccion"
          className="text-sm text-[#004225] hover:underline"
        >
          &larr; Volver a Produccion
        </Link>
        <p className="text-center py-12 text-gray-500">
          No hay datos del calendario
        </p>
      </div>
    );
  }

  const hasAnyNotes = DAY_KEYS.some(
    (dk) => data[dk] && getNoteTasks(data[dk].tareas).length > 0
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-4">
        <Link
          href="/produccion"
          className="text-sm text-[#004225] hover:underline inline-block"
          style={{ touchAction: "manipulation", minHeight: 44, display: "inline-flex", alignItems: "center" }}
        >
          &larr; Volver a Produccion
        </Link>
        <h1 className="font-[family-name:var(--font-garamond)] text-2xl text-gray-900 mt-1">
          Calendario Semanal
        </h1>
      </div>

      {/* ---------- DESKTOP: spreadsheet table ---------- */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-16 p-2 text-left text-xs text-gray-400 font-medium border-b border-gray-200">
                Hora
              </th>
              {DAY_KEYS.map((dk) => {
                const dia = data[dk];
                if (!dia) {
                  return (
                    <th
                      key={dk}
                      className="p-2 border-b border-gray-200"
                    />
                  );
                }
                const totalMin = getTotalMinutes(dia.tareas);
                return (
                  <th key={dk} className="p-2 border-b border-gray-200 text-left">
                    <button
                      onClick={() => navigateToDay(dk)}
                      className="text-left hover:text-[#004225] transition-colors group w-full"
                      style={{ touchAction: "manipulation", minHeight: 44 }}
                    >
                      <span className="text-sm font-semibold text-gray-800 group-hover:text-[#004225]">
                        {dia.nombre}
                      </span>
                      <br />
                      <span className="text-xs text-gray-400 font-normal">
                        {formatMinutes(totalMin)}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {TIME_SLOTS.map((slot) => (
              <tr key={slot} className="border-b border-gray-100">
                <td className="p-2 text-xs text-gray-400 font-mono align-top whitespace-nowrap">
                  {slot.replace(":00", "h")}
                </td>
                {DAY_KEYS.map((dk) => {
                  const dia = data[dk];
                  const tareas = dia ? getTasksForSlot(dia.tareas, slot) : [];
                  if (tareas.length === 0) {
                    return (
                      <td key={dk} className="p-1 align-top min-w-[120px]" />
                    );
                  }
                  return (
                    <td key={dk} className="p-1 align-top min-w-[120px]">
                      <div className="space-y-1">
                        {tareas.map((tarea) => {
                          const colors =
                            TIPO_COLORS[tarea.tipo] || TIPO_COLORS.produccion;
                          return (
                            <div
                              key={tarea.id}
                              className={`rounded-lg p-2 ${colors.bg} border ${colors.border}`}
                            >
                              <div className="flex items-start gap-1.5">
                                <span
                                  className={`w-2 h-2 rounded-full shrink-0 mt-1 ${colors.dot}`}
                                />
                                <div className="min-w-0 flex-1">
                                  <p className="font-medium text-gray-900 text-xs leading-tight">
                                    {tarea.titulo}
                                  </p>
                                  {tarea.descripcion && (
                                    <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-3 leading-snug whitespace-pre-line">
                                      {tarea.descripcion}
                                    </p>
                                  )}
                                  {tarea.duracion_minutos != null &&
                                    tarea.duracion_minutos > 0 && (
                                      <p className="text-[10px] text-gray-400 mt-1">
                                        {tarea.duracion_minutos} min
                                      </p>
                                    )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}

            {/* Notas row */}
            {hasAnyNotes && (
              <tr className="border-t-2 border-gray-200">
                <td className="p-2 text-xs text-gray-500 font-medium align-top">
                  Notas
                </td>
                {DAY_KEYS.map((dk) => {
                  const dia = data[dk];
                  const notes = dia ? getNoteTasks(dia.tareas) : [];
                  if (notes.length === 0) {
                    return <td key={dk} className="p-1 align-top" />;
                  }
                  return (
                    <td key={dk} className="p-1 align-top">
                      <div className="space-y-1">
                        {notes.map((nota) => {
                          const colors =
                            TIPO_COLORS[nota.tipo] || TIPO_COLORS.nota;
                          return (
                            <div
                              key={nota.id}
                              className={`rounded-lg p-2 ${colors.bg} border ${colors.border}`}
                            >
                              <div className="flex items-start gap-1.5">
                                <span
                                  className={`w-2 h-2 rounded-full shrink-0 mt-0.5 ${colors.dot}`}
                                />
                                <div className="min-w-0">
                                  <p className="font-medium text-gray-900 text-xs">
                                    {nota.titulo}
                                  </p>
                                  {nota.descripcion && (
                                    <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2 whitespace-pre-line">
                                      {nota.descripcion}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  );
                })}
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ---------- MOBILE: day-by-day card view ---------- */}
      <div className="md:hidden">
        {/* Day tab buttons */}
        <div className="flex gap-1 mb-4 overflow-x-auto pb-1 -mx-1 px-1">
          {DAY_KEYS.map((dk) => {
            const label = DAY_LABELS[dk] || dk;
            const isActive = activeDay === dk;
            return (
              <button
                key={dk}
                onClick={() => setActiveDay(dk)}
                className={`px-3 py-2 rounded-lg text-sm font-medium shrink-0 transition-colors ${
                  isActive
                    ? "bg-[#004225] text-white"
                    : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
                style={{ touchAction: "manipulation", minHeight: 44 }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Active day content */}
        {data[activeDay] &&
          (() => {
            const dia = data[activeDay];
            const totalMin = getTotalMinutes(dia.tareas);
            const timedTareas = dia.tareas
              .filter((t) => t.hora !== null && t.is_active)
              .sort((a, b) => (a.hora || "").localeCompare(b.hora || ""));
            const noteTareas = getNoteTasks(dia.tareas);

            return (
              <div>
                {/* Day header */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-800">
                      {dia.nombre}
                    </h2>
                    <p className="text-xs text-gray-400">
                      {formatMinutes(totalMin)} planificados
                    </p>
                  </div>
                  <button
                    onClick={() => navigateToDay(activeDay)}
                    className="text-sm text-[#004225] border border-[#004225]/30 px-3 py-2 rounded-lg hover:bg-[#004225]/5 transition-colors"
                    style={{ touchAction: "manipulation", minHeight: 44 }}
                  >
                    Ver dia
                  </button>
                </div>

                {/* Tasks list */}
                {timedTareas.length === 0 && noteTareas.length === 0 ? (
                  <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-400 text-sm">
                    Sin tareas para este dia
                  </div>
                ) : (
                  <div className="space-y-2">
                    {timedTareas.map((tarea) => {
                      const colors =
                        TIPO_COLORS[tarea.tipo] || TIPO_COLORS.produccion;
                      return (
                        <div
                          key={tarea.id}
                          className={`rounded-xl p-3 ${colors.bg} border ${colors.border}`}
                        >
                          <div className="flex items-start gap-2">
                            <span
                              className={`w-2.5 h-2.5 rounded-full shrink-0 mt-1 ${colors.dot}`}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-400 font-mono">
                                  {tarea.hora?.replace(":00", "h")}
                                </span>
                                {tarea.duracion_minutos != null &&
                                  tarea.duracion_minutos > 0 && (
                                    <span className="text-xs text-gray-400">
                                      -- {tarea.duracion_minutos} min
                                    </span>
                                  )}
                              </div>
                              <p className="font-medium text-gray-900 text-sm mt-0.5">
                                {tarea.titulo}
                              </p>
                              {tarea.descripcion && (
                                <p className="text-xs text-gray-500 mt-1 line-clamp-3 whitespace-pre-line">
                                  {tarea.descripcion}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}

                    {/* Note tasks (no time slot) */}
                    {noteTareas.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
                          Recordatorios
                        </p>
                        <div className="space-y-1">
                          {noteTareas.map((nota) => {
                            const colors =
                              TIPO_COLORS[nota.tipo] || TIPO_COLORS.nota;
                            return (
                              <div
                                key={nota.id}
                                className={`flex items-center gap-2 rounded-lg px-3 py-2.5 ${colors.bg} border ${colors.border}`}
                              >
                                <span
                                  className={`w-2 h-2 rounded-full shrink-0 ${colors.dot}`}
                                />
                                <span className="text-sm text-gray-700 font-medium">
                                  {nota.titulo}
                                </span>
                                {nota.descripcion && (
                                  <span className="text-xs text-gray-400 ml-auto truncate max-w-[140px]">
                                    {nota.descripcion}
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })()}
      </div>
    </div>
  );
}
