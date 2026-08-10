"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS, formatDateTime } from "@/lib/format";

type Motivo = "caducado" | "dañado" | "produccion" | "otro";

interface Merma {
  id: number;
  ingrediente_id: number | null;
  receta_id: number | null;
  nombre_libre: string | null;
  cantidad: number;
  unidad: string;
  motivo: Motivo;
  notas: string | null;
  fecha: string;
  ubicacion: string | null;
  coste_unitario: number;
  coste_total: number;
  registered_by: number | null;
  registered_at: string;
}

const MOTIVO_LABELS: Record<Motivo, string> = {
  caducado: "Caducado",
  dañado: "Dañado",
  produccion: "Producción",
  otro: "Otro",
};

const MOTIVO_COLORS: Record<Motivo, string> = {
  caducado: "bg-amber-100 text-amber-800",
  dañado: "bg-red-100 text-red-700",
  produccion: "bg-blue-100 text-blue-700",
  otro: "bg-gray-100 text-warm-gray",
};

const MOTIVO_FILTERS: (Motivo | "todos")[] = [
  "todos",
  "caducado",
  "dañado",
  "produccion",
  "otro",
];

function getDefaultDates() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return {
    desde: from.toISOString().slice(0, 10),
    hasta: to.toISOString().slice(0, 10),
  };
}

function itemName(m: Merma): string {
  return m.nombre_libre ?? "Ingrediente";
}

export default function MermasPage() {
  const router = useRouter();
  const { toast } = useToast();

  const defaults = getDefaultDates();
  const [mermas, setMermas] = useState<Merma[]>([]);
  const [loading, setLoading] = useState(true);
  const [fechaDesde, setFechaDesde] = useState(defaults.desde);
  const [fechaHasta, setFechaHasta] = useState(defaults.hasta);
  const [motivo, setMotivo] = useState<Motivo | "todos">("todos");
  const [deleting, setDeleting] = useState<number | null>(null);

  const fetchMermas = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (fechaDesde) params.set("fecha_desde", fechaDesde);
    if (fechaHasta) params.set("fecha_hasta", fechaHasta);
    if (motivo !== "todos") params.set("motivo", motivo);
    apiFetch<Merma[]>(`/api/mermas?${params}`)
      .then(setMermas)
      .catch(() => toast("Error al cargar mermas", "error"))
      .finally(() => setLoading(false));
  }, [fechaDesde, fechaHasta, motivo]);

  useEffect(() => {
    fetchMermas();
  }, [fetchMermas]);

  async function handleDelete(id: number) {
    if (!confirm("¿Eliminar este registro de merma?")) return;
    setDeleting(id);
    try {
      await apiFetch(`/api/mermas/${id}`, { method: "DELETE" });
      toast("Merma eliminada");
      setMermas((prev) => prev.filter((m) => m.id !== id));
    } catch {
      toast("Error al eliminar", "error");
    } finally {
      setDeleting(null);
    }
  }

  const costoTotal = mermas.reduce((sum, m) => sum + (m.coste_total ?? 0), 0);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Mermas
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/mermas/analisis")}
            className="border border-brot text-brot px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot/5 transition-colors min-h-[44px] whitespace-nowrap"
          >
            Ver Análisis
          </button>
          <button
            onClick={() => router.push("/mermas/nuevo")}
            className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] whitespace-nowrap"
          >
            + Registrar Merma
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Desde
            </label>
            <input
              type="date"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Hasta
            </label>
            <input
              type="date"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] text-sm"
            />
          </div>
        </div>

        {/* Motivo filter chips */}
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {MOTIVO_FILTERS.map((m) => (
            <button
              key={m}
              onClick={() => setMotivo(m)}
              className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
                motivo === m
                  ? "bg-brot text-white"
                  : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
              }`}
            >
              {m === "todos" ? "Todos" : MOTIVO_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {/* Summary bar */}
      {!loading && mermas.length > 0 && (
        <div className="flex items-center justify-between mb-3 px-1">
          <p className="text-xs text-warm-gray">
            {mermas.length} registro{mermas.length !== 1 ? "s" : ""}
          </p>
          <p className="text-sm font-medium text-red-700">
            Total: {formatARS(costoTotal)}
          </p>
        </div>
      )}

      {/* List */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : mermas.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No hay mermas registradas en este período.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Ítem
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Cantidad
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Motivo
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Coste
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Fecha
                    </th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {mermas.map((m, idx) => (
                    <tr
                      key={m.id}
                      className={`transition-colors ${
                        idx < mermas.length - 1 ? "border-b border-cream-dark" : ""
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-text">
                        {itemName(m)}
                        {m.notas && (
                          <p className="text-xs text-warm-gray font-normal truncate max-w-[200px]">
                            {m.notas}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-text">
                        {m.cantidad}{" "}
                        <span className="text-warm-gray text-xs">{m.unidad}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                            MOTIVO_COLORS[m.motivo]
                          }`}
                        >
                          {MOTIVO_LABELS[m.motivo]}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {m.coste_total != null ? (
                          <span className="text-red-700 font-medium">
                            {formatARS(m.coste_total)}
                          </span>
                        ) : (
                          <span className="text-warm-gray">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-warm-gray text-xs">
                        {formatDateTime(m.registered_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDelete(m.id)}
                          disabled={deleting === m.id}
                          className="text-warm-gray hover:text-red-600 transition-colors text-xs disabled:opacity-50"
                        >
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {mermas.map((m) => (
                <div key={m.id} className="px-4 py-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-text truncate">
                        {itemName(m)}
                      </p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                            MOTIVO_COLORS[m.motivo]
                          }`}
                        >
                          {MOTIVO_LABELS[m.motivo]}
                        </span>
                        <span className="text-xs text-warm-gray">
                          {m.cantidad} {m.unidad}
                        </span>
                      </div>
                      {m.notas && (
                        <p className="text-xs text-warm-gray mt-0.5 truncate">
                          {m.notas}
                        </p>
                      )}
                      <p className="text-xs text-warm-gray mt-0.5">
                        {formatDateTime(m.registered_at)}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      {m.coste_total != null ? (
                        <p className="text-sm font-medium text-red-700">
                          {formatARS(m.coste_total)}
                        </p>
                      ) : (
                        <p className="text-sm text-warm-gray">—</p>
                      )}
                      <button
                        onClick={() => handleDelete(m.id)}
                        disabled={deleting === m.id}
                        className="text-xs text-warm-gray hover:text-red-600 mt-1 transition-colors disabled:opacity-50"
                      >
                        Eliminar
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
