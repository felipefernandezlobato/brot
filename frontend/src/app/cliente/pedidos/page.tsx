"use client";

import { useEffect, useState } from "react";
import { CustomerAuthGuard } from "@/components/CustomerAuthGuard";
import { CustomerNav } from "@/components/CustomerNav";
import { apiClienteFetch } from "@/lib/api-cliente";
import { useToast } from "@/components/Toast";
import { Cliente } from "@/lib/types";

// ── Types ──────────────────────────────────────────────────────────────────

interface LineaPedido {
  producto_id: number;
  producto_nombre: string;
  cantidad: number;
  precio_unitario: number;
}

interface Pedido {
  id: number;
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
    weekday: "long",
    day: "numeric",
    month: "long",
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

const ESTADO_CONFIG: Record<
  string,
  { label: string; className: string }
> = {
  pendiente: {
    label: "Pendiente",
    className: "bg-yellow-100 text-yellow-800",
  },
  confirmado: {
    label: "Confirmado",
    className: "bg-blue-100 text-blue-800",
  },
  en_proceso: {
    label: "En proceso",
    className: "bg-orange-100 text-orange-800",
  },
  entregado: {
    label: "Entregado",
    className: "bg-green-100 text-green-800",
  },
  cancelado: {
    label: "Cancelado",
    className: "bg-red-100 text-red-800",
  },
};

function EstadoBadge({ estado }: { estado: string }) {
  const cfg = ESTADO_CONFIG[estado] ?? {
    label: estado,
    className: "bg-cream-dark text-warm-gray",
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${cfg.className}`}
    >
      {cfg.label}
    </span>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

function MisPedidosList({ cliente }: { cliente: Cliente }) {
  const { toast } = useToast();
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    apiClienteFetch<Pedido[]>("/api/cliente/pedidos")
      .then(setPedidos)
      .catch(() => toast("Error al cargar tus pedidos", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <CustomerNav nombre={cliente.nombre} />

      <main className="flex-1 max-w-3xl mx-auto w-full px-4 py-6">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mb-6">
          Mis Pedidos
        </h1>

        {loading ? (
          <p className="text-warm-gray text-center py-12">
            Cargando pedidos...
          </p>
        ) : pedidos.length === 0 ? (
          <div className="text-center py-12 text-warm-gray">
            <p className="text-lg">Aún no tienes pedidos</p>
            <p className="text-sm mt-1">
              Visita el catálogo para hacer tu primer pedido.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pedidos.map((pedido) => {
              const expanded = expandedId === pedido.id;
              return (
                <div
                  key={pedido.id}
                  className="bg-white rounded-xl border border-cream-dark overflow-hidden"
                >
                  {/* Header row */}
                  <button
                    className="w-full text-left px-4 py-4 flex items-start justify-between gap-3 hover:bg-cream/30 transition-colors"
                    onClick={() =>
                      setExpandedId(expanded ? null : pedido.id)
                    }
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <EstadoBadge estado={pedido.estado} />
                        <span className="text-xs text-warm-gray">
                          #{pedido.id}
                        </span>
                      </div>
                      <p className="text-sm text-text font-medium capitalize">
                        Entrega: {formatDate(pedido.fecha_entrega)}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-semibold text-brot">
                        {formatPrice(pedido.total)}
                      </p>
                      <p className="text-xs text-warm-gray mt-0.5">
                        {expanded ? "▲ Ocultar" : "▼ Ver detalle"}
                      </p>
                    </div>
                  </button>

                  {/* Expanded detail */}
                  {expanded && pedido.lineas && pedido.lineas.length > 0 && (
                    <div className="border-t border-cream-dark px-4 py-3 divide-y divide-cream-dark">
                      {pedido.lineas.map((linea, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between py-2 text-sm gap-3"
                        >
                          <span className="text-text flex-1">
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
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

export default function MisPedidosPage() {
  return (
    <CustomerAuthGuard>
      {(cliente) => <MisPedidosList cliente={cliente} />}
    </CustomerAuthGuard>
  );
}
