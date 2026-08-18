"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { useLineasReceta } from "@/lib/useLineasReceta";
import { useRecetaFormOptions } from "@/lib/useRecetaFormOptions";
import { IngredientOrSubrecetaPicker } from "@/components/IngredientOrSubrecetaPicker";
import { RecetaInfoFields } from "@/components/RecetaInfoFields";
import { RecetaLineasEditor } from "@/components/RecetaLineasEditor";

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
  const [submitting, setSubmitting] = useState(false);

  const { lineas, addItem, removeLinea, updateLinea, costoTotal, toApiPayload } = useLineasReceta();
  const { categorias, ingredientesOpts, subrecetasOpts } = useRecetaFormOptions();

  // Picker state
  const [selectorOpen, setSelectorOpen] = useState(false);

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
        lineas: toApiPayload(),
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
        <RecetaInfoFields
          nombre={nombre}
          onNombreChange={setNombre}
          categoriaId={categoriaId}
          onCategoriaIdChange={setCategoriaId}
          categorias={categorias}
          porciones={porciones}
          onPorcionesChange={setPorciones}
          precioVenta={precioVenta}
          onPrecioVentaChange={setPrecioVenta}
          esSubreceta={esSubreceta}
          onEsSubrecetaChange={setEsSubreceta}
          unidadRendimiento={unidadRendimiento}
          onUnidadRendimientoChange={setUnidadRendimiento}
          notas={notas}
          onNotasChange={setNotas}
        />

        <RecetaLineasEditor
          lineas={lineas}
          onAdd={() => setSelectorOpen(true)}
          onRemove={removeLinea}
          onChange={updateLinea}
          costoTotal={costoTotal}
        />

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

      <IngredientOrSubrecetaPicker
        open={selectorOpen}
        onClose={() => setSelectorOpen(false)}
        onSelect={addItem}
        ingredientes={ingredientesOpts}
        subrecetas={subrecetasOpts}
      />
    </div>
  );
}
