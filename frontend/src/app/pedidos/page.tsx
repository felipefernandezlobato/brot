"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatARS, formatDate } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

// ── Types ────────────────────────────────────────────────────────────────────

type EstadoPedido = "borrador" | "enviado" | "recibido";

interface PedidoListItem {
  id: number;
  proveedor_id: number;
  proveedor_nombre: string;
  fecha: string;
  estado: EstadoPedido;
  notas: string | null;
  fecha_recepcion: string | null;
  lineas: { id: number; ingrediente_id: number; cantidad_pedida: number; precio_unitario: number | null; unidad: string }[];
}

interface RecomendacionItem {
  ingrediente_id: number;
  ingrediente: string;
  unidad: string;
  proveedor: string;
  stock_actual: number;
  consumo_semanal: number;
  par_level: number;
  cantidad_sugerida: number;
}

interface RecomendacionData {
  fecha: string;
  por_proveedor: { proveedor: string; items: RecomendacionItem[] }[];
}

interface Proveedor {
  id: number;
  nombre: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function calcTotal(lineas: PedidoListItem["lineas"]): number {
  return lineas.reduce((s, l) => s + l.cantidad_pedida * (l.precio_unitario ?? 0), 0);
}

const ESTADO_CLS: Record<EstadoPedido, string> = {
  borrador: "bg-amber-100 text-amber-700",
  enviado: "bg-blue-100 text-blue-700",
  recibido: "bg-green-100 text-green-700",
};

// ── Tab navigation ───────────────────────────────────────────────────────────

type Tab = "activos" | "propuesta" | "historial";

const TABS: { key: Tab; label: string }[] = [
  { key: "activos", label: "Activos" },
  { key: "propuesta", label: "Propuesta Pedido" },
  { key: "historial", label: "Historial" },
];

// ── Main component ───────────────────────────────────────────────────────────

export default function ComprasPage() {
  const { toast } = useToast();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("activos");
  const [pedidos, setPedidos] = useState<PedidoListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<PedidoListItem[]>("/api/pedidos")
      .then(setPedidos)
      .catch(() => toast("Error al cargar pedidos", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const switchTab = (t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", `/pedidos?tab=${t}`);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tab") as Tab | null;
    if (t && TABS.some((x) => x.key === t)) setTab(t);
  }, []);

  const borradores = pedidos.filter((p) => p.estado === "borrador");
  const enviados = pedidos.filter((p) => p.estado === "enviado");
  const recibidos = pedidos.filter((p) => p.estado === "recibido");

  return (
    <div>
      <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mb-6">
        Compras Ingredientes
      </h1>

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
            {t.key === "activos" && (borradores.length + enviados.length > 0) && (
              <span className="ml-1 text-xs opacity-70">({borradores.length + enviados.length})</span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">Cargando...</div>
      ) : (
        <>
          {tab === "activos" && (
            <TabActivos
              borradores={borradores}
              enviados={enviados}
              onAction={load}
            />
          )}
          {tab === "propuesta" && (
            <TabPropuesta onCreated={() => { load(); switchTab("activos"); }} />
          )}
          {tab === "historial" && (
            <TabHistorial recibidos={recibidos} />
          )}
        </>
      )}
    </div>
  );
}

// ── Tab: Activos ─────────────────────────────────────────────────────────────

function TabActivos({
  borradores,
  enviados,
  onAction,
}: {
  borradores: PedidoListItem[];
  enviados: PedidoListItem[];
  onAction: () => void;
}) {
  const { toast } = useToast();
  const router = useRouter();
  const [acting, setActing] = useState(false);

  const enviar = async (id: number) => {
    setActing(true);
    try {
      await apiFetch(`/api/pedidos/${id}/enviar`, { method: "POST" });
      toast("Pedido enviado");
      onAction();
    } catch { toast("Error al enviar", "error"); }
    finally { setActing(false); }
  };

  const recibir = async (id: number) => {
    setActing(true);
    try {
      await apiFetch(`/api/pedidos/${id}/recibir`, { method: "POST" });
      toast("Pedido recibido — stock actualizado");
      onAction();
    } catch { toast("Error al recibir", "error"); }
    finally { setActing(false); }
  };

  const eliminar = async (id: number) => {
    setActing(true);
    try {
      await apiFetch(`/api/pedidos/${id}`, { method: "DELETE" });
      toast("Pedido eliminado");
      onAction();
    } catch { toast("Error al eliminar", "error"); }
    finally { setActing(false); }
  };

  const PedidoCard = ({ p, actions }: { p: PedidoListItem; actions: React.ReactNode }) => (
    <div className="bg-white rounded-xl border border-cream-dark p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <p className="font-medium text-text">{p.proveedor_nombre}</p>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_CLS[p.estado]}`}>
              {p.estado === "borrador" ? "Borrador" : "Enviado"}
            </span>
          </div>
          <p className="text-xs text-warm-gray mt-0.5">
            #{p.id} · {formatDate(p.fecha)} · {p.lineas.length} item{p.lineas.length !== 1 ? "s" : ""}
          </p>
        </div>
        <p className="font-bold text-text">{formatARS(calcTotal(p.lineas))}</p>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => router.push(`/pedidos/${p.id}`)}
          className="px-3 py-1.5 border border-cream-dark rounded-lg text-xs hover:border-brot hover:text-brot transition-colors min-h-[36px]"
        >
          Ver detalle
        </button>
        {actions}
      </div>
    </div>
  );

