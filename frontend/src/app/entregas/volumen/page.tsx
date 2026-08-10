"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface VolumenCliente {
  cliente_id: number;
  cliente_nombre: string;
  total_entregas: number;
  total_productos?: number;
  importe_total?: number;
}

interface VolumenProducto {
  producto_id?: number;
  producto_nombre: string;
  cantidad_total: number;
  unidad?: string;
  importe_total?: number;
}

interface VolumenResponse {
  fecha_desde?: string;
  fecha_hasta?: string;
  total_entregas?: number;
  por_cliente?: VolumenCliente[];
  por_producto?: VolumenProducto[];
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-xl border border-cream-dark p-4">
      <p className="text-xs font-medium text-warm-gray uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-medium text-brot mt-1">{value}</p>
    </div>
  );
}

export default function VolumenPage() {
  const { toast } = useToast();

  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";

  const [fechaDesde, setFechaDesde] = useState(firstOfMonth);
  const [fechaHasta, setFechaHasta] = useState(today);
  const [data, setData] = useState<VolumenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fechaDesde || !fechaHasta) return;
    setLoading(true);
    setData(null);
    setSearched(false);
    try {
      const result = await apiFetch<VolumenResponse>(
        `/api/entregas-b2b/volumen?fecha_desde=${fechaDesde}&fecha_hasta=${fechaHasta}`
      );
      setData(result);
      setSearched(true);
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al obtener volumen", "error");
    } finally {
      setLoading(false);
    }
  };

  const porCliente = data?.por_cliente ?? [];
  const porProducto = data?.por_producto ?? [];
  const showSummary = data !== null && data.total_entregas != null;
  const showClientes = porCliente.length > 0;
  const showProductos = porProducto.length > 0;
  const showEmpty =
    searched && !loading && data !== null && !showSummary && !showClientes && !showProductos;
  const showPlaceholder = !loading && !searched;

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Análisis de Volumen
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Consulta los totales de entregas B2B por período.
        </p>
      </div>

      {/* Date range form */}
      <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
        <form onSubmit={handleFetch}>
          <div className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Desde <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={fechaDesde}
                onChange={(e) => setFechaDesde(e.target.value)}
                required
                className="px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Hasta <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={fechaHasta}
                onChange={(e) => setFechaHasta(e.target.value)}
                required
                min={fechaDesde}
                className="px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {loading ? "Consultando..." : "Consultar"}
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {loading ? (
        <div className="text-center text-warm-gray py-12">Cargando datos...</div>
      ) : null}

      {data != null && (
        <div className="space-y-6">
          {/* Summary stat */}
          {data.total_entregas != null && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <StatCard label="Total entregas" value={data.total_entregas} />
            </div>
          )}

          {/* Por cliente */}
          {porCliente.length > 0 && (
            <div>
              <h3 className="font-medium text-text mb-3">Por cliente</h3>
              <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-cream-dark bg-cream/50">
                        <th className="text-left px-4 py-3 font-medium text-warm-gray">Cliente</th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">Entregas</th>
                        {porCliente[0]?.total_productos != null && (
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Productos</th>
                        )}
                        {porCliente[0]?.importe_total != null && (
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Importe</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {porCliente.map((row, idx) => (
                        <tr
                          key={row.cliente_id ?? idx}
                          className={idx < porCliente.length - 1 ? "border-b border-cream-dark" : ""}
                        >
                          <td className="px-4 py-3 font-medium text-text">{row.cliente_nombre}</td>
                          <td className="px-4 py-3 text-right text-text">{row.total_entregas}</td>
                          {row.total_productos != null && (
                            <td className="px-4 py-3 text-right text-text">{row.total_productos}</td>
                          )}
                          {row.importe_total != null && (
                            <td className="px-4 py-3 text-right font-medium text-brot">
                              {new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(row.importe_total)}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {/* Mobile */}
                <div className="md:hidden divide-y divide-cream-dark">
                  {porCliente.map((row, idx) => (
                    <div key={row.cliente_id ?? idx} className="px-4 py-3 flex items-center justify-between gap-2">
                      <p className="font-medium text-text">{row.cliente_nombre}</p>
                      <div className="text-right text-sm">
                        <p className="text-text">{row.total_entregas} entregas</p>
                        {row.total_productos != null && (
                          <p className="text-warm-gray text-xs">{row.total_productos} productos</p>
                        )}
                        {row.importe_total != null && (
                          <p className="text-brot font-medium">
                            {new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(row.importe_total)}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Por producto */}
          {porProducto.length > 0 && (
            <div>
              <h3 className="font-medium text-text mb-3">Por producto</h3>
              <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-cream-dark bg-cream/50">
                        <th className="text-left px-4 py-3 font-medium text-warm-gray">Producto</th>
                        <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad</th>
                        {porProducto[0]?.unidad && (
                          <th className="text-left px-4 py-3 font-medium text-warm-gray">Unidad</th>
                        )}
                        {porProducto[0]?.importe_total != null && (
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Importe</th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {porProducto.map((row, idx) => (
                        <tr
                          key={row.producto_id ?? idx}
                          className={idx < porProducto.length - 1 ? "border-b border-cream-dark" : ""}
                        >
                          <td className="px-4 py-3 font-medium text-text">{row.producto_nombre}</td>
                          <td className="px-4 py-3 text-right text-text">{row.cantidad_total}</td>
                          {row.unidad && (
                            <td className="px-4 py-3 text-warm-gray">{row.unidad}</td>
                          )}
                          {row.importe_total != null && (
                            <td className="px-4 py-3 text-right font-medium text-brot">
                              {new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(row.importe_total)}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {/* Mobile */}
                <div className="md:hidden divide-y divide-cream-dark">
                  {porProducto.map((row, idx) => (
                    <div key={row.producto_id ?? idx} className="px-4 py-3 flex items-center justify-between gap-2">
                      <p className="font-medium text-text">{row.producto_nombre}</p>
                      <div className="text-right text-sm">
                        <p className="text-text">
                          {row.cantidad_total}
                          {row.unidad ? ` ${row.unidad}` : ""}
                        </p>
                        {row.importe_total != null && (
                          <p className="text-brot font-medium">
                            {new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(row.importe_total)}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Fallback: no structured data but we got something */}
          {porCliente.length === 0 && porProducto.length === 0 && data.total_entregas == null && (
            <div className="bg-white rounded-xl border border-cream-dark p-6 text-center text-warm-gray text-sm">
              No hay datos de volumen para el período seleccionado.
            </div>
          )}
        </div>
      )}

      {!loading && !data && !searched && (
        <div className="text-center text-warm-gray py-12 text-sm">
          Selecciona un rango de fechas y pulsa Consultar.
        </div>
      )}
    </div>
  );
}
