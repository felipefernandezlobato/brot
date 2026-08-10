"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatARS, formatDateTime } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

type EstadoPedido = "borrador" | "enviado" | "recibido";

interface PedidoListItem {
  id: number;
  proveedor_id: number;
  proveedor_nombre: string;
  fecha: string;
  estado: EstadoPedido;
  notas: string | null;
  fecha_recepcion: string | null;
  lineas: { id: number; cantidad_pedida: number; precio_unitario: number | null }[];
}

function calcTotalEstimado(lineas: PedidoListItem["lineas"]): number {
  return lineas.reduce(
    (sum, l) => sum + l.cantidad_pedida * (l.precio_unitario ?? 0),
    0
  );
}

const ESTADO_LABELS: Record<EstadoPedido, string> = {
  borrador: "Borrador",
  enviado: "Enviado",
  recibido: "Recibido",
};

const ESTADO_CLASSES: Record<EstadoPedido, string> = {
  borrador: "bg-gray-100 text-gray-600",
  enviado: "bg-blue-50 text-blue-700",
  recibido: "bg-green-50 text-green-700",
};

function EstadoBadge({ estado }: { estado: EstadoPedido }) {
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_CLASSES[estado]}`}
    >
      {ESTADO_LABELS[estado]}
    </span>
  );
}

const ESTADOS: Array<EstadoPedido | "todos"> = [
  "todos",
  "borrador",
  "enviado",
  "recibido",
];

const ESTADO_FILTER_LABELS: Record<EstadoPedido | "todos", string> = {
  todos: "Todos",
  borrador: "Borrador",
  enviado: "Enviado",
  recibido: "Recibido",
};

export default function PedidosPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [pedidos, setPedidos] = useState<PedidoListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroEstado, setFiltroEstado] = useState<EstadoPedido | "todos">(
    "todos"
  );

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filtroEstado !== "todos") params.set("estado", filtroEstado);
    apiFetch<PedidoListItem[]>(`/api/pedidos?${params}`)
      .then(setPedidos)
      .catch(() => toast("Error al cargar pedidos", "error"))
      .finally(() => setLoading(false));
  }, [filtroEstado, toast]);

  const grouped = pedidos;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Pedidos
        </h1>
        <PermissionGate module="pedidos" action="create">
          <Link
            href="/pedidos/nuevo"
            className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] flex items-center whitespace-nowrap"
          >
            + Nuevo Pedido
          </Link>
        </PermissionGate>
      </div>

      {/* Status filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        {ESTADOS.map((e) => (
          <button
            key={e}
            onClick={() => setFiltroEstado(e)}
            className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
              filtroEstado === e
                ? "bg-brot text-white"
                : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
            }`}
          >
            {ESTADO_FILTER_LABELS[e]}
          </button>
        ))}
      </div>

      {/* List */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : grouped.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No hay pedidos{filtroEstado !== "todos" ? ` en estado "${ESTADO_LABELS[filtroEstado as EstadoPedido]}"` : ""}.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      #
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Proveedor
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Fecha
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Estado
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Total est.
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {grouped.map((p, idx) => (
                    <tr
                      key={p.id}
                      onClick={() => router.push(`/pedidos/${p.id}`)}
                      className={`cursor-pointer hover:bg-cream/40 transition-colors ${
                        idx < grouped.length - 1
                          ? "border-b border-cream-dark"
                          : ""
                      }`}
                    >
                      <td className="px-4 py-3 text-warm-gray font-mono text-xs">
                        #{p.id}
                      </td>
                      <td className="px-4 py-3 font-medium text-text">
                        {p.proveedor_nombre}
                      </td>
                      <td className="px-4 py-3 text-warm-gray text-xs">
                        {formatDateTime(p.fecha)}
                      </td>
                      <td className="px-4 py-3">
                        <EstadoBadge estado={p.estado} />
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-text">
                        {formatARS(calcTotalEstimado(p.lineas))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {grouped.map((p) => (
                <button
                  key={p.id}
                  onClick={() => router.push(`/pedidos/${p.id}`)}
                  className="w-full text-left px-4 py-4 hover:bg-cream/40 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium text-text">
                          {p.proveedor_nombre}
                        </p>
                        <EstadoBadge estado={p.estado} />
                      </div>
                      <p className="text-xs text-warm-gray mt-0.5">
                        #{p.id} · {formatDateTime(p.fecha)}
                      </p>
                    </div>
                    <p className="text-sm font-medium text-text shrink-0">
                      {formatARS(calcTotalEstimado(p.lineas))}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {grouped.length} pedido{grouped.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
