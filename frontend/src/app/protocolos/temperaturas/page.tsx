"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

// ── Types ──────────────────────────────────────────────────────────────────

interface Frigorifico {
  id: number;
  nombre: string;
  temp_max: number;
}

interface HistorialTemp {
  id: number;
  frigorifico_id: number;
  frigorifico_nombre: string;
  value: number;
  turno: string;
  recorded_at: string;
  recorded_by: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function getShift(): "manana" | "tarde" {
  return new Date().getHours() < 15 ? "manana" : "tarde";
}

// ── Bar chart component ────────────────────────────────────────────────────

function TempBar({
  value,
  tempMax,
}: {
  value: number;
  tempMax: number;
}) {
  // Display range: –25°C to +15°C
  const minDisplay = -25;
  const maxDisplay = 15;
  const range = maxDisplay - minDisplay;
  const heightPct = Math.max(
    2,
    Math.min(100, ((value - minDisplay) / range) * 100)
  );
  const isHot = value > tempMax;

  return (
    <div className="flex flex-col items-center gap-1" style={{ width: 26 }}>
      <span
        className={`text-[9px] font-mono leading-none ${
          isHot ? "text-red-600 font-bold" : "text-warm-gray"
        }`}
      >
        {value}°
      </span>
      <div
        className="relative w-4 bg-cream-dark rounded-sm"
        style={{ height: 56 }}
      >
        <div
          className={`absolute bottom-0 left-0 right-0 rounded-sm transition-all ${
            isHot ? "bg-red-400" : "bg-brot/70"
          }`}
          style={{ height: `${heightPct}%` }}
        />
      </div>
      {isHot && (
        <span className="text-[8px] text-red-500 font-bold leading-none">
          ▲
        </span>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function TemperaturasPage() {
  const { toast } = useToast();
  const [frigorificos, setFrigorificos] = useState<Frigorifico[]>([]);
  const [values, setValues] = useState<Record<number, string>>({});
  const [historial, setHistorial] = useState<HistorialTemp[]>([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const shift = getShift();
  const shiftLabel = shift === "manana" ? "Mañana" : "Tarde";

  const loadHistorial = () =>
    apiFetch<HistorialTemp[]>("/api/temperaturas/historial").then(setHistorial);

  useEffect(() => {
    Promise.all([
      apiFetch<Frigorifico[]>("/api/temperaturas/frigorificos"),
      apiFetch<HistorialTemp[]>("/api/temperaturas/historial"),
    ])
      .then(([frigs, hist]) => {
        setFrigorificos(frigs);
        const init: Record<number, string> = {};
        frigs.forEach((f) => (init[f.id] = ""));
        setValues(init);
        setHistorial(hist);
      })
      .catch(() => toast("Error al cargar datos", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const records = frigorificos
      .filter((f) => values[f.id]?.trim() !== "")
      .map((f) => ({
        frigorifico_id: f.id,
        value: parseFloat(values[f.id]),
      }));

    if (records.length === 0) {
      toast("Ingresa al menos una temperatura", "error");
      return;
    }

    setSaving(true);
    try {
      await apiFetch(`/api/temperaturas/${shift}`, {
        method: "POST",
        body: JSON.stringify(records),
      });
      toast("Temperaturas guardadas ✓");
      const cleared: Record<number, string> = {};
      frigorificos.forEach((f) => (cleared[f.id] = ""));
      setValues(cleared);
      loadHistorial();
    } catch {
      toast("Error al guardar temperaturas", "error");
    } finally {
      setSaving(false);
    }
  };

  // Build chart: last 7 distinct dates, all entries per date
  const byDate = historial.reduce<Record<string, HistorialTemp[]>>(
    (acc, item) => {
      const date = item.recorded_at.split("T")[0];
      if (!acc[date]) acc[date] = [];
      acc[date].push(item);
      return acc;
    },
    {}
  );
  const chartDates = Object.keys(byDate).sort().slice(-7);

  const fridgeMaxMap = new Map(frigorificos.map((f) => [f.id, f.temp_max]));

  return (
    <div>
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 mb-6 text-sm">
        <Link
          href="/protocolos"
          className="text-warm-gray hover:text-brot transition-colors"
        >
          ← Protocolos
        </Link>
        <span className="text-cream-dark">|</span>
        <h1 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Temperaturas
        </h1>
      </div>

      {loading ? (
        <div className="py-12 text-center text-warm-gray text-sm">
          Cargando…
        </div>
      ) : (
        <>
          {/* Recording form */}
          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-medium text-text">Turno {shiftLabel}</h2>
              <span className="text-xs text-warm-gray bg-cream rounded-full px-3 py-1">
                {new Date().toLocaleDateString("es-ES", {
                  weekday: "short",
                  day: "numeric",
                  month: "long",
                })}
              </span>
            </div>

            {frigorificos.length === 0 ? (
              <p className="text-sm text-warm-gray py-4 text-center">
                No hay frigoríficos configurados.
              </p>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-3">
                {frigorificos.map((f) => {
                  const raw = values[f.id] ?? "";
                  const val = parseFloat(raw);
                  const isAlert = raw.trim() !== "" && !isNaN(val) && val > f.temp_max;
                  return (
                    <div
                      key={f.id}
                      className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                        isAlert
                          ? "bg-red-50 border border-red-200"
                          : "bg-cream"
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-text">
                          {f.nombre}
                        </p>
                        <p className="text-xs text-warm-gray">
                          Máx: {f.temp_max}°C
                        </p>
                      </div>
                      {isAlert && (
                        <span className="text-xs font-semibold text-red-600 flex-shrink-0">
                          Alta
                        </span>
                      )}
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <input
                          type="number"
                          step="0.1"
                          placeholder="—"
                          value={raw}
                          onChange={(e) =>
                            setValues((v) => ({ ...v, [f.id]: e.target.value }))
                          }
                          className={`w-20 text-right px-2 py-1.5 rounded border text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brot/30 ${
                            isAlert
                              ? "border-red-300 bg-white text-red-700"
                              : "border-cream-dark bg-white"
                          }`}
                        />
                        <span className="text-xs text-warm-gray">°C</span>
                      </div>
                    </div>
                  );
                })}

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={saving}
                    className="w-full bg-brot text-white rounded-lg py-3 text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
                  >
                    {saving ? "Guardando…" : "Registrar temperaturas"}
                  </button>
                </div>
              </form>
            )}
          </div>

          {/* History chart */}
          {historial.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <h2 className="font-medium text-text mb-1">Últimos 7 días</h2>
              <p className="text-xs text-warm-gray mb-4">
                Barras más altas = temperatura más elevada. Rojo = sobre máximo.
              </p>
              <div className="overflow-x-auto pb-2">
                <div className="flex gap-6 min-w-max items-end">
                  {chartDates.map((date) => {
                    const dayItems = byDate[date] ?? [];
                    const dayLabel = new Date(date + "T12:00:00").toLocaleDateString(
                      "es-ES",
                      { weekday: "short", day: "numeric" }
                    );
                    return (
                      <div
                        key={date}
                        className="flex flex-col items-center gap-2"
                      >
                        <div className="flex gap-1 items-end" style={{ height: 80 }}>
                          {dayItems.map((item) => (
                            <TempBar
                              key={item.id}
                              value={item.value}
                              tempMax={
                                fridgeMaxMap.get(item.frigorifico_id) ?? 8
                              }
                            />
                          ))}
                        </div>
                        <span className="text-[10px] text-warm-gray capitalize">
                          {dayLabel}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Legend */}
              {frigorificos.length > 0 && (
                <div className="mt-4 pt-4 border-t border-cream flex flex-wrap gap-2">
                  {frigorificos.map((f) => (
                    <span
                      key={f.id}
                      className="text-xs text-warm-gray bg-cream rounded-full px-2.5 py-1"
                    >
                      {f.nombre} · máx {f.temp_max}°C
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
