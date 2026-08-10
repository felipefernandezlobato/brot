"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface LogItem {
  id?: number;
  producto_id: number;
  producto_nombre: string;
  cantidad_planificada: number;
  cantidad_real: string;
  tiempo_maquina: string;
  tiempo_humano: string;
  noplanificado?: boolean;
}

interface ProductoProduccion {
  id: number;
  nombre: string;
  unidad: string;
  is_active: boolean;
}

interface LogEntryApi {
  id: number;
  producto_id: number;
  target_date: string;
  planned_qty: number | null;
  actual_qty: number | null;
  duration_minutes_machine: number | null;
  duration_minutes_human: number | null;
  is_unplanned: boolean;
  notes: string | null;
  recorded_by: number;
  recorded_at: string;
}

function formatDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function formatDisplayDate(dateStr: string): string {
  const [y, m, day] = dateStr.split("-");
  const names = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
  ];
  return `${day} de ${names[Number(m) - 1]} de ${y}`;
}

export default function RegistroProduccionPage() {
  const router = useRouter();
  const { toast } = useToast();

  const today = formatDate(new Date());
  const [fecha, setFecha] = useState(today);
  const [items, setItems] = useState<LogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showUnplanned, setShowUnplanned] = useState(false);
  const [productos, setProductos] = useState<ProductoProduccion[]>([]);
  const [unplannedId, setUnplannedId] = useState("");

  const loadLog = useCallback(async () => {
    setLoading(true);
    try {
      const [logData, calData, prods] = await Promise.all([
        apiFetch<LogEntryApi[]>(`/api/produccion/log?fecha=${fecha}`),
        apiFetch<{ producto_id: number; planned_qty: number | null; actual_qty: number | null }[]>(
          `/api/produccion/calendario?fecha_desde=${fecha}&fecha_hasta=${fecha}`
        ),
        apiFetch<ProductoProduccion[]>("/api/produccion/productos"),
      ]);
      const prodMap = new Map(prods.map((p) => [p.id, p.nombre]));
      const logMap = new Map(logData.map((e) => [e.producto_id, e]));
      const seen = new Set<number>();
      const merged: LogItem[] = [];
      for (const cal of calData) {
        seen.add(cal.producto_id);
        const log = logMap.get(cal.producto_id);
        merged.push({
          id: log?.id,
          producto_id: cal.producto_id,
          producto_nombre: prodMap.get(cal.producto_id) || `Producto ${cal.producto_id}`,
          cantidad_planificada: cal.planned_qty || 0,
          cantidad_real: log?.actual_qty?.toString() ?? "",
          tiempo_maquina: log?.duration_minutes_machine?.toString() ?? "",
          tiempo_humano: log?.duration_minutes_human?.toString() ?? "",
        });
      }
      for (const log of logData) {
        if (!seen.has(log.producto_id)) {
          merged.push({
            id: log.id,
            producto_id: log.producto_id,
            producto_nombre: prodMap.get(log.producto_id) || `Producto ${log.producto_id}`,
            cantidad_planificada: log.planned_qty || 0,
            cantidad_real: log.actual_qty?.toString() ?? "",
            tiempo_maquina: log.duration_minutes_machine?.toString() ?? "",
            tiempo_humano: log.duration_minutes_human?.toString() ?? "",
          });
        }
      }
      const draftKey = `brot_produccion_draft_${fecha}`;
      const draft = sessionStorage.getItem(draftKey);
      if (draft) {
        try {
          const saved = JSON.parse(draft) as LogItem[];
          const draftMap = new Map(saved.map((s) => [s.producto_id, s]));
          for (const item of merged) {
            const d = draftMap.get(item.producto_id);
            if (d) {
              item.cantidad_real = d.cantidad_real;
              item.tiempo_maquina = d.tiempo_maquina;
              item.tiempo_humano = d.tiempo_humano;
            }
          }
          const unplanned = saved.filter((s) => s.noplanificado && !merged.some((m) => m.producto_id === s.producto_id));
          merged.push(...unplanned);
        } catch {}
      }
      setItems(merged);
      setProductos(prods.filter((p) => p.is_active));
    } catch {
      toast("Error al cargar el registro de producción", "error");
    } finally {
      setLoading(false);
    }
  }, [fecha]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadLog();
  }, [loadLog]);

  useEffect(() => {
    apiFetch<ProductoProduccion[]>("/api/produccion/productos")
      .then((data) => setProductos(data.filter((p) => p.is_active)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!loading && items.length > 0) {
      sessionStorage.setItem(`brot_produccion_draft_${fecha}`, JSON.stringify(items));
    }
  }, [items, fecha, loading]);

  function updateItem(
    idx: number,
    field: "cantidad_real" | "tiempo_maquina" | "tiempo_humano",
    value: string
  ) {
    setItems((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, [field]: value } : item))
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload = items.map((item) => ({
        producto_id: item.producto_id,
        target_date: fecha,
        actual_qty: item.cantidad_real !== "" ? Number(item.cantidad_real) : null,
        duration_minutes_machine:
          item.tiempo_maquina !== "" ? Number(item.tiempo_maquina) : null,
        duration_minutes_human:
          item.tiempo_humano !== "" ? Number(item.tiempo_humano) : null,
      }));
      await apiFetch(`/api/produccion/log?fecha=${fecha}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      sessionStorage.removeItem(`brot_produccion_draft_${fecha}`);
      toast("Registro guardado correctamente");
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al guardar el registro",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }

  function addUnplanned() {
    if (!unplannedId) return;
    const prod = productos.find((p) => p.id === Number(unplannedId));
    if (!prod) return;
    const exists = items.some((it) => it.producto_id === prod.id);
    if (exists) {
      toast("Este producto ya está en el registro", "error");
      return;
    }
    setItems((prev) => [
      ...prev,
      {
        producto_id: prod.id,
        producto_nombre: prod.nombre,
        cantidad_planificada: 0,
        cantidad_real: "",
        tiempo_maquina: "",
        tiempo_humano: "",
        noplanificado: true,
      },
    ]);
    setUnplannedId("");
    setShowUnplanned(false);
  }

  function removeUnplanned(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  const plannedItems = items.filter((it) => !it.noplanificado);
  const unplannedItems = items.filter((it) => it.noplanificado);

  const inputCls =
    "w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-text text-sm placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] text-center";

  return (
    <div className="max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/produccion")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <div>
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Registro de Producción
          </h1>
          <p className="text-sm text-warm-gray mt-0.5">
            {formatDisplayDate(fecha)}
          </p>
        </div>
      </div>

      {/* Date picker */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4 flex items-center gap-3">
        <label className="text-sm font-medium text-text shrink-0">Fecha:</label>
        <input
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          max={today}
          className="px-3 py-2 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : (
        <>
          {/* Planned items */}
          {plannedItems.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
              <div className="px-4 py-3 border-b border-cream-dark bg-cream/40">
                <h2 className="text-sm font-medium text-text">
                  Producción planificada
                </h2>
              </div>

              {/* Desktop table */}
              <div className="hidden md:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-cream-dark text-xs text-warm-gray uppercase tracking-wide">
                      <th className="text-left px-4 py-2.5">Producto</th>
                      <th className="text-center px-3 py-2.5">Planificado</th>
                      <th className="text-center px-3 py-2.5">Real</th>
                      <th className="text-center px-3 py-2.5">T. Máquina (min)</th>
                      <th className="text-center px-3 py-2.5">T. Humano (min)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plannedItems.map((item, rawIdx) => {
                      const idx = items.indexOf(item);
                      return (
                        <tr
                          key={item.producto_id}
                          className="border-b border-cream-dark last:border-0"
                        >
                          <td className="px-4 py-3">
                            <span className="font-medium text-text">
                              {item.producto_nombre}
                            </span>
                          </td>
                          <td className="px-3 py-3 text-center text-warm-gray">
                            {item.cantidad_planificada}
                          </td>
                          <td className="px-3 py-3">
                            <input
                              type="number"
                              min="0"
                              inputMode="decimal"
                              value={item.cantidad_real}
                              onChange={(e) =>
                                updateItem(idx, "cantidad_real", e.target.value)
                              }
                              placeholder="—"
                              className={inputCls}
                            />
                          </td>
                          <td className="px-3 py-3">
                            <input
                              type="number"
                              min="0"
                              inputMode="decimal"
                              value={item.tiempo_maquina}
                              onChange={(e) =>
                                updateItem(idx, "tiempo_maquina", e.target.value)
                              }
                              placeholder="—"
                              className={inputCls}
                            />
                          </td>
                          <td className="px-3 py-3">
                            <input
                              type="number"
                              min="0"
                              inputMode="decimal"
                              value={item.tiempo_humano}
                              onChange={(e) =>
                                updateItem(idx, "tiempo_humano", e.target.value)
                              }
                              placeholder="—"
                              className={inputCls}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden divide-y divide-cream-dark">
                {plannedItems.map((item) => {
                  const idx = items.indexOf(item);
                  return (
                    <div key={item.producto_id} className="px-4 py-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-text">
                          {item.producto_nombre}
                        </span>
                        <span className="text-xs text-warm-gray bg-cream px-2 py-1 rounded-full">
                          Plan: {item.cantidad_planificada}
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="block text-xs text-warm-gray mb-1">
                            Real
                          </label>
                          <input
                            type="number"
                            min="0"
                            inputMode="decimal"
                            value={item.cantidad_real}
                            onChange={(e) =>
                              updateItem(idx, "cantidad_real", e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-warm-gray mb-1">
                            T. Máq. (min)
                          </label>
                          <input
                            type="number"
                            min="0"
                            inputMode="decimal"
                            value={item.tiempo_maquina}
                            onChange={(e) =>
                              updateItem(idx, "tiempo_maquina", e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-warm-gray mb-1">
                            T. Hum. (min)
                          </label>
                          <input
                            type="number"
                            min="0"
                            inputMode="decimal"
                            value={item.tiempo_humano}
                            onChange={(e) =>
                              updateItem(idx, "tiempo_humano", e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Unplanned items */}
          {unplannedItems.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
              <div className="px-4 py-3 border-b border-cream-dark bg-yellow-50">
                <h2 className="text-sm font-medium text-text">
                  Producción no planificada
                </h2>
              </div>
              <div className="divide-y divide-cream-dark">
                {unplannedItems.map((item) => {
                  const idx = items.indexOf(item);
                  return (
                    <div key={item.producto_id} className="px-4 py-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-text">
                          {item.producto_nombre}
                        </span>
                        <button
                          onClick={() => removeUnplanned(idx)}
                          className="text-xs text-red-500 hover:text-red-700 min-h-[44px] px-2"
                        >
                          Quitar
                        </button>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="block text-xs text-warm-gray mb-1">
                            Real
                          </label>
                          <input
                            type="number"
                            min="0"
                            inputMode="decimal"
                            value={item.cantidad_real}
                            onChange={(e) =>
                              updateItem(idx, "cantidad_real", e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-warm-gray mb-1">
                            T. Máq. (min)
                          </label>
                          <input
                            type="number"
                            min="0"
                            inputMode="decimal"
                            value={item.tiempo_maquina}
                            onChange={(e) =>
                              updateItem(idx, "tiempo_maquina", e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-warm-gray mb-1">
                            T. Hum. (min)
                          </label>
                          <input
                            type="number"
                            min="0"
                            inputMode="decimal"
                            value={item.tiempo_humano}
                            onChange={(e) =>
                              updateItem(idx, "tiempo_humano", e.target.value)
                            }
                            placeholder="—"
                            className={inputCls}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* No items */}
          {items.length === 0 && (
            <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray mb-4">
              No hay producción planificada para esta fecha.
            </div>
          )}

          {/* Add unplanned */}
          <div className="mb-6">
            {showUnplanned ? (
              <div className="bg-white rounded-xl border border-cream-dark p-4 flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-text mb-1">
                    Producto no planificado
                  </label>
                  <select
                    value={unplannedId}
                    onChange={(e) => setUnplannedId(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
                  >
                    <option value="">Seleccionar producto...</option>
                    {productos
                      .filter(
                        (p) => !items.some((it) => it.producto_id === p.id)
                      )
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.nombre}
                        </option>
                      ))}
                  </select>
                </div>
                <button
                  onClick={addUnplanned}
                  disabled={!unplannedId}
                  className="px-4 py-2.5 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] disabled:opacity-50"
                >
                  Añadir
                </button>
                <button
                  onClick={() => setShowUnplanned(false)}
                  className="px-4 py-2.5 border border-cream-dark bg-white text-warm-gray rounded-lg text-sm font-medium hover:bg-cream transition-colors min-h-[44px]"
                >
                  Cancelar
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowUnplanned(true)}
                className="w-full border-2 border-dashed border-cream-dark rounded-xl py-3 text-sm text-warm-gray hover:border-brot hover:text-brot transition-colors min-h-[44px]"
              >
                + Añadir producción no planificada
              </button>
            )}
          </div>

          {/* Save */}
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
              disabled={saving || items.length === 0}
              className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Guardando..." : "Guardar registro"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
