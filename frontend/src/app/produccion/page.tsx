"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const DIAS_FULL = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];

interface CalendarioItem {
  producto_id: number;
  producto_nombre: string;
  cantidad_planificada: number;
  cantidad_real: number | null;
}

interface CalendarioDia {
  fecha: string;
  dia_semana: number;
  items: CalendarioItem[];
}

interface CalendarioRaw {
  fecha: string;
  day_of_week: number;
  producto_id: number;
  planned_qty: number | null;
  actual_qty: number | null;
}

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDisplayDate(dateStr: string): string {
  const [y, m, day] = dateStr.split("-");
  return `${day}/${m}/${y}`;
}

function getStatusColor(item: CalendarioItem): string {
  if (item.cantidad_real === null || item.cantidad_real === undefined) {
    return "bg-red-50 border-red-200 text-red-700";
  }
  if (item.cantidad_real >= item.cantidad_planificada) {
    return "bg-green-50 border-green-200 text-green-700";
  }
  return "bg-yellow-50 border-yellow-200 text-yellow-700";
}

function getStatusDot(item: CalendarioItem): string {
  if (item.cantidad_real === null || item.cantidad_real === undefined) {
    return "bg-red-400";
  }
  if (item.cantidad_real >= item.cantidad_planificada) {
    return "bg-green-500";
  }
  return "bg-yellow-400";
}

