"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";

interface Ingrediente {
  id: number;
  nombre: string;
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

export default function HistorialStockPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [registros, setRegistros] = useState<RegistroStock[]>([]);
  const [ingredientes, setIngredientes] = useState<Ingrediente[]>([]);
  const [loading, setLoading] = useState(true);

  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split("T")[0];
  });
  const [fechaHasta, setFechaHasta] = useState(() => new Date().toISOString().split("T")[0]);
  const [ingredienteId, setIngredienteId] = useState<number | null>(null);

  const ingMap = useMemo(
    () => new Map(ingredientes.map((i) => [i.id, i.nombre])),
    [ingredientes]
  );

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (fechaDesde) params.set("fecha_desde", fechaDesde);
    if (fechaHasta) params.set("fecha_hasta", fechaHasta);
    if (ingredienteId) params.set("ingrediente_id", String(ingredienteId));

    Promise.all([
      apiFetch<RegistroStock[]>(`/api/inventario?${params.toString()}`),
      ingredientes.length === 0
        ? apiFetch<Ingrediente[]>("/api/ingredientes")
        : Promise.resolve(ingredientes),
    ])
      .then(([regs, ings]) => {
        setRegistros(regs);
        if (ingredientes.length === 0) setIngredientes(ings);
      })
      .catch(() => toast("Error al cargar historial", "error"))
      .finally(() => setLoading(false));
  }, [fechaDesde, fechaHasta, ingredienteId, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const groupedByDate = useMemo(() => {
    const groups: Record<string, RegistroStock[]> = {};
    for (const r of registros) {
      const key = r.fecha_registro;
      if (!groups[key]) groups[key] = [];
      groups[key].push(r);
    }
    return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
  }, [registros]);

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
          Historial de Stock
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
            <label className="block text-xs font-medium text-warm-gray mb-1">Ingrediente</label>
            <select
              value={ingredienteId ?? ""}
              onChange={(e) => setIngredienteId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            >
              <option value="">Todos</option>
              {ingredientes
                .filter((i) => i.activo)
                .map((i) => (
                  <option key={i.id} value={i.id}>{i.nombre}</option>
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
      ) : registros.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No hay registros en este periodo.
        </div>
      ) : (
        <div className="space-y-4">
          {groupedByDate.map(([fecha, regs]) => (
            <div key={fecha} className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              <div className="px-4 py-2.5 bg-cream/50 border-b border-cream-dark">
                <p className="text-sm font-medium text-text">{formatDate(fecha)}</p>
                <p className="text-xs text-warm-gray">{regs.length} registro{regs.length !== 1 ? "s" : ""}</p>
              </div>

              {/* Desktop table */}
              <div className="hidden md:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-cream-dark">
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Ingrediente</th>
                      <th className="text-right px-4 py-2 font-medium text-warm-gray">Cantidad</th>
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Ubicacion</th>
                      <th className="text-left px-4 py-2 font-medium text-warm-gray">Notas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {regs.map((r, idx) => (
                      <tr
                        key={r.id}
                        className={idx < regs.length - 1 ? "border-b border-cream-dark" : ""}
                      >
                        <td className="px-4 py-2.5 font-medium text-text">
                          {ingMap.get(r.ingrediente_id) ?? `#${r.ingrediente_id}`}
                        </td>
                        <td className="px-4 py-2.5 text-right text-text">
                          {r.cantidad}{" "}
                          <span className="text-warm-gray text-xs">{r.unidad}</span>
                        </td>
                        <td className="px-4 py-2.5 text-warm-gray">{r.ubicacion ?? "—"}</td>
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
                        <p className="font-medium text-text text-sm">
                          {ingMap.get(r.ingrediente_id) ?? `#${r.ingrediente_id}`}
                        </p>
                        {r.ubicacion && (
                          <p className="text-xs text-warm-gray mt-0.5">{r.ubicacion}</p>
                        )}
                        {r.notas && (
                          <p className="text-xs text-warm-gray mt-0.5">{r.notas}</p>
                        )}
                      </div>
                      <p className="text-sm font-bold text-text shrink-0">
                        {r.cantidad}{" "}
                        <span className="font-normal text-warm-gray">{r.unidad}</span>
                      </p>
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
          {registros.length} registro{registros.length !== 1 ? "s" : ""} total
        </p>
      )}
    </div>
  );
}
