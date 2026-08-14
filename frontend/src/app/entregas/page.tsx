"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";

interface ClienteB2B {
  id: number;
  nombre: string;
}

interface EntregaB2B {
  id: number;
  cliente_b2b_id: number;
  fecha_entrega: string;
  estado: string;
  notas: string | null;
  created_at: string;
  lineas: { id: number; entrega_id: number; producto_id: number; cantidad: number; precio_unitario: number }[];
}

interface ProductoCatalogo {
  id: number;
  nombre: string;
  receta_id: number | null;
}

interface EntregaUnificada {
  id: number;
  tipo: "b2b" | "portal";
  cliente_nombre: string;
  fecha_entrega: string;
  estado: string;
  notas: string | null;
  total: number;
  lineas: { producto_nombre: string; cantidad: number; precio_unitario: number }[];
}


type Tab = "calendario" | "entregas" | "historial";
const TABS: { key: Tab; label: string }[] = [
  { key: "calendario", label: "Calendario" },
  { key: "entregas", label: "Entregas" },
  { key: "historial", label: "Historial" },
];

const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];
const DAY_LABELS = ["L", "M", "X", "J", "V", "S", "D"];

const ESTADOS_PEDIDO = ["pendiente", "confirmado", "en_preparacion", "listo", "entregado"];
const ESTADOS_B2B = ["pendiente", "entregado"];

function toLocalISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function EntregasPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("calendario");
  const [entregas, setEntregas] = useState<EntregaB2B[]>([]);
  const [clientes, setClientes] = useState<ClienteB2B[]>([]);
  const [productos, setProductos] = useState<ProductoCatalogo[]>([]);
  const [todasEntregas, setTodasEntregas] = useState<EntregaUnificada[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<EntregaB2B[]>("/api/entregas-b2b"),
      apiFetch<ClienteB2B[]>("/api/clientes-b2b"),
      apiFetch<ProductoCatalogo[]>("/api/catalogo"),
      apiFetch<EntregaUnificada[]>("/api/entregas-b2b/todas"),
    ])
      .then(([e, c, p, t]) => { setEntregas(e); setClientes(c); setProductos(p); setTodasEntregas(t); })
      .catch(() => toast("Error al cargar entregas", "error"))
      .finally(() => setLoading(false));
    // Historial tab still uses entregas/clientes/productos
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const switchTab = (t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", `/entregas?tab=${t}`);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tab") as Tab | null;
    if (t && TABS.some((x) => x.key === t)) setTab(t);
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Entregas
        </h1>
        <Link href="/entregas/clientes" className="text-sm text-brot hover:text-brot-dark transition-colors">
          Clientes →
        </Link>
      </div>

      <div className="flex gap-1 bg-white rounded-xl border border-cream-dark p-1 mb-6 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => switchTab(t.key)}
            className={`flex-1 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors min-h-[44px] whitespace-nowrap ${
              tab === t.key ? "bg-brot text-white" : "text-warm-gray hover:text-text hover:bg-cream/50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">Cargando...</div>
      ) : (
        <>
          {tab === "calendario" && (
            <TabCalendario entregas={todasEntregas} onReload={load} />
          )}
          {tab === "entregas" && (
            <TabEntregas entregas={todasEntregas} clientes={clientes} productos={productos} onReload={load} />
          )}
          {tab === "historial" && (
            <TabHistorial entregas={entregas} clientes={clientes} productos={productos} />
          )}
        </>
      )}
    </div>
  );
}

// ── Tab: Calendario ─────────────────────────────────────────────────────────

function TabCalendario({
  entregas,
  onReload,
}: {
  entregas: EntregaUnificada[];
  onReload: () => void;
}) {
  const { toast } = useToast();
  const now = new Date();
  const [calYear, setCalYear] = useState(now.getFullYear());
  const [calMonth, setCalMonth] = useState(now.getMonth());
  const [selectedDate, setSelectedDate] = useState(toLocalISO(now));
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const entregasByDate = useMemo(() => {
    const map = new Map<string, EntregaUnificada[]>();
    for (const e of entregas) {
      const d = e.fecha_entrega;
      if (!map.has(d)) map.set(d, []);
      map.get(d)!.push(e);
    }
    return map;
  }, [entregas]);

  const calendarWeeks = useMemo(() => {
    const first = new Date(calYear, calMonth, 1);
    let startDay = first.getDay();
    if (startDay === 0) startDay = 7;
    const start = new Date(first);
    start.setDate(start.getDate() - (startDay - 1));

    const weeks: Date[][] = [];
    const cursor = new Date(start);
    for (let w = 0; w < 6; w++) {
      const week: Date[] = [];
      for (let d = 0; d < 7; d++) {
        week.push(new Date(cursor));
        cursor.setDate(cursor.getDate() + 1);
      }
      weeks.push(week);
      if (cursor.getMonth() !== calMonth && cursor.getDate() > 7) break;
    }
    return weeks;
  }, [calYear, calMonth]);

  const prevMonth = () => {
    if (calMonth === 0) { setCalYear((y) => y - 1); setCalMonth(11); }
    else setCalMonth((m) => m - 1);
  };
  const nextMonth = () => {
    if (calMonth === 11) { setCalYear((y) => y + 1); setCalMonth(0); }
    else setCalMonth((m) => m + 1);
  };
  const goToday = () => {
    const t = new Date();
    setCalYear(t.getFullYear());
    setCalMonth(t.getMonth());
    setSelectedDate(toLocalISO(t));
  };

  const selectedEntregas = useMemo(() => {
    return (entregasByDate.get(selectedDate) ?? []).sort((a, b) => a.cliente_nombre.localeCompare(b.cliente_nombre));
  }, [entregasByDate, selectedDate]);

  const pendientes = useMemo(() => {
    return entregas
      .filter((e) => e.estado !== "entregado")
      .sort((a, b) => a.fecha_entrega.localeCompare(b.fecha_entrega));
  }, [entregas]);

  const updateEstado = async (e: EntregaUnificada, nuevoEstado: string) => {
    setSaving(true);
    try {
      const url = e.tipo === "b2b"
        ? `/api/entregas-b2b/${e.id}/estado`
        : `/api/entregas-b2b/pedido-portal/${e.id}/estado`;
      await apiFetch(url, { method: "PUT", body: JSON.stringify({ estado: nuevoEstado }) });
      toast("Estado actualizado");
      onReload();
    } catch {
      toast("Error al actualizar estado", "error");
    } finally {
      setSaving(false);
    }
  };

  const deleteEntrega = async (e: EntregaUnificada) => {
    setSaving(true);
    try {
      const url = e.tipo === "b2b"
        ? `/api/entregas-b2b/${e.id}`
        : `/api/entregas-b2b/pedido-portal/${e.id}`;
      await apiFetch(url, { method: "DELETE" });
      toast("Entrega eliminada");
      onReload();
    } catch {
      toast("Error al eliminar", "error");
    } finally {
      setSaving(false);
    }
  };

  const entregaKey = (e: EntregaUnificada) => `${e.tipo}-${e.id}`;

  const todayISO = toLocalISO(new Date());

  return (
    <div className="space-y-6">
      {/* Calendar grid */}
      <div className="bg-white rounded-xl border border-cream-dark p-4">
        <div className="flex items-center justify-between mb-4">
          <button onClick={prevMonth} className="p-2 hover:bg-cream rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center text-warm-gray">
            &lt;
          </button>
          <div className="text-center">
            <button onClick={goToday} className="font-medium text-brot hover:underline">
              {MONTH_NAMES[calMonth]} {calYear}
            </button>
          </div>
          <button onClick={nextMonth} className="p-2 hover:bg-cream rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center text-warm-gray">
            &gt;
          </button>
        </div>

        <div className="grid grid-cols-7 gap-1 mb-1">
          {DAY_LABELS.map((label) => (
            <div key={label} className="text-center text-xs font-medium text-warm-gray py-1">{label}</div>
          ))}
        </div>

        {calendarWeeks.map((week, wi) => (
          <div key={wi} className="grid grid-cols-7 gap-1">
            {week.map((day) => {
              const iso = toLocalISO(day);
              const isCurrentMonth = day.getMonth() === calMonth;
              const isToday = iso === todayISO;
              const isSelected = iso === selectedDate;
              const count = entregasByDate.get(iso)?.length ?? 0;
              const hasEntregas = count > 0;

              return (
                <button
                  key={iso}
                  onClick={() => setSelectedDate(iso)}
                  className={`
                    py-1.5 rounded-lg text-sm transition-colors min-h-[44px] flex flex-col items-center justify-center gap-0.5
                    ${isSelected
                      ? "bg-brot text-white font-semibold"
                      : isCurrentMonth
                        ? "text-text hover:bg-cream"
                        : "text-warm-gray/30"
                    }
                    ${isToday && !isSelected ? "ring-1 ring-brot/40" : ""}
                  `}
                >
                  <span>{day.getDate()}</span>
                  {hasEntregas && (
                    <span className={`text-[10px] leading-none font-medium ${isSelected ? "text-white/80" : "text-brot"}`}>
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Selected day deliveries */}
      <div>
        <h2 className="text-sm font-semibold text-brot uppercase tracking-wider mb-3">
          {formatDate(selectedDate)} — {selectedEntregas.length} entrega{selectedEntregas.length !== 1 ? "s" : ""}
        </h2>

        {selectedEntregas.length === 0 ? (
          <div className="bg-white rounded-xl border border-cream-dark p-6 text-center text-warm-gray text-sm">
            No hay entregas para este dia.
          </div>
        ) : (
          <div className="space-y-2">
            {selectedEntregas.map((e) => {
              const key = entregaKey(e);
              const expanded = expandedId === key;
              const estados = e.tipo === "portal" ? ESTADOS_PEDIDO : ESTADOS_B2B;

              return (
                <div key={key} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                  <button
                    onClick={() => setExpandedId(expanded ? null : key)}
                    className="w-full text-left px-4 py-3 hover:bg-cream/30 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-text truncate">{e.cliente_nombre}</p>
                        <p className="text-xs text-warm-gray">{e.lineas.length} producto{e.lineas.length !== 1 ? "s" : ""}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          e.estado === "entregado" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                        }`}>
                          {e.estado}
                        </span>
                        <span className="text-warm-gray text-sm">{expanded ? "−" : "+"}</span>
                      </div>
                    </div>
                  </button>

                  {expanded && (
                    <div className="border-t border-cream-dark">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-cream/30">
                            <th className="text-left px-4 py-2 font-medium text-warm-gray">Producto</th>
                            <th className="text-right px-4 py-2 font-medium text-warm-gray">Cantidad</th>
                          </tr>
                        </thead>
                        <tbody>
                          {e.lineas.map((l, idx) => (
                            <tr key={idx} className={idx < e.lineas.length - 1 ? "border-b border-cream-dark" : ""}>
                              <td className="px-4 py-2 text-text">{l.producto_nombre}</td>
                              <td className="px-4 py-2 text-right font-medium text-text tabular-nums">{l.cantidad}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>

                      <div className="px-4 py-3 border-t border-cream-dark flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <label className="text-xs text-warm-gray">Estado:</label>
                          <select
                            value={e.estado}
                            disabled={saving}
                            onChange={(ev) => updateEstado(e, ev.target.value)}
                            className="px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
                          >
                            {estados.map((s) => (
                              <option key={s} value={s}>{s}</option>
                            ))}
                          </select>
                        </div>
                        <button
                          onClick={() => deleteEntrega(e)}
                          disabled={saving}
                          className="px-3 py-1.5 text-red-600 text-xs hover:bg-red-50 rounded-lg transition-colors min-h-[36px]"
                        >
                          Eliminar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pending deliveries */}
      {pendientes.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-brot uppercase tracking-wider mb-3">
            Pendientes ({pendientes.length})
          </h2>
          <div className="space-y-2">
            {pendientes.map((e) => (
              <button
                key={entregaKey(e)}
                onClick={() => {
                  const [y, m] = e.fecha_entrega.split("-").map(Number);
                  setCalYear(y);
                  setCalMonth(m - 1);
                  setSelectedDate(e.fecha_entrega);
                }}
                className="w-full bg-white rounded-xl border border-cream-dark px-4 py-3 text-left hover:bg-cream/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-text text-sm">{e.cliente_nombre}</p>
                    <p className="text-xs text-warm-gray">{formatDate(e.fecha_entrega)} · {e.lineas.length} productos</p>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                    {e.estado}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tab: Entregas (unified list) ─────────────────────────────────────────────

interface LineaForm {
  producto_id: number | null;
  cantidad: string;
}

function TabEntregas({
  entregas,
  clientes,
  productos,
  onReload,
}: {
  entregas: EntregaUnificada[];
  clientes: ClienteB2B[];
  productos: ProductoCatalogo[];
  onReload: () => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [clienteId, setClienteId] = useState("");
  const [fecha, setFecha] = useState(() => new Date().toISOString().split("T")[0]);
  const [notas, setNotas] = useState("");
  const [lineas, setLineas] = useState<LineaForm[]>([{ producto_id: null, cantidad: "" }]);

  const addLinea = () => setLineas((prev) => [...prev, { producto_id: null, cantidad: "" }]);
  const removeLinea = (idx: number) => setLineas((prev) => prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx));
  const updateLinea = (idx: number, field: keyof LineaForm, value: string | number | null) => {
    setLineas((prev) => prev.map((l, i) => i === idx ? { ...l, [field]: value } : l));
  };
  const usedProductIds = new Set(lineas.map((l) => l.producto_id).filter(Boolean));
  const validLineas = lineas.filter((l) => l.producto_id && parseFloat(l.cantidad) > 0);

  const submitEntrega = async () => {
    if (!clienteId || !fecha || validLineas.length === 0) return;
    setSaving(true);
    try {
      await apiFetch("/api/entregas-b2b", {
        method: "POST",
        body: JSON.stringify({
          cliente_b2b_id: parseInt(clienteId),
          fecha_entrega: fecha,
          estado: "pendiente",
          notas: notas || null,
          lineas: validLineas.map((l) => ({
            producto_id: l.producto_id,
            cantidad: parseFloat(l.cantidad),
            precio_unitario: 0,
          })),
        }),
      });
      toast("Entrega creada");
      setShowForm(false);
      setClienteId("");
      setNotas("");
      setLineas([{ producto_id: null, cantidad: "" }]);
      onReload();
    } catch {
      toast("Error al crear entrega", "error");
    } finally {
      setSaving(false);
    }
  };

  const sorted = useMemo(
    () => [...entregas].sort((a, b) => b.fecha_entrega.localeCompare(a.fecha_entrega)),
    [entregas]
  );

  const entregaKey = (e: EntregaUnificada) => `${e.tipo}-${e.id}`;

  const updateEstado = async (e: EntregaUnificada, nuevoEstado: string) => {
    setSaving(true);
    try {
      const url = e.tipo === "b2b"
        ? `/api/entregas-b2b/${e.id}/estado`
        : `/api/entregas-b2b/pedido-portal/${e.id}/estado`;
      await apiFetch(url, { method: "PUT", body: JSON.stringify({ estado: nuevoEstado }) });
      toast("Estado actualizado");
      onReload();
    } catch {
      toast("Error al actualizar estado", "error");
    } finally {
      setSaving(false);
    }
  };

  const deleteEntrega = async (e: EntregaUnificada) => {
    setSaving(true);
    try {
      const url = e.tipo === "b2b"
        ? `/api/entregas-b2b/${e.id}`
        : `/api/entregas-b2b/pedido-portal/${e.id}`;
      await apiFetch(url, { method: "DELETE" });
      toast("Entrega eliminada");
      onReload();
    } catch {
      toast("Error al eliminar", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <button
        onClick={() => setShowForm((v) => !v)}
        className="w-full px-4 py-3 bg-brot text-white rounded-xl text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px]"
      >
        {showForm ? "Cancelar" : "+ Nueva Entrega"}
      </button>

      {showForm && (
        <div className="bg-white rounded-xl border border-cream-dark p-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">Cliente</label>
              <select value={clienteId} onChange={(e) => setClienteId(e.target.value)}
                className="w-full px-3 py-2.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]">
                <option value="">Seleccionar cliente...</option>
                {clientes.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">Fecha entrega</label>
              <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)}
                className="w-full px-3 py-2.5 border border-cream-dark rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-2">Productos</label>
            <div className="space-y-2">
              {lineas.map((l, idx) => (
                <div key={idx} className="flex gap-2 items-center">
                  <select value={l.producto_id ?? ""} onChange={(e) => updateLinea(idx, "producto_id", e.target.value ? parseInt(e.target.value) : null)}
                    className="flex-1 px-3 py-2.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]">
                    <option value="">Producto...</option>
                    {productos.map((p) => <option key={p.id} value={p.id} disabled={usedProductIds.has(p.id) && l.producto_id !== p.id}>{p.nombre}</option>)}
                  </select>
                  <input type="text" inputMode="decimal" placeholder="Cant." value={l.cantidad}
                    onChange={(e) => updateLinea(idx, "cantidad", e.target.value.replace(",", "."))}
                    className="w-20 px-3 py-2.5 border border-cream-dark rounded-lg text-sm text-right focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] tabular-nums" />
                  <button onClick={() => removeLinea(idx)} disabled={lineas.length <= 1}
                    className="p-2 text-warm-gray hover:text-red-500 transition-colors disabled:opacity-30 min-h-[44px] min-w-[44px] flex items-center justify-center">x</button>
                </div>
              ))}
            </div>
            <button onClick={addLinea} className="mt-2 text-sm text-brot hover:text-brot-dark transition-colors">+ Agregar producto</button>
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">Notas (opcional)</label>
            <input type="text" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Notas..."
              className="w-full px-3 py-2.5 border border-cream-dark rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]" />
          </div>
          <button onClick={submitEntrega} disabled={!clienteId || !fecha || validLineas.length === 0 || saving}
            className="w-full px-4 py-3 bg-brot text-white rounded-xl text-sm font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]">
            {saving ? "Guardando..." : "Crear Entrega"}
          </button>
        </div>
      )}

      {sorted.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay entregas.
        </div>
      ) : (
        sorted.map((e) => {
          const key = entregaKey(e);
          const expanded = expandedKey === key;
          const estados = e.tipo === "portal" ? ESTADOS_PEDIDO : ESTADOS_B2B;

          return (
            <div key={key} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              <button
                onClick={() => setExpandedKey(expanded ? null : key)}
                className="w-full text-left px-4 py-3 hover:bg-cream/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-text truncate">{e.cliente_nombre}</p>
                    <p className="text-xs text-warm-gray">{formatDate(e.fecha_entrega)} · {e.lineas.length} productos</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      e.estado === "entregado" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                    }`}>
                      {e.estado}
                    </span>
                    <span className="text-warm-gray text-sm">{expanded ? "−" : "+"}</span>
                  </div>
                </div>
              </button>

              {expanded && (
                <div className="border-t border-cream-dark">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-cream/30">
                        <th className="text-left px-4 py-2 font-medium text-warm-gray">Producto</th>
                        <th className="text-right px-4 py-2 font-medium text-warm-gray">Cantidad</th>
                      </tr>
                    </thead>
                    <tbody>
                      {e.lineas.map((l, idx) => (
                        <tr key={idx} className={idx < e.lineas.length - 1 ? "border-b border-cream-dark" : ""}>
                          <td className="px-4 py-2 text-text">{l.producto_nombre}</td>
                          <td className="px-4 py-2 text-right font-medium text-text tabular-nums">{l.cantidad}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div className="px-4 py-3 border-t border-cream-dark flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <label className="text-xs text-warm-gray">Estado:</label>
                      <select
                        value={e.estado}
                        disabled={saving}
                        onChange={(ev) => updateEstado(e, ev.target.value)}
                        className="px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
                      >
                        {estados.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                    <button
                      onClick={() => deleteEntrega(e)}
                      disabled={saving}
                      className="px-3 py-1.5 text-red-600 text-xs hover:bg-red-50 rounded-lg transition-colors min-h-[36px]"
                    >
                      Eliminar
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

// ── Tab: Historial (pivot by client) ─────────────────────────────────────────

function TabHistorial({
  entregas,
  clientes,
  productos,
}: {
  entregas: EntregaB2B[];
  clientes: ClienteB2B[];
  productos: ProductoCatalogo[];
}) {
  const prodMap = useMemo(() => new Map(productos.map((p) => [p.id, p])), [productos]);
  const clienteMap = useMemo(() => new Map(clientes.map((c) => [c.id, c.nombre])), [clientes]);

  const byClient = useMemo(() => {
    const entregadas = entregas.filter((e) => e.estado === "entregado");
    const map = new Map<number, EntregaB2B[]>();
    for (const e of entregadas) {
      if (!map.has(e.cliente_b2b_id)) map.set(e.cliente_b2b_id, []);
      map.get(e.cliente_b2b_id)!.push(e);
    }
    return Array.from(map.entries())
      .map(([clienteId, ents]) => ({
        clienteId,
        clienteNombre: clienteMap.get(clienteId) ?? `#${clienteId}`,
        entregas: ents,
      }))
      .sort((a, b) => a.clienteNombre.localeCompare(b.clienteNombre));
  }, [entregas, clienteMap]);

  const shortDate = (d: string) => {
    const dt = new Date(d + "T00:00:00");
    return dt.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
  };

  if (byClient.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
        No hay entregas completadas.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {byClient.map(({ clienteId, clienteNombre, entregas: clienteEntregas }) => {
        const dates = Array.from(new Set(clienteEntregas.map((e) => e.fecha_entrega.split("T")[0])))
          .sort((a, b) => b.localeCompare(a));

        const prodIds = new Set<number>();
        for (const e of clienteEntregas) {
          for (const l of e.lineas) prodIds.add(l.producto_id);
        }
        const clienteProducts = Array.from(prodIds)
          .map((id) => prodMap.get(id))
          .filter(Boolean) as ProductoCatalogo[];
        clienteProducts.sort((a, b) => a.nombre.localeCompare(b.nombre));

        const pivot = new Map<string, number>();
        for (const e of clienteEntregas) {
          const fecha = e.fecha_entrega.split("T")[0];
          for (const l of e.lineas) {
            const key = `${l.producto_id}:${fecha}`;
            pivot.set(key, (pivot.get(key) ?? 0) + l.cantidad);
          }
        }

        return (
          <div key={clienteId} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
            <div className="px-4 py-3 bg-cream/50 border-b border-cream-dark">
              <p className="font-medium text-brot">{clienteNombre}</p>
              <p className="text-xs text-warm-gray">{dates.length} entregas · {clienteProducts.length} productos</p>
            </div>
            <div className="overflow-x-auto">
              <table className="text-xs w-full">
                <thead>
                  <tr className="border-b border-cream-dark">
                    <th className="text-left px-3 py-2 font-medium text-warm-gray sticky left-0 bg-white z-10 whitespace-nowrap">
                      Producto
                    </th>
                    {dates.map((d) => (
                      <th key={d} className="text-center px-2 py-2 font-medium text-warm-gray whitespace-nowrap">
                        {shortDate(d)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {clienteProducts.map((prod, idx) => (
                    <tr
                      key={prod.id}
                      className={idx < clienteProducts.length - 1 ? "border-b border-cream-dark" : ""}
                    >
                      <td className="px-3 py-1.5 font-medium text-text sticky left-0 bg-white z-10 whitespace-nowrap">
                        {prod.receta_id ? (
                          <Link href={`/escandallos/${prod.receta_id}`} className="hover:text-brot hover:underline">{prod.nombre}</Link>
                        ) : prod.nombre}
                      </td>
                      {dates.map((d) => {
                        const val = pivot.get(`${prod.id}:${d}`);
                        return (
                          <td key={d} className={`text-center px-2 py-1.5 tabular-nums ${
                            val ? "text-text font-medium" : "text-cream-dark"
                          }`}>
                            {val ?? "--"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
