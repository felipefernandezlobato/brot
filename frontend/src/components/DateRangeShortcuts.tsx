"use client";

import { useState } from "react";

type Modo = "dia" | "semana" | "mes" | "custom";

const MODOS: { key: Modo; label: string }[] = [
  { key: "dia", label: "Día" },
  { key: "semana", label: "Semana" },
  { key: "mes", label: "Mes" },
  { key: "custom", label: "Custom" },
];

/** Local-calendar YYYY-MM-DD -- never toISOString(), which converts to UTC
 * first and silently shifts the date back a day in any timezone behind it. */
function fmt(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** ISO 8601 week ("YYYY-Www") containing the given date -- matches what
 * <input type="week"> expects and produces. */
function isoWeekOf(fecha: string): string {
  const d = new Date(fecha + "T00:00:00");
  const target = new Date(d);
  const dayNr = (d.getDay() + 6) % 7; // Monday = 0 .. Sunday = 6
  target.setDate(target.getDate() - dayNr + 3); // nearest Thursday
  const firstThursday = new Date(target.getFullYear(), 0, 4);
  const diffDays = (target.getTime() - firstThursday.getTime()) / 86400000;
  const week = 1 + Math.round(diffDays / 7);
  return `${target.getFullYear()}-W${String(week).padStart(2, "0")}`;
}

function semanaARango(semana: string): { desde: string; hasta: string } {
  const [yearStr, weekStr] = semana.split("-W");
  const year = Number(yearStr);
  const week = Number(weekStr);
  const jan4 = new Date(year, 0, 4);
  const jan4Dow = (jan4.getDay() + 6) % 7;
  const week1Monday = new Date(jan4);
  week1Monday.setDate(jan4.getDate() - jan4Dow);
  const monday = new Date(week1Monday);
  monday.setDate(week1Monday.getDate() + (week - 1) * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { desde: fmt(monday), hasta: fmt(sunday) };
}

function mesARango(mes: string): { desde: string; hasta: string } {
  const [y, m] = mes.split("-").map(Number);
  return { desde: fmt(new Date(y, m - 1, 1)), hasta: fmt(new Date(y, m, 0)) };
}

interface Props {
  fechaDesde: string;
  fechaHasta: string;
  onChange: (desde: string, hasta: string) => void;
}

/** Día / Semana / Mes / Custom range picker. Each shortcut lets you pick
 * WHICH day/week/month (not just "today") -- Custom is the plain two-date
 * picker every other date-ranged page already uses. */
export default function DateRangeShortcuts({ fechaDesde, fechaHasta, onChange }: Props) {
  const [modo, setModo] = useState<Modo>("custom");

  function switchModo(m: Modo) {
    setModo(m);
    if (m === "dia") {
      onChange(fechaDesde, fechaDesde);
    } else if (m === "semana") {
      const { desde, hasta } = semanaARango(isoWeekOf(fechaDesde));
      onChange(desde, hasta);
    } else if (m === "mes") {
      const { desde, hasta } = mesARango(fechaDesde.slice(0, 7));
      onChange(desde, hasta);
    }
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex gap-1 bg-cream rounded-lg p-1">
        {MODOS.map((m) => (
          <button
            key={m.key}
            type="button"
            onClick={() => switchModo(m.key)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors min-h-[36px] ${
              modo === m.key ? "bg-brot text-white" : "text-warm-gray hover:text-brot"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {modo === "dia" && (
        <input
          type="date"
          value={fechaDesde}
          onChange={(e) => onChange(e.target.value, e.target.value)}
          className="px-2 py-1.5 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
        />
      )}

      {modo === "semana" && (
        <input
          type="week"
          value={isoWeekOf(fechaDesde)}
          onChange={(e) => {
            if (!e.target.value) return;
            const { desde, hasta } = semanaARango(e.target.value);
            onChange(desde, hasta);
          }}
          className="px-2 py-1.5 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
        />
      )}

      {modo === "mes" && (
        <input
          type="month"
          value={fechaDesde.slice(0, 7)}
          onChange={(e) => {
            if (!e.target.value) return;
            const { desde, hasta } = mesARango(e.target.value);
            onChange(desde, hasta);
          }}
          className="px-2 py-1.5 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
        />
      )}

      {modo === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={fechaDesde}
            onChange={(e) => onChange(e.target.value, fechaHasta)}
            className="px-2 py-1.5 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
          />
          <span className="text-warm-gray text-xs">a</span>
          <input
            type="date"
            value={fechaHasta}
            onChange={(e) => onChange(fechaDesde, e.target.value)}
            className="px-2 py-1.5 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
          />
        </div>
      )}
    </div>
  );
}
