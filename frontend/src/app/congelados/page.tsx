"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";
import { formatDate } from "@/lib/format";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

// ── Types ────────────────────────────────────────────────────────────────────

interface ProductoCongelado {
  id: number;
  nombre: string;
  categoria: string;
  unidad: string;
  is_active: boolean;
  position: number;
}

interface StockCongelado {
  id: number;
  producto_congelado_id: number;
  producto_nombre: string;
  cantidad: number;
  fecha_entrada: string;
  fecha_vencimiento: string | null;
  lote: string | null;
  ubicacion: string | null;
  notas: string | null;
  is_active: boolean;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function diasHastaVencimiento(fecha: string | null): number | null {
  if (!fecha) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exp = new Date(fecha + "T00:00:00");
  return Math.ceil((exp.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function expiryBadge(dias: number | null): { text: string; cls: string } | null {
  if (dias === null) return null;
  if (dias < 0) return { text: "Vencido", cls: "bg-red-100 text-red-700" };
  if (dias === 0) return { text: "Vence hoy", cls: "bg-red-100 text-red-700" };
  if (dias <= 7) return { text: `${dias}d`, cls: "bg-amber-100 text-amber-700" };
  return null;
}

// ── Tab navigation ───────────────────────────────────────────────────────────

type Tab = "actual" | "nueva" | "historial";

const TABS: { key: Tab; label: string }[] = [
  { key: "actual", label: "Stock Actual" },
  { key: "nueva", label: "Nueva Entrada" },
  { key: "historial", label: "Historial" },
];

const CHART_COLORS = [
  "#004225", "#2563eb", "#dc2626", "#d97706", "#7c3aed",
  "#059669", "#db2777", "#0891b2", "#65a30d", "#ea580c",
];

// ── Main component ───────────────────────────────────────────────────────────

export default function CongeladosPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("actual");

  const [stock, setStock] = useState<StockCongelado[]>([]);
  const [productos, setProductos] = useState<ProductoCongelado[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<StockCongelado[]>("/api/congelados"),
      apiFetch<ProductoCongelado[]>("/api/congelados/productos"),
    ])
      .then(([s, p]) => {
        setStock(s);
        setProductos(p);
      })
      .catch(() => toast("Error al cargar stock congelado", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const switchTab = (t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", `/congelados?tab=${t}`);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tab") as Tab | null;
    if (t && TABS.some((x) => x.key === t)) setTab(t);
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Stock Congelado
        </h1>
        <Link
          href="/congelados/productos"
          className="text-sm text-brot hover:text-brot-dark transition-colors"
        >
          Gestionar productos →
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-white rounded-xl border border-cream-dark p-1 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => switchTab(t.key)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${
              tab === t.key
                ? "bg-brot text-white"
                : "text-warm-gray hover:text-text hover:bg-cream/50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : (
        <>
          {tab === "actual" && (
            <TabStockActual
              stock={stock}
              productos={productos}
              onReload={load}
            />
          )}
          {tab === "nueva" && (
            <TabNuevaEntrada
              productos={productos}
              stock={stock}
              onSaved={() => {
                load();
                switchTab("actual");
              }}
            />
          )}
          {tab === "historial" && (
            <TabHistorial productos={productos} />
          )}
        </>
      )}
    </div>
  );
}

// ── Tab: Stock Actual ────────────────────────────────────────────────────────

function TabStockActual({
  stock,
  productos,
  onReload,
}: {
  stock: StockCongelado[];
  productos: ProductoCongelado[];
  onReload: () => void;
}) {
  const { toast } = useToast();
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  // Aggregate totals per product
  const totales = useMemo(() => {
    const map = new Map<number, { nombre: string; total: number; entries: number }>();
    for (const e of stock) {
      const existing = map.get(e.producto_congelado_id);
      if (existing) {
        existing.total += e.cantidad;
        existing.entries += 1;
      } else {
        map.set(e.producto_congelado_id, {
          nombre: e.producto_nombre,
          total: e.cantidad,
          entries: 1,
        });
      }
    }
    return map;
  }, [stock]);

  // Expiry alerts
  const alertas = useMemo(() => {
    return stock
      .filter((e) => {
        const dias = diasHastaVencimiento(e.fecha_vencimiento);
        return dias !== null && dias <= 7;
      })
      .sort((a, b) => {
        const da = diasHastaVencimiento(a.fecha_vencimiento) ?? 999;
        const db = diasHastaVencimiento(b.fecha_vencimiento) ?? 999;
        return da - db;
      });
  }, [stock]);

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/congelados/${id}`, { method: "DELETE" });
      toast("Entrada eliminada");
      setDeleteConfirm(null);
      onReload();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al eliminar", "error");
      setDeleteConfirm(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <p className="text-2xl font-bold text-green-700">{stock.length}</p>
          <p className="text-sm text-green-600 mt-0.5">Entradas activas</p>
        </div>
        <div className="bg-cream border border-cream-dark rounded-xl p-4">
          <p className="text-2xl font-bold text-text">{totales.size}</p>
          <p className="text-sm text-warm-gray mt-0.5">Productos distintos</p>
        </div>
        {alertas.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-2xl font-bold text-amber-700">{alertas.length}</p>
            <p className="text-sm text-amber-600 mt-0.5">Por vencer / vencidos</p>
          </div>
        )}
      </div>

      {/* Expiry alerts */}
      {alertas.length > 0 && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-sm font-medium text-amber-800 mb-2">
            Alertas de vencimiento
          </p>
          <div className="space-y-1">
            {alertas.map((a) => {
              const dias = diasHastaVencimiento(a.fecha_vencimiento);
              const badge = expiryBadge(dias);
              return (
                <div key={a.id} className="flex items-center gap-2 text-xs text-amber-700">
                  <span className="font-medium">{a.producto_nombre}</span>
                  <span className="text-warm-gray">x{a.cantidad}</span>
                  {badge && (
                    <span className={`px-1.5 py-0.5 rounded-full text-xs font-medium ${badge.cls}`}>
                      {badge.text}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Stock list */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {stock.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No hay entradas de stock congelado.
          </div>
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Producto</th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Entrada</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Vencimiento</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Notas</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {stock.map((entry, idx) => {
                    const dias = diasHastaVencimiento(entry.fecha_vencimiento);
                    const badge = expiryBadge(dias);
                    if (deleteConfirm === entry.id) {
                      return (
                        <tr key={entry.id} className="border-b border-cream-dark bg-red-50">
                          <td colSpan={5} className="px-4 py-3 text-sm">
                            ¿Eliminar entrada de <strong>{entry.producto_nombre}</strong>?
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={() => handleDelete(entry.id)}
                                disabled={saving}
                                className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 transition-colors disabled:opacity-50"
                              >
                                {saving ? "..." : "Eliminar"}
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="px-3 py-1.5 border border-cream-dark rounded-lg text-xs hover:bg-cream-dark transition-colors"
                              >
                                Cancelar
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    }
                    return (
                      <tr
                        key={entry.id}
                        className={`${idx < stock.length - 1 ? "border-b border-cream-dark" : ""} ${
                          dias !== null && dias < 0 ? "bg-red-50/50" : dias !== null && dias <= 7 ? "bg-amber-50/30" : ""
                        }`}
                      >
                        <td className="px-4 py-3 font-medium text-text">{entry.producto_nombre}</td>
                        <td className="px-4 py-3 text-right text-text">{entry.cantidad}</td>
                        <td className="px-4 py-3 text-warm-gray">{formatDate(entry.fecha_entrada)}</td>
                        <td className="px-4 py-3">
                          {entry.fecha_vencimiento ? (
                            <span className="flex items-center gap-2">
                              <span className={dias !== null && dias <= 7 ? "font-medium" : "text-warm-gray"}>
                                {formatDate(entry.fecha_vencimiento)}
                              </span>
                              {badge && (
                                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${badge.cls}`}>
                                  {badge.text}
                                </span>
                              )}
                            </span>
                          ) : (
                            <span className="text-warm-gray">--</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-warm-gray">{entry.notas ?? "--"}</td>
                        <td className="px-4 py-3">
                          <PermissionGate module="congelados" action="delete">
                            <button
                              onClick={() => setDeleteConfirm(entry.id)}
                              className="px-3 py-1.5 text-xs text-red-600 hover:text-red-700 transition-colors min-h-[36px]"
                            >
                              Eliminar
                            </button>
                          </PermissionGate>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile */}
            <div className="md:hidden divide-y divide-cream-dark">
              {stock.map((entry) => {
                const dias = diasHastaVencimiento(entry.fecha_vencimiento);
                const badge = expiryBadge(dias);
                if (deleteConfirm === entry.id) {
                  return (
                    <div key={entry.id} className="px-4 py-3 bg-red-50 flex items-center gap-3 flex-wrap">
                      <span className="text-sm flex-1">
                        ¿Eliminar <strong>{entry.producto_nombre}</strong>?
                      </span>
                      <button
                        onClick={() => handleDelete(entry.id)}
                        disabled={saving}
                        className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm min-h-[44px] disabled:opacity-50"
                      >
                        {saving ? "..." : "Eliminar"}
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-3 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px]"
                      >
                        Cancelar
                      </button>
                    </div>
                  );
                }
                return (
                  <div
                    key={entry.id}
                    className={`px-4 py-3 ${
                      dias !== null && dias < 0 ? "bg-red-50/50" : dias !== null && dias <= 7 ? "bg-amber-50/30" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-text text-sm">{entry.producto_nombre}</p>
                        <p className="text-xs text-warm-gray mt-0.5">
                          Entrada: {formatDate(entry.fecha_entrada)}
                        </p>
                        {entry.fecha_vencimiento && (
                          <div className="flex items-center gap-1 mt-1">
                            <span className="text-xs text-warm-gray">
                              Vence: {formatDate(entry.fecha_vencimiento)}
                            </span>
                            {badge && (
                              <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${badge.cls}`}>
                                {badge.text}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p className="font-bold text-text">{entry.cantidad}</p>
                        <PermissionGate module="congelados" action="delete">
                          <button
                            onClick={() => setDeleteConfirm(entry.id)}
                            className="text-xs text-red-600 mt-1 min-h-[36px]"
                          >
                            Eliminar
                          </button>
                        </PermissionGate>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      <p className="text-xs text-warm-gray mt-3 text-right">
        {stock.length} entrada{stock.length !== 1 ? "s" : ""}
      </p>
    </>
  );
}

// ── Tab: Nueva Entrada ───────────────────────────────────────────────────────

const DRAFT_KEY_CONG = "brot_congelados_registro_draft";

function haceTiempoCong(fecha: string): string {
  const d = new Date(fecha + "T00:00:00");
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const dias = Math.floor((hoy.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (dias === 0) return "hoy";
  if (dias === 1) return "hace 1d";
  if (dias < 7) return `hace ${dias}d`;
  const sem = Math.floor(dias / 7);
  return `hace ${sem} sem`;
}

function TabNuevaEntrada({
  productos,
  stock,
  onSaved,
}: {
  productos: ProductoCongelado[];
  stock: StockCongelado[];
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [buscar, setBuscar] = useState("");
  const [categoriaFiltro, setCategoriaFiltro] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fechaEntrada, setFechaEntrada] = useState(() => new Date().toISOString().split("T")[0]);

  const activeProductos = useMemo(
    () => productos.filter((p) => p.is_active),
    [productos]
  );

  // Last entry per product for "hace Xd"
  const lastEntryMap = useMemo(() => {
    const map = new Map<number, string>();
    for (const e of stock) {
      const existing = map.get(e.producto_congelado_id);
      if (!existing || e.fecha_entrada > existing) {
        map.set(e.producto_congelado_id, e.fecha_entrada);
      }
    }
    return map;
  }, [stock]);

  const [cantidades, setCantidades] = useState<Record<number, string>>(() => {
    try {
      const saved = sessionStorage.getItem(DRAFT_KEY_CONG);
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    const nonEmpty = Object.fromEntries(
      Object.entries(cantidades).filter(([, v]) => v !== "")
    );
    if (Object.keys(nonEmpty).length > 0) {
      sessionStorage.setItem(DRAFT_KEY_CONG, JSON.stringify(nonEmpty));
    } else {
      sessionStorage.removeItem(DRAFT_KEY_CONG);
    }
  }, [cantidades]);

  const filtered = useMemo(
    () =>
      activeProductos.filter((p) => {
        const matchBuscar = buscar === "" || p.nombre.toLowerCase().includes(buscar.toLowerCase());
        const matchCat = categoriaFiltro === null || (p.categoria || "Sin categoria") === categoriaFiltro;
        return matchBuscar && matchCat;
      }),
    [activeProductos, buscar, categoriaFiltro]
  );

  const grouped = useMemo(() => {
    const map = new Map<string, ProductoCongelado[]>();
    for (const p of filtered) {
      const cat = p.categoria || "Sin categoria";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(p);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const categories = useMemo(() => {
    const cats = new Set(activeProductos.map((p) => p.categoria || "Sin categoria"));
    return Array.from(cats).sort();
  }, [activeProductos]);

  const filledCount = Object.values(cantidades).filter((v) => v !== "").length;

  const handleSubmit = async () => {
    const entries = Object.entries(cantidades)
      .filter(([, v]) => v !== "")
      .map(([id, v]) => ({
        producto_congelado_id: Number(id),
        cantidad: Number(v),
        fecha_entrada: fechaEntrada,
        fecha_vencimiento: null as string | null,
      }));

    if (entries.length === 0) {
      toast("Ingresa al menos un producto con cantidad", "error");
      return;
    }

    setSubmitting(true);
    try {
      for (const entry of entries) {
        await apiFetch("/api/congelados", {
          method: "POST",
          body: JSON.stringify(entry),
        });
      }
      toast(`${entries.length} registros guardados`);
      sessionStorage.removeItem(DRAFT_KEY_CONG);
      setCantidades({});
      onSaved();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Error al guardar", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PermissionGate
      module="congelados"
      action="create"
      fallback={
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No tenes permisos para agregar entradas.
        </div>
      }
    >
      {/* Category filter chips */}
      <div className="flex gap-2 flex-wrap mb-4">
        <button
          onClick={() => setCategoriaFiltro(null)}
          className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors border ${
            categoriaFiltro === null
              ? "bg-brot text-white border-transparent"
              : "bg-white border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
          }`}
        >
          Todas las categorias
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoriaFiltro(categoriaFiltro === cat ? null : cat)}
            className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors border ${
              categoriaFiltro === cat
                ? "bg-brot text-white border-transparent"
                : "bg-white border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Search + counter */}
      <div className="flex gap-3 items-center mb-4">
        <input
          type="search"
          placeholder="Buscar producto..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="flex-1 px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
        <span className="text-sm text-warm-gray whitespace-nowrap">
          {filledCount} / {activeProductos.length}
        </span>
      </div>

      {/* Grouped product cards */}
      <div className="space-y-6 mb-4">
        {grouped.map(([cat, prods]) => (
          <div key={cat}>
            <h3 className="text-sm font-bold text-brot uppercase tracking-wide mb-2">
              {cat}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {prods.map((p) => {
                const val = cantidades[p.id] ?? "";
                const hasCantidad = val !== "";
                const lastDate = lastEntryMap.get(p.id);
                return (
                  <div
                    key={p.id}
                    className={`bg-white rounded-xl border px-4 py-3 transition-colors ${
                      hasCantidad ? "border-brot/40 bg-brot/5" : "border-cream-dark"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium text-brot text-sm truncate">{p.nombre}</p>
                        <p className="text-xs text-warm-gray">
                          {lastDate ? haceTiempoCong(lastDate) : "--"}
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <input
                          type="number"
                          inputMode="decimal"
                          min="0"
                          step="any"
                          placeholder="0"
                          value={val}
                          onChange={(e) =>
                            setCantidades((prev) => ({ ...prev, [p.id]: e.target.value }))
                          }
                          className="w-20 px-2 py-1.5 rounded-lg border border-cream-dark text-sm text-right focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
                        />
                        <span className="text-xs text-warm-gray">{p.unidad}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Submit bar */}
      <div className="sticky bottom-20 md:bottom-4 z-20">
        <div className="flex items-center justify-between gap-4 bg-white rounded-xl border border-cream-dark p-4 shadow-lg">
          <div>
            <p className="text-sm font-medium text-text">
              {filledCount > 0
                ? `${filledCount} producto${filledCount !== 1 ? "s" : ""} para guardar`
                : "Ninguno ingresado"}
            </p>
            <p className="text-xs text-warm-gray">Fecha: {formatDate(fechaEntrada)}</p>
          </div>
          <button
            onClick={handleSubmit}
            disabled={submitting || filledCount === 0}
            className="bg-brot text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? "Guardando..." : "Registrar Stock"}
          </button>
        </div>
      </div>
    </PermissionGate>
  );
}

// ── Tab: Historial ───────────────────────────────────────────────────────────

function TabHistorial({ productos }: { productos: ProductoCongelado[] }) {
  const { toast } = useToast();
  const [entries, setEntries] = useState<StockCongelado[]>([]);
  const [loading, setLoading] = useState(true);

  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 90);
    return d.toISOString().split("T")[0];
  });
  const [fechaHasta, setFechaHasta] = useState(
    () => new Date().toISOString().split("T")[0]
  );
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (fechaDesde) params.set("fecha_desde", fechaDesde);
    if (fechaHasta) params.set("fecha_hasta", fechaHasta);
    apiFetch<StockCongelado[]>(`/api/congelados?${params}`)
      .then(setEntries)
      .catch(() => toast("Error al cargar historial", "error"))
      .finally(() => setLoading(false));
  }, [fechaDesde, fechaHasta, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const idsWithData = useMemo(
    () => new Set(entries.map((e) => e.producto_congelado_id)),
    [entries]
  );

  const categoryMap = useMemo(() => {
    const map = new Map<string, ProductoCongelado[]>();
    for (const p of productos) {
      if (!idsWithData.has(p.id)) continue;
      const cat = p.categoria || "Sin categoria";
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(p);
    }
    return map;
  }, [productos, idsWithData]);

  const categories = useMemo(
    () => Array.from(categoryMap.keys()).sort(),
    [categoryMap]
  );

  useEffect(() => {
    if (categories.length > 0 && selectedIds.size === 0) {
      const firstCat = categories[0];
      const prods = categoryMap.get(firstCat) ?? [];
      setSelectedIds(new Set(prods.map((p) => p.id)));
      setExpandedCategory(firstCat);
    }
  }, [categories]);

  const toggleCategory = (cat: string) => {
    if (expandedCategory === cat) {
      setExpandedCategory(null);
      return;
    }
    setExpandedCategory(cat);
    const prods = categoryMap.get(cat) ?? [];
    setSelectedIds(new Set(prods.map((p) => p.id)));
  };

  const toggleProduct = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const all = new Set<number>();
    for (const p of productos) {
      if (idsWithData.has(p.id)) all.add(p.id);
    }
    setSelectedIds(all);
    setExpandedCategory(null);
  };

  const chartData = useMemo(() => {
    if (selectedIds.size === 0) return [];
    const byDate = new Map<string, Record<string, number>>();
    for (const e of entries) {
      if (!selectedIds.has(e.producto_congelado_id)) continue;
      if (!byDate.has(e.fecha_entrada)) byDate.set(e.fecha_entrada, {});
      const row = byDate.get(e.fecha_entrada)!;
      const name = e.producto_nombre;
      row[name] = (row[name] ?? 0) + e.cantidad;
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fecha, values]) => ({ fecha, ...values }));
  }, [entries, selectedIds]);

  const chartNames = useMemo(
    () =>
      Array.from(selectedIds)
        .map((id) => productos.find((p) => p.id === id)?.nombre ?? `#${id}`)
        .sort(),
    [selectedIds, productos]
  );

  // Pivot table data
  const allDates = useMemo(() => {
    const dates = new Set(entries.map((e) => e.fecha_entrada));
    return Array.from(dates).sort((a, b) => b.localeCompare(a));
  }, [entries]);

  const allProductsWithData = useMemo(() => {
    const ids = new Set(entries.map((e) => e.producto_congelado_id));
    return productos.filter((p) => ids.has(p.id));
  }, [entries, productos]);

  // For congelados, aggregate quantities per (date, product) since there can be multiple entries
  const pivotData = useMemo(() => {
    const map = new Map<string, Map<number, number>>();
    for (const e of entries) {
      if (!map.has(e.fecha_entrada)) map.set(e.fecha_entrada, new Map());
      const dateMap = map.get(e.fecha_entrada)!;
      dateMap.set(e.producto_congelado_id, (dateMap.get(e.producto_congelado_id) ?? 0) + e.cantidad);
    }
    return map;
  }, [entries]);

  const shortDate = (d: string) => {
    const dt = new Date(d + "T00:00:00");
    return dt.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
  };

  return (
    <>
      {/* Filters */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">Desde</label>
            <input
              type="date"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">Hasta</label>
            <input
              type="date"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            />
          </div>
        </div>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : entries.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay registros en este periodo.
        </div>
      ) : (
        <>
          {/* Category + product selector */}
          <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-warm-gray">Grafica</p>
              <button
                onClick={selectAll}
                className="text-xs text-brot hover:text-brot-dark transition-colors min-h-[32px] px-2"
              >
                Todos
              </button>
            </div>
            <div className="flex gap-2 flex-wrap">
              {categories.map((cat) => {
                const expanded = expandedCategory === cat;
                const catProds = categoryMap.get(cat) ?? [];
                const selectedInCat = catProds.filter((p) => selectedIds.has(p.id)).length;
                return (
                  <button
                    key={cat}
                    onClick={() => toggleCategory(cat)}
                    className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors border ${
                      expanded
                        ? "bg-brot text-white border-transparent"
                        : selectedInCat > 0
                        ? "bg-brot/10 border-brot/30 text-brot"
                        : "bg-white border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
                    }`}
                  >
                    {cat}
                    {selectedInCat > 0 && !expanded && (
                      <span className="ml-1 text-xs opacity-70">({selectedInCat})</span>
                    )}
                  </button>
                );
              })}
            </div>

            {expandedCategory && (
              <div className="mt-3 pt-3 border-t border-cream-dark">
                <div className="flex gap-2 flex-wrap">
                  {(categoryMap.get(expandedCategory) ?? []).map((p) => {
                    const active = selectedIds.has(p.id);
                    return (
                      <button
                        key={p.id}
                        onClick={() => toggleProduct(p.id)}
                        className={`px-2.5 py-1 rounded-lg text-xs whitespace-nowrap min-h-[32px] transition-colors border ${
                          active
                            ? "bg-brot text-white border-transparent"
                            : "bg-white border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
                        }`}
                      >
                        {p.nombre}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Chart */}
          {selectedIds.size > 0 && chartData.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
              <p className="text-sm font-medium text-text mb-3">
                Evolucion de stock congelado
                <span className="text-warm-gray font-normal ml-2 text-xs">
                  {selectedIds.size} producto{selectedIds.size !== 1 ? "s" : ""}
                </span>
              </p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E8DFD3" />
                  <XAxis
                    dataKey="fecha"
                    tick={{ fontSize: 11, fill: "#6B5E52" }}
                    tickFormatter={(v: string) => {
                      const d = new Date(v + "T00:00:00");
                      return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
                    }}
                  />
                  <YAxis tick={{ fontSize: 11, fill: "#6B5E52" }} />
                  <Tooltip
                    labelFormatter={(v) => formatDate(String(v))}
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid #E8DFD3",
                      fontSize: "13px",
                    }}
                  />
                  {chartNames.map((name, idx) => (
                    <Line
                      key={name}
                      type="monotone"
                      dataKey={name}
                      stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Pivot table: products (rows) x dates (columns, most recent first) */}
          <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
            <div className="overflow-x-auto">
              <table className="text-xs w-full">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-3 py-2 font-medium text-warm-gray sticky left-0 bg-cream/50 z-10 whitespace-nowrap">
                      Producto
                    </th>
                    <th className="text-left px-2 py-2 font-medium text-warm-gray bg-cream/50">
                      Ud.
                    </th>
                    {allDates.map((d) => (
                      <th
                        key={d}
                        className="text-center px-2 py-2 font-medium text-warm-gray whitespace-nowrap"
                      >
                        {shortDate(d)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allProductsWithData.map((prod, idx) => (
                    <tr
                      key={prod.id}
                      className={`${idx < allProductsWithData.length - 1 ? "border-b border-cream-dark" : ""} ${idx % 2 === 0 ? "" : "bg-cream/30"}`}
                    >
                      <td className="px-3 py-1.5 font-medium text-text sticky left-0 bg-white z-10 whitespace-nowrap" style={idx % 2 !== 0 ? { backgroundColor: "rgb(245 240 232 / 0.3)" } : undefined}>
                        {prod.nombre}
                      </td>
                      <td className="px-2 py-1.5 text-warm-gray sticky z-10" style={idx % 2 !== 0 ? { backgroundColor: "rgb(245 240 232 / 0.3)" } : { backgroundColor: "white" }}>
                        {prod.unidad}
                      </td>
                      {allDates.map((d) => {
                        const val = pivotData.get(d)?.get(prod.id);
                        return (
                          <td
                            key={d}
                            className={`text-center px-2 py-1.5 tabular-nums ${
                              val === undefined
                                ? "text-cream-dark"
                                : val === 0
                                ? "text-red-600 font-medium"
                                : "text-text"
                            }`}
                          >
                            {val !== undefined ? val : "--"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className="text-xs text-warm-gray mt-3 text-right">
            {allProductsWithData.length} producto{allProductsWithData.length !== 1 ? "s" : ""} · {allDates.length} fecha{allDates.length !== 1 ? "s" : ""}
          </p>
        </>
      )}
    </>
  );
}
