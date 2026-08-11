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

type Tab = "entregas" | "historial";
const TABS: { key: Tab; label: string }[] = [
  { key: "entregas", label: "Entregas" },
  { key: "historial", label: "Historial" },
];

export default function EntregasPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("historial");
  const [entregas, setEntregas] = useState<EntregaB2B[]>([]);
  const [clientes, setClientes] = useState<ClienteB2B[]>([]);
  const [productos, setProductos] = useState<ProductoCatalogo[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<EntregaB2B[]>("/api/entregas-b2b"),
      apiFetch<ClienteB2B[]>("/api/clientes-b2b"),
      apiFetch<ProductoCatalogo[]>("/api/catalogo"),
    ])
      .then(([e, c, p]) => { setEntregas(e); setClientes(c); setProductos(p); })
      .catch(() => toast("Error al cargar entregas", "error"))
      .finally(() => setLoading(false));
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
          Entregas B2B
        </h1>
        <Link href="/entregas/clientes" className="text-sm text-brot hover:text-brot-dark transition-colors">
          Clientes →
        </Link>
      </div>

      <div className="flex gap-1 bg-white rounded-xl border border-cream-dark p-1 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => switchTab(t.key)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${
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
          {tab === "entregas" && (
            <TabEntregas entregas={entregas} clientes={clientes} productos={productos} onReload={load} />
          )}
          {tab === "historial" && (
            <TabHistorial entregas={entregas} clientes={clientes} productos={productos} />
          )}
        </>
      )}
    </div>
  );
}

// ── Tab: Entregas (list + create) ────────────────────────────────────────────

function TabEntregas({
  entregas,
  clientes,
  productos,
  onReload,
}: {
  entregas: EntregaB2B[];
  clientes: ClienteB2B[];
  productos: ProductoCatalogo[];
  onReload: () => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const clienteMap = useMemo(() => new Map(clientes.map((c) => [c.id, c.nombre])), [clientes]);
  const prodMap = useMemo(() => new Map(productos.map((p) => [p.id, p])), [productos]);

  const recibir = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/entregas-b2b/${id}/estado`, { method: "PUT", body: JSON.stringify({ estado: "entregado" }) });
      toast("Entrega marcada como entregada"); onReload();
    } catch { toast("Error", "error"); } finally { setSaving(false); }
  };

  const eliminar = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/entregas-b2b/${id}`, { method: "DELETE" });
      toast("Entrega eliminada"); onReload();
    } catch { toast("Error", "error"); } finally { setSaving(false); }
  };

  return (
    <div className="space-y-3">
      {entregas.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay entregas.
        </div>
      ) : (
        entregas.map((e) => {
          const expanded = expandedId === e.id;
          return (
            <div key={e.id} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              <button
                onClick={() => setExpandedId(expanded ? null : e.id)}
                className="w-full text-left px-4 py-3 hover:bg-cream/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium text-text">{clienteMap.get(e.cliente_b2b_id) ?? "--"}</p>
                    <p className="text-xs text-warm-gray">{formatDate(e.fecha_entrega)} · {e.lineas.length} items</p>
                  </div>
                  <div className="flex items-center gap-2">
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
                      {e.lineas.map((l, idx) => {
                        const prod = prodMap.get(l.producto_id);
                        return (
                          <tr key={l.id} className={idx < e.lineas.length - 1 ? "border-b border-cream-dark" : ""}>
                            <td className="px-4 py-2 text-text">
                              {prod?.receta_id ? (
                                <Link href={`/escandallos/${prod.receta_id}`} className="hover:text-brot hover:underline">{prod.nombre}</Link>
                              ) : prod?.nombre ?? `#${l.producto_id}`}
                            </td>
                            <td className="px-4 py-2 text-right font-medium text-text tabular-nums">{l.cantidad}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  {e.estado !== "entregado" && (
                    <div className="px-4 py-3 border-t border-cream-dark flex gap-2">
                      <button onClick={() => recibir(e.id)} disabled={saving}
                        className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs min-h-[36px] disabled:opacity-50">
                        Marcar entregado
                      </button>
                      <button onClick={() => eliminar(e.id)} disabled={saving}
                        className="px-3 py-1.5 text-red-600 text-xs min-h-[36px]">
                        Eliminar
                      </button>
                    </div>
                  )}
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

  // Group entregas by client
  const byClient = useMemo(() => {
    const map = new Map<number, EntregaB2B[]>();
    for (const e of entregas) {
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

  if (entregas.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
        No hay entregas registradas.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {byClient.map(({ clienteId, clienteNombre, entregas: clienteEntregas }) => {
        // Dates for this client, most recent first
        const dates = Array.from(new Set(clienteEntregas.map((e) => e.fecha_entrega.split("T")[0])))
          .sort((a, b) => b.localeCompare(a));

        // All products delivered to this client
        const prodIds = new Set<number>();
        for (const e of clienteEntregas) {
          for (const l of e.lineas) prodIds.add(l.producto_id);
        }
        const clienteProducts = Array.from(prodIds)
          .map((id) => prodMap.get(id))
          .filter(Boolean) as ProductoCatalogo[];
        clienteProducts.sort((a, b) => a.nombre.localeCompare(b.nombre));

        // Pivot: (producto_id, fecha) -> cantidad
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
