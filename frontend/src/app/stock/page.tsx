"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";
import { Categoria } from "@/lib/types";

interface StockActual {
  ingrediente_id: number;
  ingrediente_nombre: string;
  categoria_id: number | null;
  categoria_nombre: string | null;
  cantidad: number;
  unidad: string;
  ubicacion: string | null;
  fecha_registro: string;
  nivel: "ok" | "bajo" | "sin_stock";
}

export default function StockPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [stock, setStock] = useState<StockActual[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [loading, setLoading] = useState(true);
  const [buscar, setBuscar] = useState("");
  const [categoriaId, setCategoriaId] = useState<number | null>(null);
  const [filtroNivel, setFiltroNivel] = useState<"todos" | "ok" | "bajo" | "sin_stock">("todos");

  useEffect(() => {
    Promise.all([
      apiFetch<StockActual[]>("/api/inventario/actual"),
      apiFetch<Categoria[]>("/api/categorias?tipo=ingrediente"),
    ])
      .then(([stockData, cats]) => {
        setStock(stockData);
        setCategorias(cats);
      })
      .catch(() => toast("Error al cargar el stock", "error"))
      .finally(() => setLoading(false));
  }, []);

  const filtrados = useMemo(() => {
    return stock.filter((item) => {
      const matchBuscar =
        buscar === "" ||
        item.ingrediente_nombre.toLowerCase().includes(buscar.toLowerCase());
      const matchCategoria =
        categoriaId === null || item.categoria_id === categoriaId;
      const matchNivel =
        filtroNivel === "todos" || item.nivel === filtroNivel;
      return matchBuscar && matchCategoria && matchNivel;
    });
  }, [stock, buscar, categoriaId, filtroNivel]);

  const nivelBadge = (nivel: StockActual["nivel"]) => {
    switch (nivel) {
      case "sin_stock":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
            Sin stock
          </span>
        );
      case "bajo":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
            Stock bajo
          </span>
        );
      case "ok":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
            OK
          </span>
        );
    }
  };

  const rowBg = (nivel: StockActual["nivel"]) => {
    switch (nivel) {
      case "sin_stock":
        return "bg-red-50";
      case "bajo":
        return "bg-amber-50";
      default:
        return "";
    }
  };

  const sinStock = stock.filter((s) => s.nivel === "sin_stock").length;
  const stockBajo = stock.filter((s) => s.nivel === "bajo").length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Stock
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/stock/alertas")}
            className="border border-amber-500 text-amber-700 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-amber-50 transition-colors min-h-[44px] whitespace-nowrap"
          >
            🔔 Alertas {sinStock + stockBajo > 0 && `(${sinStock + stockBajo})`}
          </button>
          <PermissionGate module="inventario" action="write">
            <button
              onClick={() => router.push("/stock/registro")}
              className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] whitespace-nowrap"
            >
              + Registrar Stock
            </button>
          </PermissionGate>
        </div>
      </div>

      {/* Summary cards */}
      {!loading && (sinStock > 0 || stockBajo > 0) && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
          {sinStock > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-2xl font-bold text-red-700">{sinStock}</p>
              <p className="text-sm text-red-600 mt-0.5">Sin stock</p>
            </div>
          )}
          {stockBajo > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-2xl font-bold text-amber-700">{stockBajo}</p>
              <p className="text-sm text-amber-600 mt-0.5">Stock bajo</p>
            </div>
          )}
          <div className="bg-green-50 border border-green-200 rounded-xl p-4">
            <p className="text-2xl font-bold text-green-700">
              {stock.filter((s) => s.nivel === "ok").length}
            </p>
            <p className="text-sm text-green-600 mt-0.5">Con stock</p>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar ingrediente..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="w-full px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
      </div>

      {/* Filters */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide flex-wrap">
        {/* Level filter */}
        {(["todos", "sin_stock", "bajo", "ok"] as const).map((nivel) => {
          const labels: Record<string, string> = {
            todos: "Todos",
            sin_stock: "Sin stock",
            bajo: "Stock bajo",
            ok: "OK",
          };
          return (
            <button
              key={nivel}
              onClick={() => setFiltroNivel(nivel)}
              className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
                filtroNivel === nivel
                  ? "bg-brot text-white"
                  : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
              }`}
            >
              {labels[nivel]}
            </button>
          );
        })}
      </div>

      {/* Category chips */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        <button
          onClick={() => setCategoriaId(null)}
          className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
            categoriaId === null
              ? "bg-brot text-white"
              : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
          }`}
        >
          Todas las categorías
        </button>
        {categorias.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setCategoriaId(cat.id === categoriaId ? null : cat.id)}
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

      {/* Table */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : filtrados.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No se encontraron resultados.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Ingrediente
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Categoría
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Cantidad
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Ubicación
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Estado
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Último registro
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((item, idx) => (
                    <tr
                      key={item.ingrediente_id}
                      className={`${rowBg(item.nivel)} ${
                        idx < filtrados.length - 1
                          ? "border-b border-cream-dark"
                          : ""
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-text">
                        {item.ingrediente_nombre}
                      </td>
                      <td className="px-4 py-3 text-warm-gray">
                        {item.categoria_nombre ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-text font-medium">
                        {item.cantidad}{" "}
                        <span className="text-warm-gray text-xs font-normal">
                          {item.unidad}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-warm-gray">
                        {item.ubicacion ?? "—"}
                      </td>
                      <td className="px-4 py-3">{nivelBadge(item.nivel)}</td>
                      <td className="px-4 py-3 text-warm-gray text-xs">
                        {item.fecha_registro
                          ? new Date(item.fecha_registro).toLocaleDateString(
                              "es-AR",
                              { day: "2-digit", month: "2-digit", year: "numeric" }
                            )
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {filtrados.map((item) => (
                <div
                  key={item.ingrediente_id}
                  className={`px-4 py-4 ${rowBg(item.nivel)}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-text">
                        {item.ingrediente_nombre}
                      </p>
                      <p className="text-xs text-warm-gray mt-0.5">
                        {item.categoria_nombre ?? "Sin categoría"}
                        {item.ubicacion ? ` · ${item.ubicacion}` : ""}
                      </p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-bold text-text">
                        {item.cantidad}{" "}
                        <span className="font-normal text-warm-gray">
                          {item.unidad}
                        </span>
                      </p>
                      <div className="mt-1">{nivelBadge(item.nivel)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {filtrados.length} ingrediente{filtrados.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
