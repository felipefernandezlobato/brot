"use client";

import { useEffect, useState, useCallback } from "react";
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
  necesita_bastones: boolean;
  tipo: string;
  registro_id: number | null;
  completada: boolean;
  cantidad_real: number | null;
  duracion_real: number | null;
  notas: string | null;
  bastones_consumidos: number | null;
  porciones_por_lote: number | null;
  ingrediente_principal: IngredientePrincipal | null;
}

interface IngredientePrincipal {
  nombre: string;
  cantidad_por_receta: number;
  unidad: string;
}

/** What the operator is typing, before it's saved. */
interface Draft {
  cantidad: string;
  duracion: string;
  bastones: string;
  notas: string;
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
  const [extraProductoId, setExtraProductoId] = useState("");
  const [extraBastones, setExtraBastones] = useState("");
  const [extraCantidad, setExtraCantidad] = useState("");
  const [extraDuracion, setExtraDuracion] = useState("");
  const [extraNotas, setExtraNotas] = useState("");
  const [expandedNotes, setExpandedNotes] = useState<Set<number>>(new Set());
  const [recetas, setRecetas] = useState<RecetaDropdown[]>([]);
  const [productosCongelados, setProductosCongelados] = useState<{id:number;nombre:string;nivel:string;necesita_bastones?:boolean}[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [editando, setEditando] = useState<Set<number>>(new Set());
  const { toast } = useToast();

  const draftKey = `brot_produccion_dia_${fecha}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, recs, prods] = await Promise.all([
        apiFetch<DiaData>(`/api/produccion/dia?fecha=${fecha}`),
        apiFetch<RecetaDropdown[]>("/api/produccion/productos-dropdown"),
        apiFetch<{id:number;nombre:string;nivel:string;producto_padre_id:number|null;cantidad_por_padre:number|null}[]>("/api/congelados/productos"),
      ]);
      setData(d);
      setRecetas(recs);
      // Restore any unsaved typing for this day — nothing is lost just because the
      // tab closed before someone hit Guardar.
      const saved = sessionStorage.getItem(`brot_produccion_dia_${fecha}`);
      let restored: Record<number, Draft> = {};
      if (saved) {
        try { restored = JSON.parse(saved); } catch { /* corrupt draft, ignore */ }
      }
      setDrafts(restored);
      setEditando(new Set());
      const prodMap = new Map(prods.map(p => [p.id, p]));
      setProductosCongelados(prods.filter((p: any) => p.is_active).map((p: any) => {
        const padre = p.producto_padre_id ? prodMap.get(p.producto_padre_id) : null;
        return {
          ...p,
          necesita_bastones: padre && (padre as any).nivel === "semi" && (padre as any).nombre.toLowerCase().includes("baston"),
        };
      }).sort((a: any, b: any) => a.nombre.localeCompare(b.nombre)));
    } catch {
      toast("Error cargando datos", "error");
    } finally {
      setLoading(false);
    }
  }, [fecha, toast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (Object.keys(drafts).length > 0) {
      sessionStorage.setItem(draftKey, JSON.stringify(drafts));
    } else {
      sessionStorage.removeItem(draftKey);
    }
  }, [drafts, draftKey]);

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

  function num(s: string): number | null {
    if (!s.trim()) return null;
    const n = parseFloat(s.replace(",", "."));
    return Number.isFinite(n) ? n : null;
  }

  /** The draft being edited, falling back to whatever is already saved. */
  function draftOf(tarea: TareaDia): Draft {
    return (
      drafts[tarea.tarea_id] ?? {
        cantidad: tarea.cantidad_real != null ? String(tarea.cantidad_real) : "",
        duracion: tarea.duracion_real != null ? String(tarea.duracion_real) : "",
        bastones: tarea.bastones_consumidos != null ? String(tarea.bastones_consumidos) : "",
        notas: tarea.notas ?? "",
      }
    );
  }

  function setDraft(tarea: TareaDia, patch: Partial<Draft>) {
    setDrafts((prev) => ({
      ...prev,
      [tarea.tarea_id]: { ...draftOf(tarea), ...patch },
    }));
  }

  /** Saving is the only thing that moves stock — no quantity, no save. */
  function puedeGuardar(tarea: TareaDia): boolean {
    if (!tarea.producto_congelado_id) return true;
    const c = num(draftOf(tarea).cantidad);
    return c !== null && c > 0;
  }

  async function guardar(tarea: TareaDia, completada = true) {
    if (completada && !puedeGuardar(tarea)) return;
    const d = draftOf(tarea);
    setSaving(tarea.tarea_id);
    try {
      const res = await apiFetch<{ movimientos: number }>("/api/produccion/registro", {
        method: "POST",
        body: JSON.stringify({
          tarea_id: tarea.tarea_id,
          fecha,
          completada,
          cantidad_real: num(d.cantidad),
          duracion_real: d.duracion ? parseInt(d.duracion) : null,
          notas: d.notas || null,
          bastones_consumidos: num(d.bastones),
        }),
      });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[tarea.tarea_id];
        return next;
      });
      setEditando((prev) => {
        const next = new Set(prev);
        next.delete(tarea.tarea_id);
        return next;
      });
      if (!completada) toast("Stock devuelto");
      else if (res.movimientos > 0) toast(`Guardado · ${res.movimientos} movimientos de stock`);
      else toast("Guardado");
      await load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      toast(msg.includes("cantidad") ? "Ingresa la cantidad producida" : "Error al guardar", "error");
    } finally {
      setSaving(null);
    }
  }

  function fmt(n: number): string {
    return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, "").replace(".", ",");
  }

  /** Recipe lines are in g/ml; show kg/L once the number gets unwieldy. */
  function fmtCantidad(valor: number, unidad: string): string {
    if (unidad === "g" && valor >= 1000) return `${fmt(valor / 1000)} kg`;
    if (unidad === "ml" && valor >= 1000) return `${fmt(valor / 1000)} L`;
    return `${fmt(valor)} ${unidad}`;
  }

  /** "2 recetas · 24 kg Harina 000" — what was saved and what it moved. */
  function resumenGuardado(tarea: TareaDia): string {
    const partes: string[] = [];
    if (tarea.cantidad_real != null) {
      partes.push(`${fmt(tarea.cantidad_real)} ${tarea.unidad_cantidad ?? ""}`.trim());
    }
    const ing = tarea.ingrediente_principal;
    if (ing && tarea.cantidad_real != null) {
      partes.push(
        `${fmtCantidad(consumoPrincipal(tarea, tarea.cantidad_real), ing.unidad)} ${ing.nombre}`
      );
    }
    if (tarea.bastones_consumidos != null) {
      partes.push(`${fmt(tarea.bastones_consumidos)} bastones`);
    }
    if (tarea.duracion_real != null) partes.push(`${tarea.duracion_real} min`);
    return partes.length ? partes.join(" · ") : "completada";
  }

  function consumoPrincipal(tarea: TareaDia, cantidad: number): number {
    const ing = tarea.ingrediente_principal;
    if (!ing) return 0;
    // A task measured in "u receta" consumes whole recipes; anything else is
    // already in portions, so scale by the batch yield.
    const recetas =
      tarea.unidad_cantidad === "u receta"
        ? cantidad
        : cantidad / (tarea.porciones_por_lote || 1);
    return ing.cantidad_por_receta * recetas;
  }

  /** Shown while typing, so a wrong number is caught before it moves stock. */
  function previewConsumo(tarea: TareaDia, cantidadStr: string): string | null {
    const c = num(cantidadStr);
    if (c === null || c <= 0 || !tarea.ingrediente_principal) return null;
    const ing = tarea.ingrediente_principal;
    const partes = [`${fmtCantidad(consumoPrincipal(tarea, c), ing.unidad)} ${ing.nombre}`];
    if (tarea.unidad_cantidad === "u receta" && (tarea.porciones_por_lote || 1) > 1) {
      partes.unshift(`${fmt(c * (tarea.porciones_por_lote || 1))} porciones`);
    }
    return `Va a descontar: ${partes.join(" · ")}`;
  }

  function editar(tarea: TareaDia) {
    setEditando((prev) => new Set(prev).add(tarea.tarea_id));
  }

  function cancelarEdicion(tarea: TareaDia) {
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[tarea.tarea_id];
      return next;
    });
    setEditando((prev) => {
      const next = new Set(prev);
      next.delete(tarea.tarea_id);
      return next;
    });
  }

  async function submitExtra() {
    if (!extraProductoId || !extraCantidad) return;
    try {
      const body: Record<string, unknown> = {
        producto_id: parseInt(extraProductoId),
        cantidad_producida: num(extraCantidad),
        fecha,
        duracion_real: extraDuracion ? parseInt(extraDuracion) : null,
        notas: extraNotas || null,
      };
      const bast = num(extraBastones);
      if (bast !== null && bast > 0) {
        body.bastones_consumidos = bast;
      }
      await apiFetch("/api/produccion/producir", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setShowExtraForm(false);
      setExtraProductoId("");
      setExtraBastones("");
      setExtraCantidad("");
      setExtraDuracion("");
      setExtraNotas("");
      toast("Produccion extra registrada");
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
              const d = draftOf(tarea);
              const enEdicion = editando.has(tarea.tarea_id);
              const guardado = tarea.completada && !enEdicion;
              const habilitado = puedeGuardar(tarea);

              return (
                <div
                  key={tarea.tarea_id}
                  className={`bg-white rounded-xl border p-3 transition-all ${
                    guardado ? "border-green-200 bg-green-50/50" : "border-gray-200"
                  }`}
                >
                  {/* Row 1: status + title + time */}
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-7 h-7 rounded-lg border-2 flex items-center justify-center shrink-0 mt-0.5 ${
                        guardado
                          ? "bg-[#004225] border-[#004225] text-white"
                          : "border-gray-300"
                      }`}
                    >
                      {guardado && (
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full shrink-0 ${dot}`} />
                        <span className="text-xs text-gray-400 font-mono">
                          {tarea.hora?.replace(":00", "h")}
                        </span>
                        {tarea.producto_congelado_id ? (
                          <Link href={`/congelados/${tarea.producto_congelado_id}`}
                            className={`text-sm font-medium hover:text-brot hover:underline ${guardado ? "text-gray-500" : "text-gray-900"}`}
                            onClick={(e) => e.stopPropagation()}>
                            {tarea.titulo}
                          </Link>
                        ) : (
                          <span className={`text-sm font-medium ${guardado ? "text-gray-500" : "text-gray-900"}`}>
                            {tarea.titulo}
                          </span>
                        )}
                        {isSaving && <span className="text-[10px] text-gray-400">...</span>}
                      </div>
                      {tarea.descripcion && !guardado && (
                        <p className="text-xs text-gray-400 mt-0.5 whitespace-pre-line line-clamp-2 ml-4">
                          {tarea.descripcion}
                        </p>
                      )}
                    </div>
                  </div>

                  {guardado ? (
                    /* ---------- SAVED ---------- */
                    <div className="flex items-center gap-2 mt-2 ml-10 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-green-800 font-medium">
                          Guardado: {resumenGuardado(tarea)}
                        </p>
                        {tarea.notas && (
                          <p className="text-xs text-gray-500 mt-0.5 whitespace-pre-line">{tarea.notas}</p>
                        )}
                      </div>
                      <button
                        onClick={() => editar(tarea)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#004225] border border-[#004225]/30 hover:bg-[#004225]/5 transition-colors"
                        style={{ touchAction: "manipulation", minHeight: 36 }}
                      >
                        Editar
                      </button>
                    </div>
                  ) : (
                    /* ---------- EDITING ---------- */
                    <>
                      <div className="flex items-center gap-2 mt-2 ml-10 flex-wrap">
                        {tarea.necesita_bastones && (
                          <div className="flex items-center gap-1">
                            <input
                              type="number"
                              inputMode="decimal"
                              placeholder="1"
                              value={d.bastones}
                              onChange={(e) => setDraft(tarea, { bastones: e.target.value })}
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
                              value={d.cantidad}
                              onChange={(e) => setDraft(tarea, { cantidad: e.target.value })}
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
                            value={d.duracion}
                            onChange={(e) => setDraft(tarea, { duracion: e.target.value })}
                            className="w-14 border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-center focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                            style={{ minHeight: 36 }}
                          />
                          <span className="text-xs text-gray-400">min</span>
                        </div>
                        <button
                          onClick={() => toggleNotes(tarea.tarea_id)}
                          className={`ml-auto px-2 py-1 rounded text-xs transition-colors ${
                            d.notas ? "text-[#004225] bg-[#004225]/10" : "text-gray-400 hover:text-gray-600"
                          }`}
                          style={{ touchAction: "manipulation", minHeight: 36 }}
                        >
                          {d.notas ? "Notas" : "+ Nota"}
                        </button>
                      </div>

                      {notesOpen && (
                        <div className="mt-2 ml-10">
                          <textarea
                            value={d.notas}
                            onChange={(e) => setDraft(tarea, { notas: e.target.value })}
                            placeholder="Agregar nota..."
                            rows={2}
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none resize-none"
                          />
                        </div>
                      )}

                      {/* What this will consume — visible before committing to it */}
                      {previewConsumo(tarea, d.cantidad) && (
                        <p className="text-xs text-gray-500 mt-1.5 ml-10">
                          {previewConsumo(tarea, d.cantidad)}
                        </p>
                      )}

                      <div className="flex items-center gap-2 mt-2 ml-10">
                        <button
                          onClick={() => guardar(tarea)}
                          disabled={!habilitado || isSaving}
                          className="px-4 py-1.5 rounded-lg text-xs font-medium bg-[#004225] text-white hover:bg-[#00331C] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                          style={{ touchAction: "manipulation", minHeight: 36 }}
                        >
                          {isSaving ? "Guardando..." : "Guardar"}
                        </button>
                        {enEdicion && (
                          <>
                            <button
                              onClick={() => cancelarEdicion(tarea)}
                              className="px-3 py-1.5 rounded-lg text-xs font-medium text-gray-500 border border-gray-200 hover:bg-gray-50 transition-colors"
                              style={{ touchAction: "manipulation", minHeight: 36 }}
                            >
                              Cancelar
                            </button>
                            <button
                              onClick={() => guardar(tarea, false)}
                              className="ml-auto px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 transition-colors"
                              style={{ touchAction: "manipulation", minHeight: 36 }}
                            >
                              Deshacer
                            </button>
                          </>
                        )}
                        {!habilitado && !enEdicion && (
                          <span className="text-xs text-gray-400">Ingresa la cantidad</span>
                        )}
                      </div>
                    </>
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
                value={extraProductoId}
                onChange={(e) => { setExtraProductoId(e.target.value); setExtraBastones(""); }}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#004225]/30 focus:border-[#004225] outline-none"
                style={{ minHeight: 44 }}
              >
                <option value="">Seleccionar producto...</option>
                {["masa","semi","crudo","terminado"].map(nivel => {
                  const items = productosCongelados.filter(p => p.nivel === nivel);
                  if (!items.length) return null;
                  const labels: Record<string,string> = {masa:"Masas",semi:"Semi-elaborados",crudo:"Crudos",terminado:"Terminados"};
                  return (
                    <optgroup key={nivel} label={labels[nivel] || nivel}>
                      {items.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </optgroup>
                  );
                })}
              </select>
              {extraProductoId && productosCongelados.find(p => p.id === parseInt(extraProductoId))?.necesita_bastones && (
                <input
                  type="number"
                  inputMode="decimal"
                  placeholder="Bastones consumidos"
                  value={extraBastones}
                  onChange={(e) => setExtraBastones(e.target.value)}
                  className="w-full border border-blue-200 bg-blue-50/50 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-400/30 outline-none"
                  style={{ minHeight: 44 }}
                />
              )}
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
                  disabled={!extraProductoId || !extraCantidad}
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
