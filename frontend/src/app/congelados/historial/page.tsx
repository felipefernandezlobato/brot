"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";

interface ProductoCongelado {
  id: number;
  nombre: string;
  unidad: string;
  is_active: boolean;
}

interface StockCongelado {
  id: number;
  producto_congelado_id: number;
  producto_nombre: string;
  cantidad: number;
  fecha_entrada: string;
  fecha_vencimiento: string | null;
  notas: string | null;
  is_active: boolean;
}

export default function HistorialCongeladosPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [entries, setEntries] = useState<StockCongelado[]>([]);
  const [productos, setProductos] = useState<ProductoCongelado[]>([]);
  const [loading, setLoading] = useState(true);

  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split("T")[0];
  });
  const [fechaHasta, setFechaHasta] = useState(() => new Date().toISOString().split("T")[0]);
  const [productoId, setProductoId] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (fechaDesde) params.set("fecha_desde", fechaDesde);
    if (fechaHasta) params.set("fecha_hasta", fechaHasta);
    if (productoId) params.set("producto_id", String(productoId));

    Promise.all([
      apiFetch<StockCongelado[]>(`/api/congelados?${params.toString()}`),
      productos.length === 0
        ? apiFetch<ProductoCongelado[]>("/api/congelados/productos")
        : Promise.resolve(productos),
    ])
      .then(([e, p]) => {
        setEntries(e);
        if (productos.length === 0) setProductos(p);
      })
      .catch(() => toast("Error al cargar historial", "error"))
      .finally(() => setLoading(false));
  }, [fechaDesde, fechaHasta, productoId, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const groupedByDate = useMemo(() => {
    const groups: Record<string, StockCongelado[]> = {};
    for (const e of entries) {
      const key = e.fecha_entrada;
      if (!groups[key]) groups[key] = [];
      groups[key].push(e);
    }
    return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
  }, [entries]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.back()}
          className="text-warm-gray hover:text-text transition-colors p-1 min-h-[44px] min-w-[44px] flex items-center justify-center"
        >
          ←
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Historial Congelados
        </h1>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">Producto</label>
            <select
              value={productoId ?? ""}
              onChange={(e) => setProductoId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            >
              <option value="">Todos</option>
              {productos
                .filter((p) => p.is_active)
                .map((p) => (
                  <option key={p.id} value={p.id}>{p.nombre}</option>
                ))}
            </select>
          </div>
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : entries.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay registros en este periodo.
        </div>
      ) : (
        <div className="space-y-4">
          {groupedByDate.map(([fecha, regs]) => (
            <div key={fecha} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              <div className="px-4 py-2.5 bg-cream/50 border-b border-cream-dark">
                <p className="text-sm font-medium text-text">{formatDate(fecha)}</p>
                <p className="text-xs text-warm-gray">{regs.length} entrada{regs.length !== 1 ? "s" : ""}</p>
              </div>

              {/* Desktop table */}
              <div className="hidden md:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-cream-dark">
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Producto</th>
                      <th className="text-right px-4 py-2 font-medium text-warm-gray">Cantidad</th>
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Vencimiento</th>
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {regs.map((r, idx) => (
                      <tr
                        key={r.id}
                        className={idx < regs.length - 1 ? "border-b border-cream-dark" : ""}
                      >
                        <td className="px-4 py-2.5 font-medium text-text">{r.producto_nombre}</td>
                        <td className="px-4 py-2.5 text-right text-text">{r.cantidad}</td>
                        <td className="px-4 py-2.5 text-warm-gray">
                          {r.fecha_vencimiento ? formatDate(r.fecha_vencimiento) : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-warm-gray">{r.notas ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden divide-y divide-cream-dark">
                {regs.map((r) => (
                  <div key={r.id} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-text text-sm">{r.producto_nombre}</p>
                        {r.fecha_vencimiento && (
                          <p className="text-xs text-warm-gray mt-0.5">
                            Vence: {formatDate(r.fecha_vencimiento)}
                          </p>
                        )}
                        {r.notas && (
                          <p className="text-xs text-warm-gray mt-0.5">{r.notas}</p>
                        )}
                      </div>
                      <p className="text-sm font-bold text-text shrink-0">{r.cantidad}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {entries.length} entrada{entries.length !== 1 ? "s" : ""} total
        </p>
      )}
    </div>
  );
}
