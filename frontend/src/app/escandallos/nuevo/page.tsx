"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { Categoria } from "@/lib/types";
import { useToast } from "@/components/Toast";

interface IngredienteOpt {
  id: number;
  nombre: string;
  unidad_uso: string;
  costo_por_unidad_uso: number;
}

interface LineaLocal {
  key: number;
  ingrediente_id: number;
  nombre: string;
  cantidad: string;
  unidad: string;
  costo_por_unidad_uso: number;
}

const UNIDADES = [
  "g",
  "kg",
  "ml",
  "l",
  "unidad",
  "taza",
  "cdta",
  "cda",
  "sobre",
];

let lineaKey = 0;

export default function NuevaRecetaPage() {
  const router = useRouter();
  const { toast } = useToast();

  // Form state
  const [nombre, setNombre] = useState("");
  const [categoriaId, setCategoriaId] = useState("");
  const [porciones, setPorciones] = useState("1");
  const [precioVenta, setPrecioVenta] = useState("");
  const [esSubreceta, setEsSubreceta] = useState(false);
  const [unidadRendimiento, setUnidadRendimiento] = useState("");
  const [notas, setNotas] = useState("");
  const [lineas, setLineas] = useState<LineaLocal[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Data
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [ingredientes, setIngredientes] = useState<IngredienteOpt[]>([]);

  // Ingredient selector state
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorBuscar, setSelectorBuscar] = useState("");

  useEffect(() => {
    apiFetch<Categoria[]>("/api/categorias?tipo=receta").then(setCategorias);
    apiFetch<IngredienteOpt[]>("/api/ingredientes").then(setIngredientes);
  }, []);

  const ingFiltered = ingredientes.filter((i) =>
    i.nombre.toLowerCase().includes(selectorBuscar.toLowerCase())
  );

  const addIngrediente = (ing: IngredienteOpt) => {
    setLineas((prev) => [
      ...prev,
      {
        key: lineaKey++,
        ingrediente_id: ing.id,
        nombre: ing.nombre,
        cantidad: "100",
        unidad: ing.unidad_uso,
        costo_por_unidad_uso: ing.costo_por_unidad_uso,
      },
    ]);
    setSelectorOpen(false);
    setSelectorBuscar("");
  };

  const removeLinea = (key: number) => {
    setLineas((prev) => prev.filter((l) => l.key !== key));
  };

  const updateLinea = (
    key: number,
    field: "cantidad" | "unidad",
    value: string
  ) => {
    setLineas((prev) =>
      prev.map((l) => (l.key === key ? { ...l, [field]: value } : l))
    );
  };

  const costoTotal = lineas.reduce((sum, l) => {
    const cant = parseFloat(l.cantidad) || 0;
    return sum + cant * l.costo_por_unidad_uso;
  }, 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nombre.trim() || !categoriaId) {
      toast("Nombre y categoría son obligatorios", "error");
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        nombre: nombre.trim(),
        categoria_id: parseInt(categoriaId),
        porciones_por_lote: parseFloat(porciones) || 1,
        precio_venta: precioVenta ? parseFloat(precioVenta) : null,
        es_subreceta: esSubreceta,
        unidad_rendimiento: esSubreceta ? unidadRendimiento || null : null,
        notas: notas || null,
        lineas: lineas.map((l) => ({
          ingrediente_id: l.ingrediente_id,
          subreceta_id: null,
          cantidad: parseFloat(l.cantidad) || 0,
          unidad: l.unidad,
        })),
      };
      const receta = await apiFetch<{ id: number }>("/api/recetas", {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast("Receta creada correctamente");
      router.push(`/escandallos/${receta.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al crear la receta";
      toast(msg, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.back()}
          className="text-warm-gray hover:text-brot transition-colors min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Nueva Receta
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic info card */}
        <div className="bg-white rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Información básica
          </h2>

          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Nombre *
            </label>
            <input
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej: Pan de masa madre 400g"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              required
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Categoría *
              </label>
              <select
                value={categoriaId}
                onChange={(e) => setCategoriaId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                required
              >
                <option value="">Seleccionar...</option>
                {categorias.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Porciones por lote
              </label>
              <input
                type="number"
                value={porciones}
                onChange={(e) => setPorciones(e.target.value)}
                min="0.01"
                step="0.01"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Precio de venta (ARS)
              </label>
              <input
                type="number"
                value={precioVenta}
                onChange={(e) => setPrecioVenta(e.target.value)}
                min="0"
                step="0.01"
                placeholder="Opcional"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            <div className="flex items-center gap-3 pt-7">
              <input
                type="checkbox"
                id="esSubreceta"
                checked={esSubreceta}
                onChange={(e) => setEsSubreceta(e.target.checked)}
                className="w-5 h-5 accent-brot"
              />
              <label
                htmlFor="esSubreceta"
                className="text-sm font-medium text-text"
              >
                Es subreceta
              </label>
            </div>
          </div>

          {esSubreceta && (
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Unidad de rendimiento
              </label>
              <input
                type="text"
                value={unidadRendimiento}
                onChange={(e) => setUnidadRendimiento(e.target.value)}
                placeholder="Ej: g, ml, unidad..."
                className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Notas
            </label>
            <textarea
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              rows={3}
              placeholder="Observaciones, instrucciones especiales..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
            />
          </div>
        </div>

        {/* Line items */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Ingredientes
            </h2>
            <button
              type="button"
              onClick={() => setSelectorOpen(true)}
              className="bg-brot text-white px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] flex items-center hover:bg-brot-dark transition-colors"
            >
              + Agregar ingrediente
            </button>
          </div>

          {lineas.length === 0 ? (
            <p className="text-warm-gray text-sm py-4 text-center">
              Sin ingredientes. Agrega al menos uno.
            </p>
          ) : (
            <div className="space-y-3">
              {lineas.map((l) => (
                <div
                  key={l.key}
                  className="flex items-center gap-3 p-3 bg-cream rounded-lg"
                >
                  <div className="flex-1 text-sm font-medium text-text min-w-0">
                    <span className="truncate block">{l.nombre}</span>
                  </div>
                  <input
                    type="number"
                    value={l.cantidad}
                    onChange={(e) =>
                      updateLinea(l.key, "cantidad", e.target.value)
                    }
                    min="0"
                    step="0.01"
                    className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                  />
                  <select
                    value={l.unidad}
                    onChange={(e) =>
                      updateLinea(l.key, "unidad", e.target.value)
                    }
                    className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                  >
                    {UNIDADES.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => removeLinea(l.key)}
                    className="text-red-400 hover:text-red-600 p-1 min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
                    aria-label="Eliminar ingrediente"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Running cost */}
          {lineas.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
              <span className="text-sm text-warm-gray">
                Costo estimado total
              </span>
              <span className="font-medium text-brot">
                {formatARS(costoTotal)}
              </span>
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex gap-3 justify-end pb-4">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="bg-brot text-white px-6 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
          >
            {submitting ? "Guardando..." : "Crear Receta"}
          </button>
        </div>
      </form>

      {/* Ingredient selector modal */}
      {selectorOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col shadow-xl">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-medium text-text">
                Seleccionar ingrediente
              </h3>
              <button
                onClick={() => {
                  setSelectorOpen(false);
                  setSelectorBuscar("");
                }}
                className="text-warm-gray hover:text-text min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
                aria-label="Cerrar"
              >
                &times;
              </button>
            </div>
            <div className="p-3 border-b border-gray-100">
              <input
                type="search"
                placeholder="Buscar ingrediente..."
                value={selectorBuscar}
                onChange={(e) => setSelectorBuscar(e.target.value)}
                autoFocus
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="flex-1 overflow-y-auto">
              {ingFiltered.length === 0 ? (
                <p className="p-4 text-center text-warm-gray text-sm">
                  No se encontraron ingredientes.
                </p>
              ) : (
                ingFiltered.map((i) => (
                  <button
                    key={i.id}
                    onClick={() => addIngrediente(i)}
                    className="w-full text-left px-4 py-3 hover:bg-cream transition-colors flex items-center justify-between border-b border-gray-50 min-h-[44px]"
                  >
                    <span className="text-sm font-medium text-text">
                      {i.nombre}
                    </span>
                    <span className="text-xs text-warm-gray">
                      {formatARS(i.costo_por_unidad_uso)}/{i.unidad_uso}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