export default function ProduccionCalendarioPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [weekStart, setWeekStart] = useState<Date>(() => getMonday(new Date()));
  const [calendario, setCalendario] = useState<CalendarioDia[]>([]);
  const [loading, setLoading] = useState(true);

  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);

  const loadCalendario = useCallback(async () => {
    setLoading(true);
    try {
      const desde = formatDate(weekStart);
      const hasta = formatDate(weekEnd);
      const raw = await apiFetch<CalendarioRaw[]>(
        `/api/produccion/calendario?fecha_desde=${desde}&fecha_hasta=${hasta}`
      );
      const productos = await apiFetch<{ id: number; nombre: string }[]>(
        "/api/produccion/productos"
      );
      const prodMap = new Map(productos.map((p) => [p.id, p.nombre]));
      const grouped = new Map<string, CalendarioDia>();
      for (const row of raw) {
        if (!grouped.has(row.fecha)) {
          grouped.set(row.fecha, {
            fecha: row.fecha,
            dia_semana: row.day_of_week,
            items: [],
          });
        }
        grouped.get(row.fecha)!.items.push({
          producto_id: row.producto_id,
          producto_nombre: prodMap.get(row.producto_id) || `Producto ${row.producto_id}`,
          cantidad_planificada: row.planned_qty || 0,
          cantidad_real: row.actual_qty,
        });
      }
      setCalendario(Array.from(grouped.values()));
    } catch {
      toast("Error al cargar el calendario", "error");
    } finally {
      setLoading(false);
    }
  }, [weekStart]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadCalendario();
  }, [loadCalendario]);

  function prevWeek() {
    setWeekStart((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() - 7);
      return d;
    });
  }

  function nextWeek() {
    setWeekStart((prev) => {
      const d = new Date(prev);
      d.setDate(d.getDate() + 7);
      return d;
    });
  }

  function goToToday() {
    setWeekStart(getMonday(new Date()));
  }

  // Build a map from date string to CalendarioDia
  const calMap = new Map<string, CalendarioDia>();
  calendario.forEach((d) => calMap.set(d.fecha, d));

  // Build the 7 days of the week
  const weekDays: { date: Date; dateStr: string; dayData: CalendarioDia | null }[] =
    Array.from({ length: 7 }, (_, i) => {
      const d = new Date(weekStart);
      d.setDate(weekStart.getDate() + i);
      const dateStr = formatDate(d);
      return { date: d, dateStr, dayData: calMap.get(dateStr) ?? null };
    });

  const todayStr = formatDate(new Date());

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-3">
        <div>
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Producción
          </h1>
          <p className="text-sm text-warm-gray mt-0.5">
            Semana del {formatDisplayDate(formatDate(weekStart))} al{" "}
            {formatDisplayDate(formatDate(weekEnd))}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => router.push("/produccion/registro")}
            className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px]"
          >
            Registrar hoy
          </button>
          <button
            onClick={() => router.push("/produccion/plan")}
            className="border border-cream-dark bg-white text-text px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-cream transition-colors min-h-[44px]"
          >
            Plan semanal
          </button>
          <button
            onClick={() => router.push("/produccion/productos")}
            className="border border-cream-dark bg-white text-text px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-cream transition-colors min-h-[44px]"
          >
            Productos
          </button>
          <button
            onClick={() => router.push("/produccion/analytics")}
            className="border border-cream-dark bg-white text-text px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-cream transition-colors min-h-[44px]"
          >
            Análisis
          </button>
        </div>
      </div>

      {/* Week navigator */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={prevWeek}
          className="p-2 rounded-lg border border-cream-dark bg-white hover:bg-cream transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
          aria-label="Semana anterior"
        >
          ‹
        </button>
        <button
          onClick={goToToday}
          className="px-3 py-2 rounded-lg border border-cream-dark bg-white text-sm text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
        >
          Hoy
        </button>
        <button
          onClick={nextWeek}
          className="p-2 rounded-lg border border-cream-dark bg-white hover:bg-cream transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
          aria-label="Semana siguiente"
        >
          ›
        </button>

        {/* Legend */}
        <div className="ml-auto flex items-center gap-3 text-xs text-warm-gray">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
            Cumplido
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
            Parcial
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
            Sin registrar
          </span>
        </div>
      </div>

      {/* Calendar grid */}
      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : (
        <>
          {/* Desktop: 7-column grid */}
          <div className="hidden md:grid grid-cols-7 gap-2">
            {weekDays.map(({ date, dateStr, dayData }, i) => {
              const isToday = dateStr === todayStr;
              return (
                <div
                  key={dateStr}
                  className={`bg-white rounded-xl border min-h-[200px] flex flex-col ${
                    isToday
                      ? "border-brot shadow-sm"
                      : "border-cream-dark"
                  }`}
                >
                  {/* Day header */}
                  <div
                    className={`px-3 py-2 border-b ${
                      isToday
                        ? "border-brot/20 bg-brot/5"
                        : "border-cream-dark"
                    }`}
                  >
                    <p
                      className={`text-xs font-medium uppercase tracking-wide ${
                        isToday ? "text-brot" : "text-warm-gray"
                      }`}
                    >
                      {DIAS[i]}
                    </p>
                    <p
                      className={`text-sm font-semibold mt-0.5 ${
                        isToday ? "text-brot" : "text-text"
                      }`}
                    >
                      {date.getDate()}
                    </p>
                  </div>

                  {/* Items */}
                  <div className="p-2 flex-1 space-y-1.5">
                    {dayData && dayData.items && dayData.items.length > 0 ? (
                      dayData.items.map((item) => (
                        <div
                          key={item.producto_id}
                          className={`rounded-md border px-2 py-1.5 text-xs ${getStatusColor(item)}`}
                        >
                          <div className="flex items-start gap-1">
                            <span
                              className={`w-1.5 h-1.5 rounded-full mt-0.5 shrink-0 ${getStatusDot(item)}`}
                            />
                            <div className="min-w-0">
                              <p className="font-medium truncate">
                                {item.producto_nombre}
                              </p>
                              <p className="text-[10px] opacity-80 mt-0.5">
                                {item.cantidad_real !== null
                                  ? `${item.cantidad_real}/${item.cantidad_planificada}`
                                  : `0/${item.cantidad_planificada}`}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-warm-gray/60 text-center pt-4">
                        Sin plan
                      </p>
                    )}
                  </div>

                  {/* Quick log link */}
                  {isToday && (
                    <div className="px-2 pb-2">
                      <button
                        onClick={() => router.push("/produccion/registro")}
                        className="w-full text-xs text-brot hover:text-brot-dark py-1 text-center border border-brot/30 rounded-md hover:bg-brot/5 transition-colors"
                      >
                        Registrar
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Mobile: stacked cards */}
          <div className="md:hidden space-y-3">
            {weekDays.map(({ date, dateStr, dayData }, i) => {
              const isToday = dateStr === todayStr;
              return (
                <div
                  key={dateStr}
                  className={`bg-white rounded-xl border ${
                    isToday ? "border-brot" : "border-cream-dark"
                  }`}
                >
                  <div
                    className={`flex items-center justify-between px-4 py-3 border-b ${
                      isToday ? "border-brot/20 bg-brot/5" : "border-cream-dark"
                    }`}
                  >
                    <div>
                      <span
                        className={`text-sm font-semibold ${isToday ? "text-brot" : "text-text"}`}
                      >
                        {DIAS_FULL[i]}
                      </span>
                      <span className="text-xs text-warm-gray ml-2">
                        {date.getDate()}/{date.getMonth() + 1}
                      </span>
                    </div>
                    {isToday && (
                      <button
                        onClick={() => router.push("/produccion/registro")}
                        className="text-xs text-brot border border-brot/30 rounded-md px-2 py-1 hover:bg-brot/5"
                      >
                        Registrar
                      </button>
                    )}
                  </div>
                  {dayData && dayData.items && dayData.items.length > 0 ? (
                    <div className="p-3 space-y-2">
                      {dayData.items.map((item) => (
                        <div
                          key={item.producto_id}
                          className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${getStatusColor(item)}`}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-2 h-2 rounded-full shrink-0 ${getStatusDot(item)}`}
                            />
                            <span className="font-medium">
                              {item.producto_nombre}
                            </span>
                          </div>
                          <span className="text-xs opacity-80 shrink-0 ml-2">
                            {item.cantidad_real !== null
                              ? `${item.cantidad_real}/${item.cantidad_planificada}`
                              : `0/${item.cantidad_planificada}`}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="px-4 py-3 text-sm text-warm-gray">
                      Sin producción planificada
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
