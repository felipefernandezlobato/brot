"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface TareaDia {
  tarea_id: number;
  hora: string | null;
  titulo: string;
  descripcion: string | null;
  duracion_planificada: number | null;
  cantidad_planificada: number | null;
  unidad_cantidad: string | null;
  receta_id: number | null;
  receta_nombre: string | null;
  producto_congelado_id: number | null;
  tipo: string;
  registro_id: number | null;
  completada: boolean;
  cantidad_real: number | null;
  duracion_real: number | null;
  notas: string | null;
}

interface ExtraDia {
  registro_id: number;
  titulo: string;
  receta_id: number | null;
  unidad_cantidad: string | null;
  completada: boolean;
  cantidad_real: number | null;
  duracion_real: number | null;
  notas: string | null;
}

interface DiaData {
  fecha: string;
  dia_semana: number;
  dia_nombre: string;
  tareas: TareaDia[];
  extras: ExtraDia[];
}

interface RecetaDropdown {
  id: number;
  nombre: string;
  porciones_por_lote: number;
}

const TIPO_DOT: Record<string, string> = {
  produccion: "bg-[#004225]",
  limpieza: "bg-amber-500",
  nota: "bg-blue-500",
  entrega: "bg-purple-500",
  admin: "bg-gray-500",
};

function toLocalISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function displayDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function isDomingo(iso: string): boolean {
  return new Date(iso + "T12:00:00").getDay() === 0;
}

