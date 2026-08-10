"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
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

interface Ingrediente {
  id: number;
  nombre: string;
  categoria_id: number;
  categoria_nombre: string;
  unidad_uso: string;
  activo: boolean;
}

interface RegistroStock {
  id: number;
  ingrediente_id: number;
  cantidad: number;
  unidad: string;
  fecha_registro: string;
  notas: string | null;
  ubicacion: string | null;
}

interface StockActualItem {
  ingrediente_id: number;
  nombre: string;
  categoria: string;
  cantidad: number;
  unidad: string;
  fecha_registro: string;
}

// ── Tab navigation ───────────────────────────────────────────────────────────

type Tab = "actual" | "registrar" | "historial";

const TABS: { key: Tab; label: string }[] = [
  { key: "actual", label: "Stock Actual" },
  { key: "registrar", label: "Registrar" },
  { key: "historial", label: "Historial" },
];

// ── Chart colors ─────────────────────────────────────────────────────────────

const CHART_COLORS = [
  "#004225", "#2563eb", "#dc2626", "#d97706", "#7c3aed",
  "#059669", "#db2777", "#0891b2", "#65a30d", "#ea580c",
  "#4f46e5", "#0d9488", "#b91c1c", "#ca8a04", "#9333ea",
];

// ── Main component ───────────────────────────────────────────────────────────

export default function StockPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("actual");

  const [ingredientes, setIngredientes] = useState<Ingrediente[]>([]);
  const [stockActual, setStockActual] = useState<RegistroStock[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<Ingrediente[]>("/api/ingredientes"),
      apiFetch<RegistroStock[]>("/api/inventario/actual"),
    ])
      .then(([ings, stock]) => {
        setIngredientes(ings.filter((i) => i.activo));
        setStockActual(stock);
      })
      .catch(() => toast("Error al cargar stock", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const switchTab = (t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", `/stock?tab=${t}`);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tab") as Tab | null;
    if (t && TABS.some((x) => x.key === t)) setTab(t);
  }, []);

  return (
    <div>
      <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mb-6">
        Stock Materia Prima
      </h1>

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
              ingredientes={ingredientes}
              stockActual={stockActual}
            />
          )}
          {tab === "registrar" && (
            <TabRegistrar
              ingredientes={ingredientes}
              stockActual={stockActual}
              onSaved={() => {
                load();
                switchTab("actual");
              }}
            />
          )}
          {tab === "historial" && (
            <TabHistorial ingredientes={ingredientes} />
          )}
        </>
      )}
    </div>
  );
}

// ── Tab: Stock Actual ────────────────────────────────────────────────────────

