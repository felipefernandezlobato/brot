"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { Categoria } from "@/lib/types";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

interface RecetaListItem {
  id: number;
  nombre: string;
  categoria_id: number;
  categoria_nombre: string;
  porciones_por_lote: number;
  precio_venta: number | null;
  es_subreceta: boolean;
  costo_total: number;
  costo_por_porcion: number;
  margen: number | null;
  multi: number | null;
}

function MargenBadge({
  margen,
  objetivo,
}: {
  margen: number | null;
  objetivo: number | null;
}) {
  if (margen === null) {
    return (
      <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">
        —
      </span>
    );
  }

  if (objetivo === null) {
    return (
      <span className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700">
        {margen.toFixed(1)}%
      </span>
    );
  }

  let colorClass = "";
  if (margen >= objetivo) {
    colorClass = "bg-green-50 text-green-700";
  } else if (margen >= objetivo - 5) {
    colorClass = "bg-yellow-50 text-yellow-700";
  } else {
    colorClass = "bg-red-50 text-red-700";
  }

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs ${colorClass}`}>
      {margen.toFixed(1)}%
    </span>
  );
}

export default function EscandallsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [recetas, setRecetas] = useState<RecetaListItem[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [categoriaFiltro, setCategoriaFiltro] = useState<number | null>(null);
  const [buscar, setBuscar] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<Categoria[]>("/api/categorias?tipo=receta")
      .then(setCategorias)
      .catch(() => toast("Error al cargar categorías", "error"));
  }, [toast]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (categoriaFiltro) params.set("categoria_id", String(categoriaFiltro));
    if (buscar) params.set("buscar", buscar);
    apiFetch<RecetaListItem[]>(`/api/recetas?${params}`)
      .then(setRecetas)
      .catch(() => toast("Error al cargar recetas", "error"))
      .finally(() => setLoading(false));
  }, [categoriaFiltro, buscar, toast]);

  const categoryMap = new Map(
    categorias.map((c) => [c.id, c.margen_objetivo ?? null])
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Escandallos
        </h1>
        <PermissionGate module="recetas" action="create">
          <Link
            href="/escandallos/nuevo"
            className="bg-brot text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] flex items-center hover:bg-brot-dark transition-colors"
          >
            + Nueva Receta
          </Link>
        </PermissionGate>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar receta..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
        />
      </div>

      {/* Category filter chips */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setCategoriaFiltro(null)}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            categoriaFiltro === null
              ? "bg-brot text-white"
              : "bg-white text-warm-gray border border-gray-200 hover:bg-cream"
          }`}
        >
          Todas
        </button>
        {categorias.map((c) => (
          <button
            key={c.id}
            onClick={() =>
              setCategoriaFiltro(c.id === categoriaFiltro ? null : c.id)
            }
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              categoriaFiltro === c.id
                ? "bg-brot text-white"
                : "bg-white text-warm-gray border border-gray-200 hover:bg-cream"
            }`}
          >
            {c.nombre}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray text-sm">
            Cargando...
          </div>
        ) : recetas.length === 0 ? (
          <div className="p-8 text-center text-warm-gray text-sm">
            No hay recetas registradas.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-warm-gray text-xs uppercase tracking-wide">
                  <th className="text-left px-4 py-3">Nombre</th>
                  <th className="text-left px-4 py-3 hidden sm:table-cell">
                    Categoría
                  </th>
                  <th className="text-right px-4 py-3">Costo/U</th>
                  <th className="text-right px-4 py-3 hidden md:table-cell">
                    PVP
                  </th>
                  <th className="text-right px-4 py-3">Margen</th>
                  <th className="text-right px-4 py-3 hidden md:table-cell">
                    Multi
                  </th>
                </tr>
              </thead>
              <tbody>
                {recetas.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => router.push(`/escandallos/${r.id}`)}
                    className="border-b border-gray-50 hover:bg-cream cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-text">{r.nombre}</div>
                      {r.es_subreceta && (
                        <span className="text-xs text-brot">subreceta</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-warm-gray hidden sm:table-cell">
                      {r.categoria_nombre}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm">
                      {formatARS(r.costo_por_porcion)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm hidden md:table-cell">
                      {r.precio_venta !== null
                        ? formatARS(r.precio_venta)
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <MargenBadge
                        margen={r.margen}
                        objetivo={categoryMap.get(r.categoria_id) ?? null}
                      />
                    </td>
                    <td className="px-4 py-3 text-right text-warm-gray hidden md:table-cell">
                      {r.multi !== null ? `${r.multi.toFixed(2)}×` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
