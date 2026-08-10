"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS } from "@/lib/format";
import { Categoria } from "@/lib/types";

interface Ingrediente {
  id: number;
  nombre: string;
  categoria_id: number;
  categoria_nombre: string;
  unidad_compra: string;
  cantidad_compra: number;
  precio_compra: number;
  unidad_uso: string;
  merma_porcentaje: number;
  proveedor: string | null;
  notas: string | null;
  activo: boolean;
  costo_por_unidad_uso: number;
  fecha_actualizacion: string;
}

export default function IngredientesPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [ingredientes, setIngredientes] = useState<Ingrediente[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [loading, setLoading] = useState(true);
  const [buscar, setBuscar] = useState("");
  const [categoriaId, setCategoriaId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<Ingrediente[]>("/api/ingredientes"),
      apiFetch<Categoria[]>("/api/categorias?tipo=ingrediente"),
    ])
      .then(([ings, cats]) => {
        setIngredientes(ings);
        setCategorias(cats);
      })
      .catch(() => toast("Error al cargar ingredientes", "error"))
      .finally(() => setLoading(false));
  }, []);

  const filtrados = useMemo(() => {
    return ingredientes.filter((ing) => {
      const matchBuscar =
        buscar === "" ||
        ing.nombre.toLowerCase().includes(buscar.toLowerCase()) ||
        (ing.proveedor ?? "").toLowerCase().includes(buscar.toLowerCase());
      const matchCategoria =
        categoriaId === null || ing.categoria_id === categoriaId;
      return matchBuscar && matchCategoria;
    });
  }, [ingredientes, buscar, categoriaId]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Ingredientes
        </h1>
        <button
          onClick={() => router.push("/ingredientes/nuevo")}
          className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] whitespace-nowrap"
        >
          + Nuevo Ingrediente
        </button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar por nombre o proveedor..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="w-full px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
      </div>

      {/* Category filter chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        <button
          onClick={() => setCategoriaId(null)}
          className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
            categoriaId === null
              ? "bg-brot text-white"
              : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
          }`}
        >
          Todas
        </button>
        {categorias.map((cat) => (
          <button
            key={cat.id}
            onClick={() =>
              setCategoriaId(cat.id === categoriaId ? null : cat.id)
            }
            className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
              categoriaId === cat.id
                ? "bg-brot text-white"
                : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
            }`}
          >
            {cat.nombre}
          </button>
        ))}
      </div>

      {/* Table card */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : filtrados.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No se encontraron ingredientes.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Nombre
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Categoría
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Precio Compra
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Costo/Unidad Uso
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Proveedor
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((ing, idx) => (
                    <tr
                      key={ing.id}
                      onClick={() => router.push(`/ingredientes/${ing.id}`)}
                      className={`cursor-pointer hover:bg-cream/40 transition-colors ${
                        idx < filtrados.length - 1
                          ? "border-b border-cream-dark"
                          : ""
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-text">
                        {ing.nombre}
                        {!ing.activo && (
                          <span className="ml-2 text-xs text-warm-gray bg-cream px-1.5 py-0.5 rounded">
                            Inactivo
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-warm-gray">
                        {ing.categoria_nombre}
                      </td>
                      <td className="px-4 py-3 text-right text-text">
                        {formatARS(ing.precio_compra)}{" "}
                        <span className="text-warm-gray text-xs">
                          /{ing.cantidad_compra} {ing.unidad_compra}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-brot">
                        {formatARS(ing.costo_por_unidad_uso)}{" "}
                        <span className="text-warm-gray text-xs font-normal">
                          /{ing.unidad_uso}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-warm-gray">
                        {ing.proveedor ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {filtrados.map((ing) => (
                <button
                  key={ing.id}
                  onClick={() => router.push(`/ingredientes/${ing.id}`)}
                  className="w-full text-left px-4 py-4 hover:bg-cream/40 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-text">{ing.nombre}</p>
                      <p className="text-xs text-warm-gray mt-0.5">
                        {ing.categoria_nombre}
                        {ing.proveedor ? ` · ${ing.proveedor}` : ""}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-medium text-brot">
                        {formatARS(ing.costo_por_unidad_uso)}/{ing.unidad_uso}
                      </p>
                      <p className="text-xs text-warm-gray mt-0.5">
                        {formatARS(ing.precio_compra)}/{ing.cantidad_compra}{" "}
                        {ing.unidad_compra}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Count */}
      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {filtrados.length} ingrediente{filtrados.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
