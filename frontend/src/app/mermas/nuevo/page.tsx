"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS } from "@/lib/format";

type Motivo = "caducado" | "dañado" | "produccion" | "otro";

interface Ingrediente {
  id: number;
  nombre: string;
  unidad_uso: string;
  costo_por_unidad_uso: number;
}

interface Receta {
  id: number;
  nombre: string;
  costo_por_porcion: number;
  precio_venta: number | null;
}

const MOTIVOS: { value: Motivo; label: string }[] = [
  { value: "caducado", label: "Caducado" },
  { value: "dañado", label: "Dañado" },
  { value: "produccion", label: "Merma de produccion" },
  { value: "otro", label: "Otro" },
];

const UNIDADES = ["g", "kg", "ml", "litro", "unidad"];

interface FormData {
  modo: "ingrediente" | "producto" | "libre";
  ingrediente_id: string;
  receta_id: string;
  nombre_libre: string;
  cantidad: string;
  unidad: string;
  motivo: Motivo;
  notas: string;
}

const EMPTY_FORM: FormData = {
  modo: "producto",
  ingrediente_id: "",
  receta_id: "",
  nombre_libre: "",
  cantidad: "",
  unidad: "unidad",
  motivo: "caducado",
  notas: "",
};

export default function NuevaMermaPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [ingredientes, setIngredientes] = useState<Ingrediente[]>([]);
  const [recetas, setRecetas] = useState<Receta[]>([]);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});

  useEffect(() => {
    Promise.all([
      apiFetch<Ingrediente[]>("/api/ingredientes"),
      apiFetch<Record<string, unknown>[]>("/api/recetas"),
    ])
      .then(([ings, recs]) => {
        setIngredientes(ings);
        setRecetas(recs.filter((r) => !(r.es_subreceta as boolean)).map((r) => ({
          id: r.id as number,
          nombre: r.nombre as string,
          costo_por_porcion: r.costo_por_porcion as number,
          precio_venta: r.precio_venta as number | null,
        })));
      })
      .catch(() => toast("Error al cargar datos", "error"));
  }, []);

  function setField<K extends keyof FormData>(field: K, value: FormData[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  const selectedIngredient = ingredientes.find(
    (i) => String(i.id) === form.ingrediente_id
  );
  const selectedReceta = recetas.find(
    (r) => String(r.id) === form.receta_id
  );

  const costPreview = (() => {
    const qty = Number(form.cantidad);
    if (!qty || qty <= 0) return null;
    if (form.modo === "ingrediente" && selectedIngredient) {
      return selectedIngredient.costo_por_unidad_uso * qty;
    }
    if (form.modo === "producto" && selectedReceta) {
      return selectedReceta.costo_por_porcion * qty;
    }
    return null;
  })();

  function validate(): boolean {
    const errs: Partial<Record<string, string>> = {};
    if (form.modo === "ingrediente" && !form.ingrediente_id) {
      errs.ingrediente_id = "Seleccione un ingrediente";
    }
    if (form.modo === "producto" && !form.receta_id) {
      errs.receta_id = "Seleccione un producto";
    }
    if (form.modo === "libre" && !form.nombre_libre.trim()) {
      errs.nombre_libre = "Ingrese el nombre del item";
    }
    if (!form.cantidad || Number(form.cantidad) <= 0) {
      errs.cantidad = "Debe ser mayor a 0";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      const cantidad = Number(form.cantidad);
      let unidad = form.unidad;
      let costeUnitario = 0;
      if (form.modo === "ingrediente" && selectedIngredient) {
        unidad = selectedIngredient.unidad_uso;
        costeUnitario = selectedIngredient.costo_por_unidad_uso;
      } else if (form.modo === "producto" && selectedReceta) {
        unidad = "unidad";
        costeUnitario = selectedReceta.costo_por_porcion;
      }
      const body: Record<string, unknown> = {
        cantidad,
        unidad,
        motivo: form.motivo,
        notas: form.notas.trim() || null,
        fecha: new Date().toISOString().slice(0, 10),
        coste_unitario: costeUnitario,
        coste_total: costeUnitario * cantidad,
      };
      if (form.modo === "ingrediente") {
        body.ingrediente_id = Number(form.ingrediente_id);
      } else if (form.modo === "producto") {
        body.receta_id = Number(form.receta_id);
      } else {
        body.nombre_libre = form.nombre_libre.trim();
      }
      await apiFetch("/api/mermas", {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast("Merma registrada correctamente");
      router.push("/mermas");
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al registrar merma",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/mermas")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Registrar Merma
        </h1>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {/* Item source toggle */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Ítem
          </h2>

          {/* Mode toggle */}
          <div className="flex rounded-lg border border-cream-dark overflow-hidden">
            <button
              type="button"
              onClick={() => setField("modo", "producto")}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                form.modo === "producto"
                  ? "bg-brot text-white"
                  : "bg-white text-warm-gray hover:bg-cream"
              }`}
            >
              Producto
            </button>
            <button
              type="button"
              onClick={() => setField("modo", "ingrediente")}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                form.modo === "ingrediente"
                  ? "bg-brot text-white"
                  : "bg-white text-warm-gray hover:bg-cream"
              }`}
            >
              Ingrediente
            </button>
            <button
              type="button"
              onClick={() => setField("modo", "libre")}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                form.modo === "libre"
                  ? "bg-brot text-white"
                  : "bg-white text-warm-gray hover:bg-cream"
              }`}
            >
              Otro
            </button>
          </div>

          {/* Product dropdown */}
          {form.modo === "producto" && (
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Producto
              </label>
              <select
                value={form.receta_id}
                onChange={(e) => setField("receta_id", e.target.value)}
                className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                  errors.receta_id ? "border-red-400" : "border-cream-dark"
                }`}
              >
                <option value="">Seleccionar producto...</option>
                {recetas.map((r) => (
                  <option key={r.id} value={r.id}>{r.nombre}</option>
                ))}
              </select>
              {errors.receta_id && (
                <p className="text-xs text-red-500 mt-1">{errors.receta_id}</p>
              )}
              {selectedReceta && (
                <p className="text-xs text-warm-gray mt-1">
                  Costo: {formatARS(selectedReceta.costo_por_porcion)}/unidad
                </p>
              )}
            </div>
          )}

          {/* Ingredient dropdown */}
          {form.modo === "ingrediente" && (
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Ingrediente <span className="text-red-500">*</span>
              </label>
              <select
                value={form.ingrediente_id}
                onChange={(e) => setField("ingrediente_id", e.target.value)}
                className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                  errors.ingrediente_id ? "border-red-400" : "border-cream-dark"
                }`}
              >
                <option value="">Seleccionar ingrediente...</option>
                {ingredientes.map((ing) => (
                  <option key={ing.id} value={ing.id}>
                    {ing.nombre}
                  </option>
                ))}
              </select>
              {errors.ingrediente_id && (
                <p className="text-xs text-red-500 mt-1">
                  {errors.ingrediente_id}
                </p>
              )}
              {selectedIngredient && (
                <p className="text-xs text-warm-gray mt-1">
                  Unidad: {selectedIngredient.unidad_uso} · Costo:{" "}
                  {formatARS(selectedIngredient.costo_por_unidad_uso)}/
                  {selectedIngredient.unidad_uso}
                </p>
              )}
            </div>
          )}

          {/* Free text name */}
          {form.modo === "libre" && (
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Nombre del ítem <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={form.nombre_libre}
                onChange={(e) => setField("nombre_libre", e.target.value)}
                placeholder="Ej. Pan artesanal, Brioche..."
                className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                  errors.nombre_libre ? "border-red-400" : "border-cream-dark"
                }`}
              />
              {errors.nombre_libre && (
                <p className="text-xs text-red-500 mt-1">{errors.nombre_libre}</p>
              )}
            </div>
          )}
        </div>

        {/* Quantity & unit */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Cantidad
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Cantidad <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={form.cantidad}
                onChange={(e) => setField("cantidad", e.target.value)}
                placeholder="0"
                className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                  errors.cantidad ? "border-red-400" : "border-cream-dark"
                }`}
              />
              {errors.cantidad && (
                <p className="text-xs text-red-500 mt-1">{errors.cantidad}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Unidad
              </label>
              {form.modo === "ingrediente" && selectedIngredient ? (
                <div className="px-3 py-2.5 rounded-lg border border-cream-dark bg-cream text-warm-gray text-sm min-h-[44px] flex items-center">
                  {selectedIngredient.unidad_uso}
                </div>
              ) : (
                <select
                  value={form.unidad}
                  onChange={(e) => setField("unidad", e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
                >
                  {UNIDADES.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          {/* Cost preview */}
          {costPreview != null && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              <p className="text-sm text-red-700">
                Coste estimado:{" "}
                <span className="font-semibold">{formatARS(costPreview)}</span>
              </p>
            </div>
          )}
        </div>

        {/* Motivo */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Motivo
          </h2>

          <div className="grid grid-cols-2 gap-2">
            {MOTIVOS.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => setField("motivo", value)}
                className={`py-2.5 px-3 rounded-lg border text-sm font-medium transition-colors min-h-[44px] ${
                  form.motivo === value
                    ? "bg-brot border-brot text-white"
                    : "bg-white border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6 space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Notas
          </h2>
          <textarea
            value={form.notas}
            onChange={(e) => setField("notas", e.target.value)}
            placeholder="Observaciones adicionales..."
            rows={3}
            className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => router.push("/mermas")}
            className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Guardando..." : "Registrar Merma"}
          </button>
        </div>
      </form>
    </div>
  );
}
