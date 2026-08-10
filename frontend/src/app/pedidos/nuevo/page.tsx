"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { useToast } from "@/components/Toast";

interface Proveedor {
  id: number;
  nombre: string;
}

interface IngredienteOpt {
  id: number;
  nombre: string;
  unidad_compra: string;
  precio_compra: number;
  cantidad_compra: number;
}

interface LineaLocal {
  key: number;
  ingrediente_id: number;
  nombre: string;
  cantidad: string;
  unidad: string;
  precio_unitario: string;
}

const UNIDADES_COMPRA = ["kg", "g", "l", "ml", "unidad", "bolsa", "caja", "sobre"];

let lineaKey = 0;

export default function NuevoPedidoPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [proveedorId, setProveedorId] = useState("");
  const [notas, setNotas] = useState("");
  const [lineas, setLineas] = useState<LineaLocal[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [ingredientes, setIngredientes] = useState<IngredienteOpt[]>([]);

  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorBuscar, setSelectorBuscar] = useState("");

  useEffect(() => {
    Promise.all([
      apiFetch<Proveedor[]>("/api/proveedores"),
      apiFetch<IngredienteOpt[]>("/api/ingredientes"),
    ])
      .then(([provs, ings]) => {
        setProveedores(provs);
        setIngredientes(ings);
      })
      .catch(() => toast("Error al cargar datos", "error"));
  }, [toast]);

  const ingFiltered = ingredientes.filter((i) =>
    i.nombre.toLowerCase().includes(selectorBuscar.toLowerCase())
  );

  const addIngrediente = (ing: IngredienteOpt) => {
    // Check if already added
    if (lineas.some((l) => l.ingrediente_id === ing.id)) {
      toast("Este ingrediente ya está en el pedido", "error");
      setSelectorOpen(false);
      setSelectorBuscar("");
      return;
    }
    setLineas((prev) => [
      ...prev,
      {
        key: lineaKey++,
        ingrediente_id: ing.id,
        nombre: ing.nombre,
        cantidad: String(ing.cantidad_compra || 1),
        unidad: ing.unidad_compra,
        precio_unitario: String(ing.precio_compra || ""),
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
    field: "cantidad" | "unidad" | "precio_unitario",
    value: string
  ) => {
    setLineas((prev) =>
      prev.map((l) => (l.key === key ? { ...l, [field]: value } : l))
    );
  };

  const totalEstimado = lineas.reduce((sum, l) => {
    const cant = parseFloat(l.cantidad) || 0;
    const precio = parseFloat(l.precio_unitario) || 0;
    return sum + cant * precio;
  }, 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proveedorId) {
      toast("Selecciona un proveedor", "error");
      return;
    }
    if (lineas.length === 0) {
      toast("Agrega al menos un ítem", "error");
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        proveedor_id: parseInt(proveedorId),
        notas: notas || null,
        lineas: lineas.map((l) => ({
          ingrediente_id: l.ingrediente_id,
          cantidad: parseFloat(l.cantidad) || 0,
          unidad: l.unidad,
          precio_unitario: parseFloat(l.precio_unitario) || null,
        })),
      };
      const pedido = await apiFetch<{ id: number }>("/api/pedidos", {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast("Pedido creado como borrador");
      router.push(`/pedidos/${pedido.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al crear el pedido";
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
          Nuevo Pedido
        </h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic info */}
        <div className="bg-white rounded-xl p-6 shadow-sm space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Información del pedido
          </h2>

          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Proveedor *
            </label>
            <select
              value={proveedorId}
              onChange={(e) => setProveedorId(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              required
            >
              <option value="">Seleccionar proveedor...</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Notas
            </label>
            <textarea
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              rows={2}
              placeholder="Instrucciones, observaciones..."
              className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
            />
          </div>
        </div>

        {/* Line items */}
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Ítems del pedido
            </h2>
            <button
              type="button"
              onClick={() => setSelectorOpen(true)}
              className="bg-brot text-white px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] flex items-center hover:bg-brot-dark transition-colors"
            >
              + Agregar ítem
            </button>
          </div>

          {lineas.length === 0 ? (
            <p className="text-warm-gray text-sm py-4 text-center">
              Sin ítems. Agrega al menos uno.
            </p>
          ) : (
            <div className="space-y-3">
              {/* Header labels */}
              <div className="hidden sm:grid grid-cols-[1fr_100px_100px_110px_44px] gap-2 text-xs font-medium text-warm-gray px-1">
                <span>Ingrediente</span>
                <span className="text-right">Cantidad</span>
                <span>Unidad</span>
                <span className="text-right">Precio unit.</span>
                <span />
              </div>
              {lineas.map((l) => (
                <div
                  key={l.key}
                  className="grid grid-cols-1 sm:grid-cols-[1fr_100px_100px_110px_44px] gap-2 items-center p-3 bg-cream rounded-lg"
                >
                  <div className="text-sm font-medium text-text truncate">
                    {l.nombre}
                  </div>
                  <input
                    type="number"
                    value={l.cantidad}
                    onChange={(e) =>
                      updateLinea(l.key, "cantidad", e.target.value)
                    }
                    min="0"
                    step="0.01"
                    placeholder="Cant."
                    className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 text-right"
                  />
                  <select
                    value={l.unidad}
                    onChange={(e) =>
                      updateLinea(l.key, "unidad", e.target.value)
                    }
                    className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                  >
                    {UNIDADES_COMPRA.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    value={l.precio_unitario}
                    onChange={(e) =>
                      updateLinea(l.key, "precio_unitario", e.target.value)
                    }
                    min="0"
                    step="0.01"
                    placeholder="Precio"
                    className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 text-right"
                  />
                  <button
                    type="button"
                    onClick={() => removeLinea(l.key)}
                    className="text-red-400 hover:text-red-600 p-1 min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
                    aria-label="Eliminar ítem"
                  >
                    &times;
                  </button>
                </div>
              ))}
            </div>
          )}

          {lineas.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
              <span className="text-sm text-warm-gray">Total estimado</span>
              <span className="font-medium text-brot">
                {formatARS(totalEstimado)}
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
            {submitting ? "Guardando..." : "Crear Pedido (Borrador)"}
          </button>
        </div>
      </form>

      {/* Ingredient selector modal */}
      {selectorOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col shadow-xl">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-medium text-text">Seleccionar ingrediente</h3>
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
                      {formatARS(i.precio_compra)}/{i.unidad_compra}
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
