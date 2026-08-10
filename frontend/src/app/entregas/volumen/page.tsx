"use client";

import { useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface VolumenItem {
  cliente_nombre: string;
  producto_nombre: string;
  total_cantidad: number;
  total_valor: number;
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(value);
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-xl border border-cream-dark p-4">
      <p className="text-xs font-medium text-warm-gray uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-medium text-brot mt-1">{value}</p>
    </div>
  );
}

type Vista = "todo" | "por_cliente" | "por_producto";

export default function VolumenPage() {
  const { toast } = useToast();

  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";

  const [fechaDesde, setFechaDesde] = useState(firstOfMonth);
  const [fechaHasta, setFechaHasta] = useState(today);
  const [data, setData] = useState<VolumenItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [vista, setVista] = useState<Vista>("todo");

  const handleFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fechaDesde || !fechaHasta) return;
    setLoading(true);
    setData([]);
    setSearched(false);
    try {
      const result = await apiFetch<VolumenItem[]>(
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

  const totales = useMemo(() => {
    const totalCantidad = data.reduce((sum, item) => sum + item.total_cantidad, 0);
    const totalValor = data.reduce((sum, item) => sum + item.total_valor, 0);
    return { totalCantidad, totalValor };
  }, [data]);

  const porCliente = useMemo(() => {
    const map = new Map<string, { total_cantidad: number; total_valor: number }>();
    for (const item of data) {
      const existing = map.get(item.cliente_nombre);
      if (existing) {
        existing.total_cantidad += item.total_cantidad;
        existing.total_valor += item.total_valor;
      } else {
        map.set(item.cliente_nombre, { total_cantidad: item.total_cantidad, total_valor: item.total_valor });
      }
    }
    return Array.from(map.entries())
      .map(([nombre, vals]) => ({ cliente_nombre: nombre, ...vals }))
      .sort((a, b) => b.total_valor - a.total_valor);
  }, [data]);

  const porProducto = useMemo(() => {
    const map = new Map<string, { total_cantidad: number; total_valor: number }>();
    for (const item of data) {
      const existing = map.get(item.producto_nombre);
      if (existing) {
        existing.total_cantidad += item.total_cantidad;
        existing.total_valor += item.total_valor;
      } else {
        map.set(item.producto_nombre, { total_cantidad: item.total_cantidad, total_valor: item.total_valor });
      }
    }
    return Array.from(map.entries())
      .map(([nombre, vals]) => ({ producto_nombre: nombre, ...vals }))
      .sort((a, b) => b.total_valor - a.total_valor);
  }, [data]);

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Analisis de Volumen
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Consulta los totales de entregas B2B por periodo.
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

      {searched && !loading && (
        <div className="space-y-6">
          {data.length === 0 ? (
            <div className="bg-white rounded-xl border border-cream-dark p-6 text-center text-warm-gray text-sm">
              No hay datos de volumen para el periodo seleccionado.
            </div>
          ) : (
            <>
              {/* Summary stats */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <StatCard label="Total cantidad" value={totales.totalCantidad} />
                <StatCard label="Total valor" value={formatCurrency(totales.totalValor)} />
                <StatCard label="Registros" value={data.length} />
              </div>

              {/* View toggle */}
              <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
                {([
                  ["todo", "Detalle"],
                  ["por_cliente", "Por cliente"],
                  ["por_producto", "Por producto"],
                ] as [Vista, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setVista(key)}
                    className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
                      vista === key
                        ? "bg-brot text-white"
                        : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Detail view - all items */}
              {vista === "todo" && (
                <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                  <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-cream-dark bg-cream/50">
                          <th className="text-left px-4 py-3 font-medium text-warm-gray">Cliente</th>
                          <th className="text-left px-4 py-3 font-medium text-warm-gray">Producto</th>
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad</th>
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Valor</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.map((row, idx) => (
                          <tr
                            key={idx}
                            className={idx < data.length - 1 ? "border-b border-cream-dark" : ""}
                          >
                            <td className="px-4 py-3 font-medium text-text">{row.cliente_nombre}</td>
                            <td className="px-4 py-3 text-text">{row.producto_nombre}</td>
                            <td className="px-4 py-3 text-right text-text">{row.total_cantidad}</td>
                            <td className="px-4 py-3 text-right font-medium text-brot">
                              {formatCurrency(row.total_valor)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {/* Mobile */}
                  <div className="md:hidden divide-y divide-cream-dark">
                    {data.map((row, idx) => (
                      <div key={idx} className="px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <p className="font-medium text-text">{row.cliente_nombre}</p>
                            <p className="text-xs text-warm-gray">{row.producto_nombre}</p>
                          </div>
                          <div className="text-right text-sm">
                            <p className="text-text">{row.total_cantidad} uds</p>
                            <p className="text-brot font-medium">{formatCurrency(row.total_valor)}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* By client view */}
              {vista === "por_cliente" && (
                <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                  <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-cream-dark bg-cream/50">
                          <th className="text-left px-4 py-3 font-medium text-warm-gray">Cliente</th>
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad total</th>
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Valor total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {porCliente.map((row, idx) => (
                          <tr
                            key={idx}
                            className={idx < porCliente.length - 1 ? "border-b border-cream-dark" : ""}
                          >
                            <td className="px-4 py-3 font-medium text-text">{row.cliente_nombre}</td>
                            <td className="px-4 py-3 text-right text-text">{row.total_cantidad}</td>
                            <td className="px-4 py-3 text-right font-medium text-brot">
                              {formatCurrency(row.total_valor)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {/* Mobile */}
                  <div className="md:hidden divide-y divide-cream-dark">
                    {porCliente.map((row, idx) => (
                      <div key={idx} className="px-4 py-3 flex items-center justify-between gap-2">
                        <p className="font-medium text-text">{row.cliente_nombre}</p>
                        <div className="text-right text-sm">
                          <p className="text-text">{row.total_cantidad} uds</p>
                          <p className="text-brot font-medium">{formatCurrency(row.total_valor)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* By product view */}
              {vista === "por_producto" && (
                <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
                  <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-cream-dark bg-cream/50">
                          <th className="text-left px-4 py-3 font-medium text-warm-gray">Producto</th>
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad total</th>
                          <th className="text-right px-4 py-3 font-medium text-warm-gray">Valor total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {porProducto.map((row, idx) => (
                          <tr
                            key={idx}
                            className={idx < porProducto.length - 1 ? "border-b border-cream-dark" : ""}
                          >
                            <td className="px-4 py-3 font-medium text-text">{row.producto_nombre}</td>
                            <td className="px-4 py-3 text-right text-text">{row.total_cantidad}</td>
                            <td className="px-4 py-3 text-right font-medium text-brot">
                              {formatCurrency(row.total_valor)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {/* Mobile */}
                  <div className="md:hidden divide-y divide-cream-dark">
                    {porProducto.map((row, idx) => (
                      <div key={idx} className="px-4 py-3 flex items-center justify-between gap-2">
                        <p className="font-medium text-text">{row.producto_nombre}</p>
                        <div className="text-right text-sm">
                          <p className="text-text">{row.total_cantidad} uds</p>
                          <p className="text-brot font-medium">{formatCurrency(row.total_valor)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {!loading && !searched && (
        <div className="text-center text-warm-gray py-12 text-sm">
          Selecciona un rango de fechas y pulsa Consultar.
        </div>
      )}
    </div>
  );
}
