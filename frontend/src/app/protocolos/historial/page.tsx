"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

// ── Types ──────────────────────────────────────────────────────────────────

interface HistorialCompletion {
  id: number;
  template_id: number;
  completed_by: number;
  completed_at: string;
  target_date: string;
  target_period: string | null;
  is_satisfactory: boolean;
  review_note: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
}

interface ProtocoloTemplate {
  id: number;
  checklist_type: string;
  section: string;
  task_name: string;
  position: number;
  day_of_week: number | null;
  day_of_month: number | null;
  shift: string | null;
  is_active: boolean;
}

type Mode = "day" | "week" | "month";

// ── Helpers ────────────────────────────────────────────────────────────────

function navDelta(mode: Mode, date: Date, delta: number): Date {
  const d = new Date(date);
  if (mode === "day") d.setDate(d.getDate() + delta);
  else if (mode === "week") d.setDate(d.getDate() + delta * 7);
  else d.setMonth(d.getMonth() + delta);
  return d;
}

function formatPeriodLabel(mode: Mode, date: Date): string {
  if (mode === "day")
    return date.toLocaleDateString("es-ES", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  if (mode === "week") {
    const start = new Date(date);
    // Monday of that week
    const day = start.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    start.setDate(start.getDate() + diff);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    return `${start.toLocaleDateString("es-ES", {
      day: "numeric",
      month: "short",
    })} – ${end.toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric" })}`;
  }
  return date.toLocaleDateString("es-ES", { month: "long", year: "numeric" });
}

function periodParam(mode: Mode, date: Date): string {
  if (mode === "day") return date.toISOString().split("T")[0];
  if (mode === "week") {
    const d = new Date(date);
    const day = d.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    d.setDate(d.getDate() + diff);
    return d.toISOString().split("T")[0];
  }
  const m = String(date.getMonth() + 1).padStart(2, "0");
  return `${date.getFullYear()}-${m}`;
}

const TIPO_LABELS: Record<string, string> = {
  apertura: "Apertura",
  cierre: "Cierre",
  semanal: "Semanal",
  mensual: "Mensual",
};

// ── Page ───────────────────────────────────────────────────────────────────

export default function HistorialPage() {
  const { toast } = useToast();
  const [mode, setMode] = useState<Mode>("day");
  const [date, setDate] = useState<Date>(new Date());
  const [completions, setCompletions] = useState<HistorialCompletion[]>([]);
  const [templates, setTemplates] = useState<ProtocoloTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  // Build a lookup map for template info
  const templateMap = new Map(templates.map((t) => [t.id, t]));

  useEffect(() => {
    setLoading(true);
    const param = periodParam(mode, date);
    Promise.all([
      apiFetch<HistorialCompletion[]>(
        `/api/protocolos/historial?mode=${mode}&period=${param}`
      ),
      apiFetch<ProtocoloTemplate[]>("/api/protocolos/templates"),
    ])
      .then(([hist, tmpls]) => {
        setCompletions(hist);
        setTemplates(tmpls);
      })
      .catch(() => toast("Error al cargar historial", "error"))
      .finally(() => setLoading(false));
  }, [mode, date, toast]);

  const total = completions.length;
  const completados = completions.filter((c) => c.is_satisfactory).length;
  const pct = total === 0 ? 0 : Math.round((completados / total) * 100);

  // Group by checklist_type via template lookup
  const byTipo = completions.reduce<Record<string, HistorialCompletion[]>>(
    (acc, item) => {
      const tmpl = templateMap.get(item.template_id);
      const k = tmpl?.checklist_type ?? "desconocido";
      if (!acc[k]) acc[k] = [];
      acc[k].push(item);
      return acc;
    },
    {}
  );

  const isToday =
    mode === "day" && date.toISOString().split("T")[0] === new Date().toISOString().split("T")[0];

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
          Historial
        </h1>
      </div>

      {/* Mode selector */}
      <div className="flex gap-1 bg-white border border-cream-dark rounded-xl p-1 mb-4 w-fit">
        {(["day", "week", "month"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => {
              setMode(m);
              setDate(new Date());
            }}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors min-h-[36px] ${
              mode === m
                ? "bg-brot text-white"
                : "text-warm-gray hover:text-text"
            }`}
          >
            {m === "day" ? "Día" : m === "week" ? "Semana" : "Mes"}
          </button>
        ))}
      </div>

      {/* Date navigator */}
      <div className="flex items-center justify-between bg-white border border-cream-dark rounded-xl px-4 py-3 mb-6">
        <button
          onClick={() => setDate((d) => navDelta(mode, d, -1))}
          className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-cream transition-colors text-warm-gray hover:text-text text-lg"
        >
          ‹
        </button>
        <div className="text-center">
          <span className="text-sm font-medium text-text capitalize">
            {formatPeriodLabel(mode, date)}
          </span>
          {isToday && (
            <span className="ml-2 text-xs bg-brot/10 text-brot px-2 py-0.5 rounded-full">
              hoy
            </span>
          )}
        </div>
        <button
          onClick={() => setDate((d) => navDelta(mode, d, 1))}
          className="w-9 h-9 flex items-center justify-center rounded-lg hover:bg-cream transition-colors text-warm-gray hover:text-text text-lg"
        >
          ›
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-warm-gray text-sm">
          Cargando…
        </div>
      ) : total === 0 ? (
        <div className="py-12 text-center text-warm-gray text-sm">
          Sin datos para este período.
        </div>
      ) : (
        <>
          {/* Summary */}
          <div className="bg-white border border-cream-dark rounded-xl p-5 mb-6">
            <div className="flex items-center gap-5">
              <div className="flex-shrink-0">
                <p
                  className={`text-5xl font-[family-name:var(--font-garamond)] ${
                    pct >= 80
                      ? "text-brot"
                      : pct >= 50
                        ? "text-amber-500"
                        : "text-red-500"
                  }`}
                >
                  {pct}%
                </p>
                <p className="text-xs text-warm-gray mt-0.5">
                  {completados} / {total} tareas
                </p>
              </div>
              <div className="flex-1">
                <div className="h-3 bg-cream-dark rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      pct >= 80
                        ? "bg-brot"
                        : pct >= 50
                          ? "bg-amber-400"
                          : "bg-red-400"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-xs text-warm-gray mt-2">
                  {total - completados} tareas pendientes
                </p>
              </div>
            </div>
          </div>

          {/* By tipo */}
          {Object.entries(byTipo).map(([tipo, tipoItems]) => {
            const done = tipoItems.filter((i) => i.is_satisfactory).length;
            return (
              <div key={tipo} className="mb-5">
                <div className="flex items-center justify-between mb-2 px-1">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-warm-gray">
                    {TIPO_LABELS[tipo] ?? tipo}
                  </h3>
                  <span className="text-xs text-warm-gray">
                    {done}/{tipoItems.length}
                  </span>
                </div>
                <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                  {tipoItems.map((item, idx) => {
                    const tmpl = templateMap.get(item.template_id);
                    return (
                      <div
                        key={item.id}
                        className={`flex items-center gap-3 px-4 py-3 ${
                          idx < tipoItems.length - 1
                            ? "border-b border-cream"
                            : ""
                        }`}
                      >
                        <span
                          className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                            item.is_satisfactory
                              ? "bg-brot text-white"
                              : "bg-cream-dark text-warm-gray"
                          }`}
                        >
                          {item.is_satisfactory ? "✓" : "○"}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p
                            className={`text-sm ${
                              item.is_satisfactory
                                ? "text-warm-gray line-through"
                                : "text-text"
                            }`}
                          >
                            {tmpl?.task_name ?? `Tarea #${item.template_id}`}
                          </p>
                          <p className="text-xs text-warm-gray">
                            Usuario #{item.completed_by}
                          </p>
                        </div>
                        <span className="text-xs text-warm-gray flex-shrink-0">
                          {new Date(item.completed_at).toLocaleTimeString(
                            "es-ES",
                            { hour: "2-digit", minute: "2-digit" }
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
