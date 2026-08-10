"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

// ── Types ──────────────────────────────────────────────────────────────────

interface LineaPedido {
  producto_id: number;
  producto_nombre: string;
  cantidad: number;
  precio_unitario: number;
}

interface PedidoCliente {
  id: number;
  cliente_id: number;
  cliente_nombre: string;
  cliente_email: string;
  fecha_entrega: string;
  estado: string;
  total: number;
  lineas: LineaPedido[];
  creado_en?: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString("es-AR", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatPrice(n: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(n);
}

const ESTADOS = [
  { value: "pendiente", label: "Pendiente" },
  { value: "confirmado", label: "Confirmado" },
  { value: "en_proceso", label: "En proceso" },
  { value: "entregado", label: "Entregado" },
  { value: "cancelado", label: "Cancelado" },
];

const ESTADO_CONFIG: Record<string, { label: string; className: string }> = {
  pendiente: { label: "Pendiente", className: "bg-yellow-100 text-yellow-800" },
  confirmado: { label: "Confirmado", className: "bg-blue-100 text-blue-800" },
  en_proceso: { label: "En proceso", className: "bg-orange-100 text-orange-800" },
  entregado: { label: "Entregado", className: "bg-green-100 text-green-800" },
  cancelado: { label: "Cancelado", className: "bg-red-100 text-red-800" },
};

function EstadoBadge({ estado }: { estado: string }) {
  const cfg = ESTADO_CONFIG[estado] ?? {
    label: estado,
    className: "bg-cream-dark text-warm-gray",
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.className}`}
    >
      {cfg.label}
    </span>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AdminPedidosClientesPage() {
  const { toast } = useToast();

  const [pedidos, setPedidos] = useState<PedidoCliente[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [filterEstado, setFilterEstado] = useState("todos");
  const [filterFecha, setFilterFecha] = useState("");

  // Expanded row
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Status change state
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<PedidoCliente[]>("/api/admin/pedidos-clientes")
      .then(setPedidos)
      .catch(() => toast("Error al cargar pedidos de clientes", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    return pedidos.filter((p) => {
      const matchEstado =
        filterEstado === "todos" || p.estado === filterEstado;
      const matchFecha =
        !filterFecha || p.fecha_entrega === filterFecha;
      return matchEstado && matchFecha;
    });
  }, [pedidos, filterEstado, filterFecha]);

  const handleEstadoChange = async (id: number, nuevoEstado: string) => {
    setUpdatingId(id);
    try {
      await apiFetch(`/api/admin/pedidos-clientes/${id}/estado`, {
        method: "PUT",
        body: JSON.stringify({ estado: nuevoEstado }),
      });
      toast("Estado actualizado");
      setPedidos((prev) =>
        prev.map((p) => (p.id === id ? { ...p, estado: nuevoEstado } : p))
      );
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al actualizar estado";
      toast(msg, "error");
    } finally {
      setUpdatingId(null);
    }
  };

  // Stats
  const stats = useMemo(() => {
    const byEstado = pedidos.reduce<Record<string, number>>((acc, p) => {
      acc[p.estado] = (acc[p.estado] ?? 0) + 1;
      return acc;
    }, {});
    const total = pedidos.reduce((s, p) => s + p.total, 0);
    return { byEstado, total };
  }, [pedidos]);

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Pedidos de Clientes
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Gestiona y actualiza el estado de todos los pedidos de la tienda online.
        </p>
      </div>

      {/* Stats strip */}
      {!loading && pedidos.length > 0 && (
        <div className="flex gap-3 mb-6 flex-wrap">
          {ESTADOS.map(({ value, label }) => {
            const count = stats.byEstado[value] ?? 0;
            if (count === 0) return null;
            const cfg = ESTADO_CONFIG[value];
            return (
              <button
                key={value}
                onClick={() =>
                  setFilterEstado(filterEstado === value ? "todos" : value)
                }
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  filterEstado === value
                    ? cfg.className + " ring-2 ring-offset-1 ring-current"
                    : "bg-cream border border-cream-dark text-warm-gray hover:bg-cream-dark"
                }`}
              >
                {label}: {count}
              </button>
            );
          })}
          <span className="ml-auto text-sm text-warm-gray self-center">
            Total: {formatPrice(stats.total)}
          </span>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap items-center">
        <select
          value={filterEstado}
          onChange={(e) => setFilterEstado(e.target.value)}
          className="px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[40px]"
        >
          <option value="todos">Todos los estados</option>
          {ESTADOS.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <input
          type="date"
          value={filterFecha}
          onChange={(e) => setFilterFecha(e.target.value)}
          className="px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[40px]"
          title="Filtrar por fecha de entrega"
        />

        {(filterEstado !== "todos" || filterFecha) && (
          <button
            onClick={() => {
              setFilterEstado("todos");
              setFilterFecha("");
            }}
            className="text-sm text-warm-gray hover:text-text transition-colors"
          >
            Limpiar filtros
          </button>
        )}

        <span className="text-sm text-warm-gray ml-auto">
          {filtered.length} pedido{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">
            Cargando pedidos...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            {pedidos.length === 0
              ? "Aún no hay pedidos de clientes."
              : "Sin pedidos con los filtros actuales."}
          </div>
        ) : (
          <div className="divide-y divide-cream-dark">
            {filtered.map((pedido) => {
              const expanded = expandedId === pedido.id;
              const isUpdating = updatingId === pedido.id;

              return (
                <div key={pedido.id}>
                  {/* Main row */}
                  <div className="flex items-start gap-3 px-4 py-4">
                    {/* Toggle */}
                    <button
                      onClick={() =>
                        setExpandedId(expanded ? null : pedido.id)
                      }
                      className="text-warm-gray hover:text-brot transition-colors mt-0.5 min-w-[20px] text-sm"
                      aria-label={expanded ? "Contraer" : "Expandir"}
                    >
                      {expanded ? "▲" : "▼"}
                    </button>

                    {/* Client info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <EstadoBadge estado={pedido.estado} />
                        <span className="text-xs text-warm-gray">
                          #{pedido.id}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-text">
                        {pedido.cliente_nombre}
                      </p>
                      <p className="text-xs text-warm-gray">
                        {pedido.cliente_email}
                      </p>
                      <p className="text-xs text-warm-gray capitalize mt-1">
                        Entrega: {formatDate(pedido.fecha_entrega)}
                      </p>
                    </div>

                    {/* Price + status selector */}
                    <div className="shrink-0 text-right flex flex-col items-end gap-2">
                      <span className="font-semibold text-brot text-sm">
                        {formatPrice(pedido.total)}
                      </span>
                      <select
                        value={pedido.estado}
                        disabled={isUpdating}
                        onChange={(e) =>
                          handleEstadoChange(pedido.id, e.target.value)
                        }
                        className="text-xs border border-cream-dark rounded-lg px-2 py-1 bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[32px] disabled:opacity-50"
                      >
                        {ESTADOS.map(({ value, label }) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Expanded: order lines */}
                  {expanded && (
                    <div className="border-t border-cream-dark bg-cream/30 px-4 py-3">
                      <p className="text-xs font-semibold text-warm-gray uppercase tracking-wider mb-2">
                        Líneas del pedido
                      </p>
                      {pedido.lineas && pedido.lineas.length > 0 ? (
                        <div className="divide-y divide-cream-dark">
                          {pedido.lineas.map((linea, i) => (
                            <div
                              key={i}
                              className="flex items-center justify-between py-1.5 text-sm gap-3"
                            >
                              <span className="text-text">
                                {linea.cantidad}× {linea.producto_nombre}
                              </span>
                              <span className="text-warm-gray shrink-0">
                                {formatPrice(
                                  (linea.precio_unitario ?? 0) * linea.cantidad
                                )}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-warm-gray">
                          Sin líneas disponibles.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