export default function ProduccionHoy() {
  const searchParams = useSearchParams();
  const paramFecha = searchParams.get("fecha");
  const [fecha, setFecha] = useState(() => paramFecha || toLocalISO(new Date()));
  const [data, setData] = useState<DiaData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [showExtraForm, setShowExtraForm] = useState(false);
  const [extraRecetaId, setExtraRecetaId] = useState("");
  const [extraCantidad, setExtraCantidad] = useState("");
  const [extraDuracion, setExtraDuracion] = useState("");
  const [extraNotas, setExtraNotas] = useState("");
  const [expandedNotes, setExpandedNotes] = useState<Set<number>>(new Set());
  const [recetas, setRecetas] = useState<RecetaDropdown[]>([]);
  const [bastonesMap, setBastonesMap] = useState<Record<number, string>>({});
  const { toast } = useToast();
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const draftKey = `brot_produccion_dia_${fecha}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, recs] = await Promise.all([
        apiFetch<DiaData>(`/api/produccion/dia?fecha=${fecha}`),
        apiFetch<RecetaDropdown[]>("/api/produccion/productos-dropdown"),
      ]);
      setData(d);
      setRecetas(recs);
    } catch {
      toast("Error cargando datos", "error");
    } finally {
      setLoading(false);
    }
  }, [fecha, toast]);

  useEffect(() => {
    load();
  }, [load]);

  function changeDay(offset: number) {
    const d = new Date(fecha + "T12:00:00");
    d.setDate(d.getDate() + offset);
    let next = toLocalISO(d);
    if (isDomingo(next)) {
      d.setDate(d.getDate() + (offset > 0 ? 1 : -1));
      next = toLocalISO(d);
    }
    setFecha(next);
    window.history.replaceState(null, "", `/produccion?fecha=${next}`);
  }

  function goToday() {
    const today = toLocalISO(new Date());
    setFecha(today);
    window.history.replaceState(null, "", `/produccion?fecha=${today}`);
  }

  async function saveRegistro(tarea: TareaDia, updates: Partial<TareaDia>) {
    const merged = { ...tarea, ...updates };
    const key = `save-${tarea.tarea_id}`;
    if (debounceTimers.current[key]) clearTimeout(debounceTimers.current[key]);

    debounceTimers.current[key] = setTimeout(async () => {
      setSaving(tarea.tarea_id);
      try {
        await apiFetch("/api/produccion/registro", {
          method: "POST",
          body: JSON.stringify({
            tarea_id: tarea.tarea_id,
            fecha,
            completada: merged.completada,
            cantidad_real: merged.cantidad_real,
            duracion_real: merged.duracion_real,
            notas: merged.notas,
          }),
        });
      } catch {
        toast("Error al guardar", "error");
      } finally {
        setSaving(null);
      }
    }, 500);

    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        tareas: prev.tareas.map((t) =>
          t.tarea_id === tarea.tarea_id ? { ...t, ...updates } : t
        ),
      };
    });
  }

  async function toggleComplete(tarea: TareaDia) {
    const newVal = !tarea.completada;
    await saveRegistro(tarea, { completada: newVal });

    if (newVal && tarea.producto_congelado_id && tarea.cantidad_real) {
      try {
        const body: Record<string, unknown> = {
          producto_id: tarea.producto_congelado_id,
          cantidad_producida: tarea.cantidad_real,
        };
        const bast = bastonesMap[tarea.tarea_id];
        if (bast && parseFloat(bast) > 0) {
          body.bastones_consumidos = parseFloat(bast);
        }
        await apiFetch("/api/produccion/producir", {
          method: "POST",
          body: JSON.stringify(body),
        });
        toast("Stock actualizado");
      } catch {
        toast("Error al actualizar stock", "error");
      }
    }
  }

  async function submitExtra() {
    if (!extraRecetaId) return;
    try {
      await apiFetch("/api/produccion/registro/extra", {
        method: "POST",
        body: JSON.stringify({
          fecha,
          receta_id: parseInt(extraRecetaId),
          cantidad_real: extraCantidad ? parseFloat(extraCantidad.replace(",", ".")) : null,
          duracion_real: extraDuracion ? parseInt(extraDuracion) : null,
          notas: extraNotas || null,
        }),
      });
      setShowExtraForm(false);
      setExtraRecetaId("");
      setExtraCantidad("");
      setExtraDuracion("");
      setExtraNotas("");
      toast("Produccion extra registrada", "success");
      load();
    } catch {
      toast("Error al registrar", "error");
    }
  }

  async function deleteExtra(id: number) {
    if (!confirm("Eliminar este registro?")) return;
    try {
      await apiFetch(`/api/produccion/registro/${id}`, { method: "DELETE" });
      toast("Eliminado", "success");
      load();
    } catch {
      toast("Error al eliminar", "error");
    }
  }

  function toggleNotes(tareaId: number) {
    setExpandedNotes((prev) => {
      const next = new Set(prev);
      if (next.has(tareaId)) next.delete(tareaId);
      else next.add(tareaId);
      return next;
    });
  }

  const isToday = fecha === toLocalISO(new Date());
  const timedTareas = data?.tareas.filter((t) => t.hora !== null) || [];
  const noteTareas = data?.tareas.filter((t) => t.hora === null) || [];
  const completedCount = data?.tareas.filter((t) => t.completada).length || 0;
  const totalCount = data?.tareas.length || 0;

  if (loading) {
    return <p className="text-center py-12 text-gray-500">Cargando...</p>;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h1 className="font-[family-name:var(--font-garamond)] text-2xl text-gray-900">
          Produccion
        </h1>
        <div className="flex gap-2">
          <Link
            href="/produccion/producir"
            className="text-sm bg-brot text-white px-3 py-2 rounded-lg hover:bg-brot-dark transition-colors"
            style={{ minHeight: 44, display: "flex", alignItems: "center" }}
          >
            Producir
          </Link>
          <Link
            href="/produccion/calendario"
            className="text-sm text-[#004225] border border-[#004225]/30 px-3 py-2 rounded-lg hover:bg-[#004225]/5 transition-colors"
            style={{ minHeight: 44, display: "flex", alignItems: "center" }}
          >
            Calendario
          </Link>
          <Link
            href="/produccion/analytics"
            className="text-sm text-[#004225] border border-[#004225]/30 px-3 py-2 rounded-lg hover:bg-[#004225]/5 transition-colors"
            style={{ minHeight: 44, display: "flex", alignItems: "center" }}
          >
            Analytics
          </Link>
        </div>
      </div>

      {/* Day nav */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => changeDay(-1)}
          className="w-10 h-10 flex items-center justify-center rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-lg"
          style={{ touchAction: "manipulation" }}
        >
          &lsaquo;
        </button>
        <button
          onClick={goToday}
          className={`px-3 py-2 rounded-lg text-sm transition-colors ${
            isToday
              ? "bg-[#004225] text-white"
              : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
          }`}
          style={{ touchAction: "manipulation", minHeight: 40 }}
        >
          Hoy
        </button>
        <button
          onClick={() => changeDay(1)}
          className="w-10 h-10 flex items-center justify-center rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-lg"
          style={{ touchAction: "manipulation" }}
        >
          &rsaquo;
        </button>
        <div className="ml-2">
          <p className="text-sm font-semibold text-gray-800">
            {data?.dia_nombre} {displayDate(fecha)}
          </p>
          <p className="text-xs text-gray-400">
            {completedCount}/{totalCount} completadas
          </p>
        </div>
      </div>

      {/* Progress bar */}
      {totalCount > 0 && (
        <div className="h-2 bg-gray-100 rounded-full mb-4 overflow-hidden">
          <div
            className="h-full bg-[#004225] rounded-full transition-all duration-300"
            style={{ width: `${(completedCount / totalCount) * 100}%` }}
          />
        </div>
      )}

      {/* No tasks for Sunday */}
      {!data || data.tareas.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
          Sin tareas planificadas para este dia
        </div>
      ) : (
        <>
          {/* Timed tasks */}
          <div className="space-y-2">
            {timedTareas.map((tarea) => {
              const dot = TIPO_DOT[tarea.tipo] || TIPO_DOT.produccion;
              const notesOpen = expandedNotes.has(tarea.tarea_id);
              const isSaving = saving === tarea.tarea_id;
              return (
                <div
                  key={tarea.tarea_id}
                  className={`bg-white rounded-xl border p-3 transition-all ${
                    tarea.completada
                      ? "border-green-200 bg-green-50/50"
                      : "border-gray-200"
                  }`}
                >
                  {/* Row 1: checkbox + title + time */}
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => toggleComplete(tarea)}
                      className={`w-7 h-7 rounded-lg border-2 flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                        tarea.completada
                          ? "bg-[#004225] border-[#004225] text-white"
                          : "border-gray-300 hover:border-[#004225]"
                      }`}
                      style={{ touchAction: "manipulation" }}
                    >
                      {tarea.completada && (
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </button>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                        <span className="text-xs text-gray-400 font-mono">
                          {tarea.hora?.replace(":00", "h")}
                        </span>
                        <span className={`text-sm font-medium ${tarea.completada ? "text-gray-500 line-through" : "text-gray-900"}`}>
                          {tarea.titulo}
                        </span>
                        {isSaving && <span className="text-[10px] text-gray-400">...</span>}
                      </div>
                      {tarea.descripcion && (
                        <p className="text-xs text-gray-400 mt-0.5 whitespace-pre-line line-clamp-2 ml-4">
                          {tarea.descripcion}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Row 2: inputs */}
                  <div className="flex items-center gap-2 mt-2 ml-10 flex-wrap">
                    {/* Bastones input for tasks that consume bastones */}
                    {tarea.descripcion && tarea.descripcion.toLowerCase().includes("baston") && (
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          inputMode="decimal"
                          placeholder="1"
                          value={bastonesMap[tarea.tarea_id] ?? ""}
                          onChange={(e) => setBastonesMap((prev) => ({ ...prev, [tarea.tarea_id]: e.target.value }))}
                          className="w-14 border border-blue-200 bg-blue-50/50 rounded-lg px-2 py-1.5 text-sm text-center focus:ring-2 focus:ring-blue-400/30 focus:border-blue-400 outline-none"
                          style={{ minHeight: 36 }}
                        />
                        <span className="text-xs text-blue-500">bast.</span>
                      </div>
                    )}
                    {tarea.cantidad_planificada !== null && (
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          inputMode="decimal"
                          placeholder={String(tarea.cantidad_planificada)}
                          value={tarea.cantidad_real ?? ""}
                          onChange={(e) => {
                            const val = e.target.value ? parseFloat(e.target.value.replace(",", ".")) : null;
                            saveRegistro(tarea, { cantidad_real: val });
                          }}
                          className="w-16 border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-center focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                          style={{ minHeight: 36 }}
                        />
                        <span className="text-xs text-gray-400">
                          /{tarea.cantidad_planificada} {tarea.unidad_cantidad}
                        </span>
                      </div>
                    )}
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        inputMode="numeric"
                        placeholder={tarea.duracion_planificada ? String(tarea.duracion_planificada) : "-"}
                        value={tarea.duracion_real ?? ""}
                        onChange={(e) => {
                          const val = e.target.value ? parseInt(e.target.value) : null;
                          saveRegistro(tarea, { duracion_real: val });
                        }}
                        className="w-14 border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-center focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                        style={{ minHeight: 36 }}
                      />
                      <span className="text-xs text-gray-400">min</span>
                    </div>
                    <button
                      onClick={() => toggleNotes(tarea.tarea_id)}
                      className={`ml-auto px-2 py-1 rounded text-xs transition-colors ${
                        tarea.notas
                          ? "text-[#004225] bg-[#004225]/10"
                          : "text-gray-400 hover:text-gray-600"
                      }`}
                      style={{ touchAction: "manipulation", minHeight: 36 }}
                    >
                      {tarea.notas ? "Notas" : "+ Nota"}
                    </button>
                  </div>

                  {/* Row 3: notes (expandable) */}
                  {notesOpen && (
                    <div className="mt-2 ml-10">
                      <textarea
                        value={tarea.notas || ""}
                        onChange={(e) => saveRegistro(tarea, { notas: e.target.value || null })}
                        placeholder="Agregar nota..."
                        rows={2}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none resize-none"
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Note tasks (no time slot) */}
          {noteTareas.length > 0 && (
            <div className="mt-4 space-y-1">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
                Recordatorios
              </p>
              {noteTareas.map((tarea) => {
                const dot = TIPO_DOT[tarea.tipo] || TIPO_DOT.nota;
                return (
                  <div
                    key={tarea.tarea_id}
                    className="flex items-center gap-2 bg-white rounded-lg border border-gray-200 px-3 py-2"
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                    <span className="text-sm text-gray-700">{tarea.titulo}</span>
                    {tarea.duracion_planificada && (
                      <span className="text-xs text-gray-400 ml-auto">
                        {tarea.duracion_planificada} min
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* Extras section */}
      {(data?.extras?.length ?? 0) > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
            Produccion extra
          </p>
          <div className="space-y-1">
            {data!.extras.map((extra) => (
              <div
                key={extra.registro_id}
                className="flex items-center gap-2 bg-white rounded-lg border border-dashed border-gray-300 px-3 py-2"
              >
                <span className="w-2 h-2 rounded-full shrink-0 bg-teal-500" />
                <span className="text-sm text-gray-700 font-medium">{extra.titulo}</span>
                {extra.cantidad_real !== null && (
                  <span className="text-xs text-gray-500">
                    {extra.cantidad_real} {extra.unidad_cantidad || ""}
                  </span>
                )}
                {extra.duracion_real !== null && (
                  <span className="text-xs text-gray-400">{extra.duracion_real} min</span>
                )}
                <button
                  onClick={() => deleteExtra(extra.registro_id)}
                  className="ml-auto text-xs text-red-400 hover:text-red-600"
                  style={{ touchAction: "manipulation", minHeight: 36, minWidth: 36 }}
                >
                  x
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add extra button / form */}
      <div className="mt-4">
        {!showExtraForm ? (
          <button
            onClick={() => setShowExtraForm(true)}
            className="w-full border-2 border-dashed border-gray-300 text-gray-400 rounded-xl py-3 text-sm hover:border-[#004225] hover:text-[#004225] transition-colors"
            style={{ touchAction: "manipulation", minHeight: 48 }}
          >
            + Agregar produccion extra
          </button>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-sm font-medium text-gray-700 mb-3">
              Nueva produccion extra
            </p>
            <div className="space-y-2">
              <select
                value={extraRecetaId}
                onChange={(e) => setExtraRecetaId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                style={{ minHeight: 44 }}
              >
                <option value="">Seleccionar producto...</option>
                {recetas.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.nombre}
                  </option>
                ))}
              </select>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  inputMode="decimal"
                  placeholder="Cantidad"
                  value={extraCantidad}
                  onChange={(e) => setExtraCantidad(e.target.value)}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                  style={{ minHeight: 44 }}
                />
                <input
                  type="number"
                  inputMode="numeric"
                  placeholder="Minutos"
                  value={extraDuracion}
                  onChange={(e) => setExtraDuracion(e.target.value)}
                  className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                  style={{ minHeight: 44 }}
                />
              </div>
              <textarea
                placeholder="Notas (opcional)"
                value={extraNotas}
                onChange={(e) => setExtraNotas(e.target.value)}
                rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none resize-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={submitExtra}
                  disabled={!extraRecetaId}
                  className="flex-1 bg-[#004225] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[#003319] disabled:opacity-50 transition-colors"
                  style={{ touchAction: "manipulation", minHeight: 44 }}
                >
                  Guardar
                </button>
                <button
                  onClick={() => setShowExtraForm(false)}
                  className="px-4 py-2.5 rounded-lg text-sm text-gray-500 border border-gray-200 hover:bg-gray-50 transition-colors"
                  style={{ touchAction: "manipulation", minHeight: 44 }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
