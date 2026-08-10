"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

const DAYS_LABELS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const DAYS_FULL = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];
const WEEKS = [1, 2, 3, 4];

interface ProductoProduccion {
  id: number;
  nombre: string;
  unidad: string;
  is_active: boolean;
}

interface PlanCell {
  week_number: number;
  day_of_week: number;
  planned_qty: number;
}

interface PlanEntry {
  producto_id: number;
  week_number: number;
  day_of_week: number;
  planned_qty: number;
}

// key: `${week}-${day}-${productoId}`
type PlanMap = Map<string, number>;

function cellKey(week: number, day: number, productoId: number): string {
  return `${week}-${day}-${productoId}`;
}

export default function PlanProduccionPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [productos, setProductos] = useState<ProductoProduccion[]>([]);
  const [planMap, setPlanMap] = useState<PlanMap>(new Map());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [semana, setSemana] = useState(1); // selected week view: 1-4

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [prods, planEntries] = await Promise.all([
        apiFetch<ProductoProduccion[]>("/api/produccion/productos"),
        apiFetch<PlanEntry[]>("/api/produccion/plan"),
      ]);
      setProductos(prods.filter((p) => p.is_active));
      const map = new Map<string, number>();
      planEntries.forEach((entry) => {
        const k = cellKey(
          entry.week_number,
          entry.day_of_week,
          entry.producto_id
        );
        map.set(k, entry.planned_qty ?? 0);
      });
      setPlanMap(map);
      setDirty(false);
    } catch {
      toast("Error al cargar el plan de producción", "error");
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadData();
  }, [loadData]);

  function updateCell(
    week: number,
    day: number,
    productoId: number,
    value: string
  ) {
    const num = value === "" ? 0 : Math.max(0, Number(value));
    setPlanMap((prev) => {
      const next = new Map(prev);
      const k = cellKey(week, day, productoId);
      if (num === 0) {
        next.delete(k);
      } else {
        next.set(k, num);
      }
      return next;
    });
    setDirty(true);
  }

  function getCellValue(
    week: number,
    day: number,
    productoId: number
  ): string {
    const k = cellKey(week, day, productoId);
    const v = planMap.get(k);
    return v ? String(v) : "";
  }

  function getDayTotal(week: number, day: number): number {
    return productos.reduce((sum, p) => {
      const k = cellKey(week, day, p.id);
      return sum + (planMap.get(k) ?? 0);
    }, 0);
  }

  function getProductWeekTotal(week: number, productoId: number): number {
    return DAYS_LABELS.reduce((sum, _, dayIdx) => {
      const k = cellKey(week, dayIdx + 1, productoId);
      return sum + (planMap.get(k) ?? 0);
    }, 0);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: PlanCell[] = [];
      planMap.forEach((cantidad, key) => {
        const [week, day] = key.split("-").map(Number);
        payload.push({
          week_number: week,
          day_of_week: day,
          planned_qty: cantidad,
        });
      });

      // Send per week_number + day_of_week combination to the API
      // The API accepts POST /api/produccion/plan with all entries
      for (const week of WEEKS) {
        for (let day = 1; day <= 7; day++) {
          const weekDayEntries: PlanEntry[] = productos
            .map((p) => ({
              producto_id: p.id,
              week_number: week,
              day_of_week: day,
              planned_qty:
                planMap.get(cellKey(week, day, p.id)) ?? 0,
            }))
            .filter((e) => e.planned_qty > 0);
          if (weekDayEntries.length > 0) {
            await apiFetch(
              `/api/produccion/plan?week_number=${week}&day_of_week=${day}`,
              {
                method: "POST",
                body: JSON.stringify(weekDayEntries),
              }
            );
          }
        }
      }

      toast("Plan guardado correctamente");
      setDirty(false);
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al guardar el plan",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "w-full px-1 py-1.5 rounded border border-cream-dark bg-white text-text text-xs text-center focus:outline-none focus:ring-1 focus:ring-brot/40 focus:border-brot min-h-[36px]";

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
            Plan de Producción
          </h1>
          <p className="text-sm text-warm-gray mt-0.5">
            Plan rotativo de 4 semanas
          </p>
        </div>
        {dirty && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Guardando..." : "Guardar plan"}
          </button>
        )}
      </div>

      {/* Week selector tabs */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {WEEKS.map((w) => (
          <button
            key={w}
            onClick={() => setSemana(w)}
            className={`px-4 py-2 rounded-lg text-sm font-medium min-h-[40px] transition-colors ${
              semana === w
                ? "bg-brot text-white"
                : "bg-white border border-cream-dark text-warm-gray hover:bg-cream hover:text-text"
            }`}
          >
            Semana {w}
          </button>
        ))}
        <div className="ml-auto text-xs text-warm-gray flex items-center">
          Cantidades en unidades por día
        </div>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : productos.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay productos activos.{" "}
          <button
            onClick={() => router.push("/produccion/productos")}
            className="text-brot underline"
          >
            Gestionar productos
          </button>
        </div>
      ) : (
        <>
          {/* Desktop grid */}
          <div className="hidden md:block bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-cream/50 border-b border-cream-dark">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray text-xs uppercase tracking-wide min-w-[160px]">
                      Producto
                    </th>
                    {DAYS_LABELS.map((day, i) => (
                      <th
                        key={i}
                        className="text-center px-2 py-3 font-medium text-warm-gray text-xs uppercase tracking-wide min-w-[70px]"
                      >
                        {day}
                      </th>
                    ))}
                    <th className="text-center px-3 py-3 font-medium text-warm-gray text-xs uppercase tracking-wide min-w-[60px]">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {productos.map((p, pIdx) => (
                    <tr
                      key={p.id}
                      className={`${
                        pIdx < productos.length - 1
                          ? "border-b border-cream-dark"
                          : ""
                      } hover:bg-cream/20 transition-colors`}
                    >
                      <td className="px-4 py-2.5">
                        <span className="font-medium text-text text-sm">
                          {p.nombre}
                        </span>
                        <span className="text-xs text-warm-gray ml-1">
                          ({p.unidad})
                        </span>
                      </td>
                      {DAYS_LABELS.map((_, dayIdx) => (
                        <td key={dayIdx} className="px-1.5 py-2">
                          <input
                            type="number"
                            min="0"
                            inputMode="numeric"
                            value={getCellValue(semana, dayIdx + 1, p.id)}
                            onChange={(e) =>
                              updateCell(semana, dayIdx + 1, p.id, e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </td>
                      ))}
                      <td className="px-3 py-2 text-center">
                        <span className="text-sm font-medium text-brot">
                          {getProductWeekTotal(semana, p.id) || "—"}
                        </span>
                      </td>
                    </tr>
                  ))}

                  {/* Day totals row */}
                  <tr className="border-t border-cream-dark bg-cream/40">
                    <td className="px-4 py-2.5 text-xs font-medium text-warm-gray uppercase tracking-wide">
                      Total día
                    </td>
                    {DAYS_LABELS.map((_, dayIdx) => (
                      <td key={dayIdx} className="px-1.5 py-2.5 text-center">
                        <span className="text-sm font-semibold text-text">
                          {getDayTotal(semana, dayIdx + 1) || "—"}
                        </span>
                      </td>
                    ))}
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile: one day at a time */}
          <div className="md:hidden space-y-3 mb-4">
            {/* Day selector */}
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {DAYS_FULL.map((day, i) => (
                <button
                  key={i}
                  onClick={() => {
                    // We'll use a local state for mobile day selection
                  }}
                  className="px-3 py-1.5 rounded-lg border border-cream-dark bg-white text-xs text-warm-gray hover:bg-cream whitespace-nowrap min-h-[36px]"
                >
                  {day}
                </button>
              ))}
            </div>

            {/* Full mobile table: products as rows, days as compact columns */}
            <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              <div className="overflow-x-auto">
                <table className="text-xs border-collapse w-full">
                  <thead>
                    <tr className="bg-cream/50 border-b border-cream-dark">
                      <th className="text-left px-3 py-2.5 font-medium text-warm-gray min-w-[110px]">
                        Producto
                      </th>
                      {DAYS_LABELS.map((d, i) => (
                        <th
                          key={i}
                          className="text-center px-1 py-2.5 font-medium text-warm-gray min-w-[42px]"
                        >
                          {d}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {productos.map((p, pIdx) => (
                      <tr
                        key={p.id}
                        className={
                          pIdx < productos.length - 1
                            ? "border-b border-cream-dark"
                            : ""
                        }
                      >
                        <td className="px-3 py-2 font-medium text-text">
                          {p.nombre}
                        </td>
                        {DAYS_LABELS.map((_, dayIdx) => (
                          <td key={dayIdx} className="px-0.5 py-1.5">
                            <input
                              type="number"
                              min="0"
                              inputMode="numeric"
                              value={getCellValue(semana, dayIdx + 1, p.id)}
                              onChange={(e) =>
                                updateCell(
                                  semana,
                                  dayIdx + 1,
                                  p.id,
                                  e.target.value
                                )
                              }
                              placeholder="—"
                              className="w-10 px-0.5 py-1 rounded border border-cream-dark bg-white text-center text-xs focus:outline-none focus:ring-1 focus:ring-brot/40 min-h-[34px]"
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Save button (bottom) */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => router.push("/produccion")}
              className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !dirty}
              className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Guardando..." : dirty ? "Guardar plan" : "Sin cambios"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