  if (borradores.length === 0 && enviados.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
        No hay pedidos activos. Ve a "Propuesta Pedido" para crear uno basado en el stock actual.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {borradores.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-amber-700 uppercase tracking-wide mb-3">
            Borradores ({borradores.length})
          </h3>
          <div className="space-y-3">
            {borradores.map((p) => (
              <PedidoCard key={p.id} p={p} actions={
                <>
                  <button
                    onClick={() => enviar(p.id)}
                    disabled={acting}
                    className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition-colors min-h-[36px] disabled:opacity-50"
                  >
                    Enviar
                  </button>
                  <button
                    onClick={() => eliminar(p.id)}
                    disabled={acting}
                    className="px-3 py-1.5 text-red-600 text-xs hover:text-red-700 transition-colors min-h-[36px]"
                  >
                    Eliminar
                  </button>
                </>
              } />
            ))}
          </div>
        </div>
      )}

      {enviados.length > 0 && (
        <div>
          <h3 className="text-sm font-bold text-blue-700 uppercase tracking-wide mb-3">
            Enviados — Pendientes de recibir ({enviados.length})
          </h3>
          <div className="space-y-3">
            {enviados.map((p) => (
              <PedidoCard key={p.id} p={p} actions={
                <Link
                  href={`/pedidos/${p.id}`}
                  className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700 transition-colors min-h-[36px] inline-flex items-center"
                >
                  Registrar Recepcion
                </Link>
              } />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tab: Propuesta ───────────────────────────────────────────────────────────

function TabPropuesta({ onCreated }: { onCreated: () => void }) {
  const { toast } = useToast();
  const [data, setData] = useState<RecomendacionData | null>(null);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [cantidades, setCantidades] = useState<Record<number, string>>({});
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch<RecomendacionData>("/api/inventario/recomendacion"),
      apiFetch<Proveedor[]>("/api/proveedores"),
    ])
      .then(([rec, provs]) => {
        setData(rec);
        setProveedores(provs);
        const initial: Record<number, string> = {};
        for (const group of rec.por_proveedor) {
          for (const item of group.items) {
            if (item.cantidad_sugerida > 0) {
              initial[item.ingrediente_id] = String(item.cantidad_sugerida);
            }
          }
        }
        setCantidades(initial);
      })
      .catch(() => toast("Error al cargar recomendacion", "error"))
      .finally(() => setLoading(false));
  }, []);

  const crearPedido = async (proveedorNombre: string, items: RecomendacionItem[]) => {
    const lineas = items
      .filter((i) => {
        const val = cantidades[i.ingrediente_id];
        return val && parseFloat(val) > 0;
      })
      .map((i) => ({
        ingrediente_id: i.ingrediente_id,
        cantidad_pedida: parseFloat(cantidades[i.ingrediente_id]),
        unidad: i.unidad,
      }));

    if (lineas.length === 0) {
      toast("No hay items para pedir", "error");
      return;
    }

    const prov = proveedores.find((p) => p.nombre.toLowerCase() === proveedorNombre.toLowerCase());
    if (!prov) {
      toast(`Proveedor "${proveedorNombre}" no encontrado`, "error");
      return;
    }

    setCreating(true);
    try {
      await apiFetch("/api/pedidos", {
        method: "POST",
        body: JSON.stringify({
          proveedor_id: prov.id,
          lineas,
        }),
      });
      toast(`Pedido creado para ${proveedorNombre}`);
      onCreated();
    } catch {
      toast("Error al crear pedido", "error");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">Calculando recomendacion...</div>;
  }
  if (!data) return null;

  const totalItems = Object.values(cantidades).filter((v) => v && parseFloat(v) > 0).length;

  return (
    <>
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
        <p className="text-sm text-warm-gray">
          Basado en el stock actual y el consumo de las ultimas 8 semanas.
          Ajusta las cantidades y crea pedidos por proveedor.
        </p>
      </div>

      <div className="space-y-6">
        {data.por_proveedor.map((group) => {
          const groupItems = group.items.filter((i) => {
            const val = cantidades[i.ingrediente_id];
            return val && parseFloat(val) > 0;
          });

          return (
            <div key={group.proveedor} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              <div className="px-4 py-3 bg-cream/50 border-b border-cream-dark flex items-center justify-between">
                <div>
                  <p className="font-medium text-text">{group.proveedor}</p>
                  <p className="text-xs text-warm-gray">{group.items.length} ingredientes</p>
                </div>
                <PermissionGate module="pedidos_proveedores" action="create">
                  <button
                    onClick={() => crearPedido(group.proveedor, group.items)}
                    disabled={creating || groupItems.length === 0}
                    className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[40px] disabled:opacity-50"
                  >
                    {creating ? "..." : `Crear Pedido (${groupItems.length})`}
                  </button>
                </PermissionGate>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-cream-dark">
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Ingrediente</th>
                      <th className="text-right px-3 py-2 font-medium text-warm-gray">Stock</th>
                      <th className="text-right px-3 py-2 font-medium text-warm-gray">Consumo/sem</th>
                      <th className="text-right px-3 py-2 font-medium text-warm-gray">Par level</th>
                      <th className="text-right px-3 py-2 font-medium text-warm-gray">Pedir</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map((item, idx) => {
                      const val = cantidades[item.ingrediente_id] ?? "";
                      const hasCantidad = val !== "" && parseFloat(val) > 0;
                      const lowStock = item.stock_actual < item.consumo_semanal;
                      return (
                        <tr
                          key={item.ingrediente_id}
                          className={`${idx < group.items.length - 1 ? "border-b border-cream-dark" : ""} ${
                            hasCantidad ? "bg-brot/5" : lowStock ? "bg-red-50/50" : ""
                          }`}
                        >
                          <td className="px-4 py-2">
                            <p className="font-medium text-text">{item.ingrediente}</p>
                            <p className="text-xs text-warm-gray">{item.unidad}</p>
                          </td>
                          <td className={`text-right px-3 py-2 tabular-nums ${lowStock ? "text-red-600 font-medium" : "text-text"}`}>
                            {item.stock_actual}
                          </td>
                          <td className="text-right px-3 py-2 text-warm-gray tabular-nums">
                            {item.consumo_semanal}
                          </td>
                          <td className="text-right px-3 py-2 text-warm-gray tabular-nums">
                            {item.par_level}
                          </td>
                          <td className="text-right px-3 py-2">
                            <input
                              type="number"
                              inputMode="decimal"
                              min="0"
                              step="any"
                              value={val}
                              onChange={(e) =>
                                setCantidades((p) => ({ ...p, [item.ingrediente_id]: e.target.value }))
                              }
                              placeholder="0"
                              className="w-20 px-2 py-1 rounded-lg border border-cream-dark text-sm text-right focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[32px]"
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-warm-gray mt-3 text-right">
        {totalItems} item{totalItems !== 1 ? "s" : ""} para pedir
      </p>
    </>
  );
}

// ── Tab: Historial (pivot table) ─────────────────────────────────────────────

interface IngredienteInfo {
  id: number;
  nombre: string;
  unidad: string;
  proveedor: string;
}

function TabHistorial({ recibidos }: { recibidos: PedidoListItem[] }) {
  const { toast } = useToast();
  const [ingredientes, setIngredientes] = useState<IngredienteInfo[]>([]);

  useEffect(() => {
    apiFetch<Record<string, unknown>[]>("/api/ingredientes")
      .then((data) => setIngredientes(data.map((i) => ({
        id: i.id as number,
        nombre: i.nombre as string,
        unidad: i.unidad_uso as string,
        proveedor: (i.proveedor as string) || "Sin proveedor",
      }))))
      .catch(() => {});
  }, []);

  const ingMap = useMemo(
    () => new Map(ingredientes.map((i) => [i.id, i])),
    [ingredientes]
  );

  // All unique order dates, most recent first
  const allDates = useMemo(() => {
    const dates = new Set(recibidos.map((p) => p.fecha.split("T")[0]));
    return Array.from(dates).sort((a, b) => b.localeCompare(a));
  }, [recibidos]);

  // Build pivot: (ingrediente_id, fecha) -> cantidad
  const pivotData = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of recibidos) {
      const fecha = p.fecha.split("T")[0];
      for (const l of p.lineas) {
        const key = `${l.ingrediente_id}:${fecha}`;
        map.set(key, (map.get(key) ?? 0) + l.cantidad_pedida);
      }
    }
    return map;
  }, [recibidos]);

  // All ingredients that appear in orders, grouped by supplier
  const ingWithOrders = useMemo(() => {
    const ids = new Set<number>();
    for (const p of recibidos) {
      for (const l of p.lineas) ids.add(l.ingrediente_id);
    }
    return ingredientes
      .filter((i) => ids.has(i.id))
      .sort((a, b) => a.proveedor.localeCompare(b.proveedor) || a.nombre.localeCompare(b.nombre));
  }, [recibidos, ingredientes]);

  // Group by supplier
  const bySupplier = useMemo(() => {
    const map = new Map<string, IngredienteInfo[]>();
    for (const ing of ingWithOrders) {
      if (!map.has(ing.proveedor)) map.set(ing.proveedor, []);
      map.get(ing.proveedor)!.push(ing);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [ingWithOrders]);

  const shortDate = (d: string) => {
    const dt = new Date(d + "T00:00:00");
    return dt.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
  };

  if (recibidos.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
        No hay pedidos recibidos.
      </div>
    );
  }

  return (
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
                <th key={d} className="text-center px-2 py-2 font-medium text-warm-gray whitespace-nowrap">
                  {shortDate(d)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {bySupplier.map(([supplier, ings]) => (
              <Fragment key={supplier}>
                <tr className="bg-brot/5">
                  <td
                    colSpan={2 + allDates.length}
                    className="px-3 py-1.5 font-bold text-brot text-xs uppercase tracking-wide sticky left-0 bg-brot/5 z-10"
                  >
                    {supplier}
                  </td>
                </tr>
                {ings.map((ing, idx) => (
                  <tr
                    key={ing.id}
                    className={idx < ings.length - 1 ? "border-b border-cream-dark" : "border-b border-brot/10"}
                  >
                    <td className="px-3 py-1.5 font-medium text-text sticky left-0 bg-white z-10 whitespace-nowrap">
                      <Link href={`/ingredientes/${ing.id}`} className="hover:text-brot hover:underline">
                        {ing.nombre}
                      </Link>
                    </td>
                    <td className="px-2 py-1.5 text-warm-gray">{ing.unidad}</td>
                    {allDates.map((d) => {
                      const val = pivotData.get(`${ing.id}:${d}`);
                      return (
                        <td key={d} className={`text-center px-2 py-1.5 tabular-nums ${
                          val ? "text-text font-medium" : "text-cream-dark"
                        }`}>
                          {val ? `${val}` : "--"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-warm-gray p-3 text-right border-t border-cream-dark">
        {ingWithOrders.length} ingredientes · {allDates.length} pedidos
      </p>
    </div>
  );
}