function TabStockActual({
  ingredientes,
  stockActual,
}: {
  ingredientes: Ingrediente[];
  stockActual: RegistroStock[];
}) {
  const [buscar, setBuscar] = useState("");

  const ingMap = useMemo(
    () => new Map(ingredientes.map((i) => [i.id, i])),
    [ingredientes]
  );

  const items: StockActualItem[] = useMemo(() => {
    const stockMap = new Map(stockActual.map((s) => [s.ingrediente_id, s]));
    return ingredientes.map((ing) => {
      const reg = stockMap.get(ing.id);
      return {
        ingrediente_id: ing.id,
        nombre: ing.nombre,
        categoria: ing.categoria_nombre,
        cantidad: reg?.cantidad ?? -1,
        unidad: ing.unidad_uso,
        fecha_registro: reg?.fecha_registro ?? "",
      };
    });
  }, [ingredientes, stockActual]);

  const filtered = useMemo(
    () =>
      items.filter(
        (i) =>
          buscar === "" || i.nombre.toLowerCase().includes(buscar.toLowerCase())
      ),
    [items, buscar]
  );

  const sinStock = items.filter((i) => i.cantidad === 0).length;
  const sinRegistro = items.filter((i) => i.cantidad === -1).length;
  const conStock = items.filter((i) => i.cantidad > 0).length;

  const diasDesde = (fecha: string) => {
    if (!fecha) return null;
    const d = new Date(fecha + "T00:00:00");
    const hoy = new Date();
    hoy.setHours(0, 0, 0, 0);
    return Math.floor((hoy.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  };

  return (
    <>
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <p className="text-2xl font-bold text-green-700">{conStock}</p>
          <p className="text-sm text-green-600 mt-0.5">Con stock</p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-2xl font-bold text-red-700">{sinStock}</p>
          <p className="text-sm text-red-600 mt-0.5">Sin stock</p>
        </div>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-2xl font-bold text-amber-700">{sinRegistro}</p>
          <p className="text-sm text-amber-600 mt-0.5">Sin registro</p>
        </div>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar ingrediente..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="w-full px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {/* Desktop */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-cream-dark bg-cream/50">
                <th className="text-left px-4 py-3 font-medium text-warm-gray">Ingrediente</th>
                <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad</th>
                <th className="text-left px-4 py-3 font-medium text-warm-gray">Estado</th>
                <th className="text-left px-4 py-3 font-medium text-warm-gray">Ultimo conteo</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, idx) => {
                const dias = diasDesde(item.fecha_registro);
                const stale = dias !== null && dias > 7;
                return (
                  <tr
                    key={item.ingrediente_id}
                    className={`${idx < filtered.length - 1 ? "border-b border-cream-dark" : ""} ${
                      item.cantidad === 0 ? "bg-red-50" : item.cantidad === -1 ? "bg-amber-50/50" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-text">{item.nombre}</p>
                      <p className="text-xs text-warm-gray">{item.categoria}</p>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-text">
                      {item.cantidad === -1 ? (
                        <span className="text-warm-gray">--</span>
                      ) : (
                        <>
                          {item.cantidad}{" "}
                          <span className="text-warm-gray text-xs font-normal">{item.unidad}</span>
                        </>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {item.cantidad === 0 ? (
                        <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">Sin stock</span>
                      ) : item.cantidad === -1 ? (
                        <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">Sin registro</span>
                      ) : (
                        <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">OK</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {item.fecha_registro ? (
                        <span className={stale ? "text-amber-600 font-medium" : "text-warm-gray"}>
                          {formatDate(item.fecha_registro)}
                          {stale && <span className="ml-1 text-xs">(hace {dias}d)</span>}
                        </span>
                      ) : (
                        <span className="text-warm-gray">--</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Mobile */}
        <div className="md:hidden divide-y divide-cream-dark">
          {filtered.map((item) => {
            const dias = diasDesde(item.fecha_registro);
            const stale = dias !== null && dias > 7;
            return (
              <div
                key={item.ingrediente_id}
                className={`px-4 py-3 ${
                  item.cantidad === 0 ? "bg-red-50" : item.cantidad === -1 ? "bg-amber-50/50" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-text text-sm">{item.nombre}</p>
                    <p className="text-xs text-warm-gray">{item.categoria}</p>
                    {item.fecha_registro && (
                      <p className={`text-xs mt-1 ${stale ? "text-amber-600" : "text-warm-gray"}`}>
                        {formatDate(item.fecha_registro)}
                        {stale && ` (hace ${dias}d)`}
                      </p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    {item.cantidad === -1 ? (
                      <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">Sin registro</span>
                    ) : (
                      <>
                        <p className="text-sm font-bold text-text">
                          {item.cantidad}{" "}
                          <span className="font-normal text-warm-gray text-xs">{item.unidad}</span>
                        </p>
                        {item.cantidad === 0 && (
                          <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 mt-1">Sin stock</span>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-xs text-warm-gray mt-3 text-right">
        {filtered.length} ingrediente{filtered.length !== 1 ? "s" : ""}
      </p>
    </>
  );
}

// ── Tab: Registrar ───────────────────────────────────────────────────────────

const DRAFT_KEY = "brot_stock_registro_draft";

function haceTiempo(fecha: string): string {
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

function TabRegistrar({
  ingredientes,
  stockActual,
  onSaved,
}: {
  ingredientes: Ingrediente[];
  stockActual: RegistroStock[];
  onSaved: () => void;
}) {
  const { toast } = useToast();
  const [buscar, setBuscar] = useState("");
  const [categoriaFiltro, setCategoriaFiltro] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fecha, setFecha] = useState(() => new Date().toISOString().split("T")[0]);

  const stockMap = useMemo(
    () => new Map(stockActual.map((s) => [s.ingrediente_id, s])),
    [stockActual]
  );

  const [cantidades, setCantidades] = useState<Record<number, string>>(() => {
    try {
      const saved = sessionStorage.getItem(DRAFT_KEY);
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
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(nonEmpty));
    } else {
      sessionStorage.removeItem(DRAFT_KEY);
    }
  }, [cantidades]);

  const filtered = useMemo(
    () =>
      ingredientes.filter((i) => {
        const matchBuscar = buscar === "" || i.nombre.toLowerCase().includes(buscar.toLowerCase());
        const matchCat = categoriaFiltro === null || i.categoria_nombre === categoriaFiltro;
        return matchBuscar && matchCat;
      }),
    [ingredientes, buscar, categoriaFiltro]
  );

  // Group filtered ingredients by category
  const grouped = useMemo(() => {
    const map = new Map<string, Ingrediente[]>();
    for (const ing of filtered) {
      const cat = ing.categoria_nombre;
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(ing);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const categories = useMemo(() => {
    const cats = new Set(ingredientes.map((i) => i.categoria_nombre));
    return Array.from(cats).sort();
  }, [ingredientes]);

  const filledCount = Object.values(cantidades).filter((v) => v !== "").length;

  const handleSubmit = async () => {
    const entries = Object.entries(cantidades)
      .filter(([, v]) => v !== "")
      .map(([id, v]) => {
        const ing = ingredientes.find((i) => i.id === Number(id));
        return {
          ingrediente_id: Number(id),
          cantidad: parseFloat(v),
          unidad: ing?.unidad_uso ?? "kg",
          fecha_registro: fecha,
        };
      });

    if (entries.length === 0) {
      toast("Ingresa al menos un ingrediente con cantidad", "error");
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch("/api/inventario", {
        method: "POST",
        body: JSON.stringify(entries),
      });
      toast(`${entries.length} registros guardados`);
      sessionStorage.removeItem(DRAFT_KEY);
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
      module="inventario"
      action="write"
      fallback={
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No tenes permisos para registrar stock.
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
          placeholder="Buscar ingrediente..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="flex-1 px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
        <span className="text-sm text-warm-gray whitespace-nowrap">
          {filledCount} / {ingredientes.length}
        </span>
      </div>

      {/* Grouped ingredient cards */}
      <div className="space-y-6 mb-4">
        {grouped.map(([cat, ings]) => (
          <div key={cat}>
            <h3 className="text-sm font-bold text-brot uppercase tracking-wide mb-2">
              {cat}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {ings.map((ing) => {
                const prev = stockMap.get(ing.id);
                const val = cantidades[ing.id] ?? "";
                const hasCantidad = val !== "";
                return (
                  <div
                    key={ing.id}
                    className={`bg-white rounded-xl border px-4 py-3 transition-colors ${
                      hasCantidad ? "border-brot/40 bg-brot/5" : "border-cream-dark"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium text-brot text-sm truncate">{ing.nombre}</p>
                        <p className="text-xs text-warm-gray">
                          {prev ? haceTiempo(prev.fecha_registro) : "--"}
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
                            setCantidades((p) => ({ ...p, [ing.id]: e.target.value }))
                          }
                          className="w-20 px-2 py-1.5 rounded-lg border border-cream-dark text-sm text-right focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[36px]"
                        />
                        <span className="text-xs text-warm-gray">{ing.unidad_uso}</span>
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
                ? `${filledCount} ingrediente${filledCount !== 1 ? "s" : ""} para guardar`
                : "Ninguno ingresado"}
            </p>
            <p className="text-xs text-warm-gray">Fecha: {formatDate(fecha)}</p>
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

function TabHistorial({ ingredientes }: { ingredientes: Ingrediente[] }) {
  const { toast } = useToast();
  const [registros, setRegistros] = useState<RegistroStock[]>([]);
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

  const ingMap = useMemo(
    () => new Map(ingredientes.map((i) => [i.id, i])),
    [ingredientes]
  );

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (fechaDesde) params.set("fecha_desde", fechaDesde);
    if (fechaHasta) params.set("fecha_hasta", fechaHasta);
    apiFetch<RegistroStock[]>(`/api/inventario?${params}`)
      .then(setRegistros)
      .catch(() => toast("Error al cargar historial", "error"))
      .finally(() => setLoading(false));
  }, [fechaDesde, fechaHasta, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const idsWithData = useMemo(
    () => new Set(registros.map((r) => r.ingrediente_id)),
    [registros]
  );

  // Categories that have data, with their ingredients
  const categoryMap = useMemo(() => {
    const map = new Map<string, Ingrediente[]>();
    for (const ing of ingredientes) {
      if (!idsWithData.has(ing.id)) continue;
      const cat = ing.categoria_nombre;
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(ing);
    }
    return map;
  }, [ingredientes, idsWithData]);

  const categories = useMemo(
    () => Array.from(categoryMap.keys()).sort(),
    [categoryMap]
  );

  // Auto-select first category's ingredients on first load
  useEffect(() => {
    if (categories.length > 0 && selectedIds.size === 0) {
      const firstCat = categories[0];
      const ings = categoryMap.get(firstCat) ?? [];
      setSelectedIds(new Set(ings.map((i) => i.id)));
      setExpandedCategory(firstCat);
    }
  }, [categories]);

  const toggleCategory = (cat: string) => {
    if (expandedCategory === cat) {
      setExpandedCategory(null);
      return;
    }
    setExpandedCategory(cat);
    const ings = categoryMap.get(cat) ?? [];
    setSelectedIds(new Set(ings.map((i) => i.id)));
  };

  const toggleIngredient = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    const all = new Set<number>();
    for (const ing of ingredientes) {
      if (idsWithData.has(ing.id)) all.add(ing.id);
    }
    setSelectedIds(all);
    setExpandedCategory(null);
  };

  // Chart data from selected individual ingredients
  const chartData = useMemo(() => {
    if (selectedIds.size === 0) return [];

    const byDate = new Map<string, Record<string, number>>();
    for (const r of registros) {
      if (!selectedIds.has(r.ingrediente_id)) continue;
      const name = ingMap.get(r.ingrediente_id)?.nombre ?? `#${r.ingrediente_id}`;
      if (!byDate.has(r.fecha_registro)) byDate.set(r.fecha_registro, {});
      byDate.get(r.fecha_registro)![name] = r.cantidad;
    }

    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fecha, values]) => ({ fecha, ...values }));
  }, [registros, selectedIds, ingMap]);

  const chartNames = useMemo(
    () =>
      Array.from(selectedIds)
        .map((id) => ingMap.get(id)?.nombre ?? `#${id}`)
        .sort(),
    [selectedIds, ingMap]
  );

  // Pivot table: all ingredients (rows) x dates (columns, most recent first)
  const allDates = useMemo(() => {
    const dates = new Set(registros.map((r) => r.fecha_registro));
    return Array.from(dates).sort((a, b) => b.localeCompare(a));
  }, [registros]);

  const allIngsWithData = useMemo(() => {
    const ids = new Set(registros.map((r) => r.ingrediente_id));
    return ingredientes.filter((i) => ids.has(i.id));
  }, [registros, ingredientes]);

  const pivotData = useMemo(() => {
    const map = new Map<string, Map<number, number>>();
    for (const r of registros) {
      if (!map.has(r.fecha_registro)) map.set(r.fecha_registro, new Map());
      map.get(r.fecha_registro)!.set(r.ingrediente_id, r.cantidad);
    }
    return map;
  }, [registros]);

  const shortDate = (d: string) => {
    const dt = new Date(d + "T00:00:00");
    return dt.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
  };

  return (
    <>
      {/* Date filters */}
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
      ) : registros.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay registros en este periodo.
        </div>
      ) : (
        <>
          {/* Category + ingredient selector */}
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
                const catIngs = categoryMap.get(cat) ?? [];
                const selectedInCat = catIngs.filter((i) => selectedIds.has(i.id)).length;
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

            {/* Expanded ingredient list */}
            {expandedCategory && (
              <div className="mt-3 pt-3 border-t border-cream-dark">
                <div className="flex gap-2 flex-wrap">
                  {(categoryMap.get(expandedCategory) ?? []).map((ing) => {
                    const active = selectedIds.has(ing.id);
                    return (
                      <button
                        key={ing.id}
                        onClick={() => toggleIngredient(ing.id)}
                        className={`px-2.5 py-1 rounded-lg text-xs whitespace-nowrap min-h-[32px] transition-colors border ${
                          active
                            ? "bg-brot text-white border-transparent"
                            : "bg-white border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
                        }`}
                      >
                        {ing.nombre}
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
                Evolucion de stock
                <span className="text-warm-gray font-normal ml-2 text-xs">
                  {selectedIds.size} ingrediente{selectedIds.size !== 1 ? "s" : ""}
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

          {/* Pivot table: ingredients (rows) x dates (columns) */}
          <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
            <div className="overflow-x-auto">
              <table className="text-xs w-full">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-3 py-2 font-medium text-warm-gray sticky left-0 bg-cream/50 z-10 whitespace-nowrap">
                      Ingrediente
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
                  {allIngsWithData.map((ing, idx) => (
                    <tr
                      key={ing.id}
                      className={`${idx < allIngsWithData.length - 1 ? "border-b border-cream-dark" : ""} ${idx % 2 === 0 ? "" : "bg-cream/30"}`}
                    >
                      <td className="px-3 py-1.5 font-medium text-text sticky left-0 bg-white z-10 whitespace-nowrap" style={idx % 2 !== 0 ? { backgroundColor: "rgb(245 240 232 / 0.3)" } : undefined}>
                        {ing.nombre}
                      </td>
                      <td className="px-2 py-1.5 text-warm-gray sticky z-10" style={idx % 2 !== 0 ? { backgroundColor: "rgb(245 240 232 / 0.3)" } : { backgroundColor: "white" }}>
                        {ing.unidad_uso}
                      </td>
                      {allDates.map((d) => {
                        const val = pivotData.get(d)?.get(ing.id);
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
            {allIngsWithData.length} ingrediente{allIngsWithData.length !== 1 ? "s" : ""} · {allDates.length} fecha{allDates.length !== 1 ? "s" : ""}
          </p>
        </>
      )}
    </>
  );
}
