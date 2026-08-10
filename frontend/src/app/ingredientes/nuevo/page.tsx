"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { Categoria } from "@/lib/types";

const UNIDADES_COMPRA = ["kg", "g", "litro", "ml", "unidad"];
const UNIDADES_USO = ["kg", "g", "litro", "ml", "unidad"];

interface FormData {
  nombre: string;
  categoria_id: string;
  unidad_compra: string;
  cantidad_compra: string;
  precio_compra: string;
  unidad_uso: string;
  merma_porcentaje: string;
  proveedor: string;
  notas: string;
}

const EMPTY_FORM: FormData = {
  nombre: "",
  categoria_id: "",
  unidad_compra: "kg",
  cantidad_compra: "",
  precio_compra: "",
  unidad_uso: "g",
  merma_porcentaje: "0",
  proveedor: "",
  notas: "",
};

export default function NuevoIngredientePage() {
  const router = useRouter();
  const { toast } = useToast();

  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>(
    {}
  );

  useEffect(() => {
    apiFetch<Categoria[]>("/api/categorias?tipo=ingrediente")
      .then(setCategorias)
      .catch(() => toast("Error al cargar categorías", "error"));
  }, []);

  function setField(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  function validate(): boolean {
    const newErrors: Partial<Record<keyof FormData, string>> = {};
    if (!form.nombre.trim()) newErrors.nombre = "El nombre es obligatorio";
    if (!form.categoria_id) newErrors.categoria_id = "Seleccione una categoría";
    if (!form.cantidad_compra || Number(form.cantidad_compra) <= 0)
      newErrors.cantidad_compra = "Debe ser mayor a 0";
    if (!form.precio_compra || Number(form.precio_compra) < 0)
      newErrors.precio_compra = "Debe ser 0 o mayor";
    if (
      form.merma_porcentaje !== "" &&
      (Number(form.merma_porcentaje) < 0 ||
        Number(form.merma_porcentaje) > 100)
    )
      newErrors.merma_porcentaje = "Entre 0 y 100";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      await apiFetch("/api/ingredientes", {
        method: "POST",
        body: JSON.stringify({
          nombre: form.nombre.trim(),
          categoria_id: Number(form.categoria_id),
          unidad_compra: form.unidad_compra,
          cantidad_compra: Number(form.cantidad_compra),
          precio_compra: Number(form.precio_compra),
          unidad_uso: form.unidad_uso,
          merma_porcentaje: Number(form.merma_porcentaje) || 0,
          proveedor: form.proveedor.trim() || null,
          notas: form.notas.trim() || null,
        }),
      });
      toast("Ingrediente creado correctamente");
      router.push("/ingredientes");
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al crear ingrediente",
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
          onClick={() => router.push("/ingredientes")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Nuevo Ingrediente
        </h1>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {/* Basic info card */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
          <h2 className="font-medium text-text text-sm uppercase tracking-wide text-warm-gray">
            Información básica
          </h2>

          {/* Nombre */}
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Nombre <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.nombre}
              onChange={(e) => setField("nombre", e.target.value)}
              placeholder="Ej. Harina de trigo"
              className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                errors.nombre ? "border-red-400" : "border-cream-dark"
              }`}
            />
            {errors.nombre && (
              <p className="text-xs text-red-500 mt-1">{errors.nombre}</p>
            )}
          </div>

          {/* Categoría */}
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Categoría <span className="text-red-500">*</span>
            </label>
            <select
              value={form.categoria_id}
              onChange={(e) => setField("categoria_id", e.target.value)}
              className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                errors.categoria_id ? "border-red-400" : "border-cream-dark"
              }`}
            >
              <option value="">Seleccionar categoría...</option>
              {categorias.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.nombre}
                </option>
              ))}
            </select>
            {errors.categoria_id && (
              <p className="text-xs text-red-500 mt-1">{errors.categoria_id}</p>
            )}
          </div>

          {/* Proveedor */}
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Proveedor
            </label>
            <input
              type="text"
              value={form.proveedor}
              onChange={(e) => setField("proveedor", e.target.value)}
              placeholder="Nombre del proveedor"
              className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            />
          </div>
        </div>

        {/* Purchase info card */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Datos de compra
          </h2>

          <div className="grid grid-cols-2 gap-4">
            {/* Cantidad compra */}
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Cantidad <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={form.cantidad_compra}
                onChange={(e) => setField("cantidad_compra", e.target.value)}
                placeholder="1"
                className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                  errors.cantidad_compra ? "border-red-400" : "border-cream-dark"
                }`}
              />
              {errors.cantidad_compra && (
                <p className="text-xs text-red-500 mt-1">
                  {errors.cantidad_compra}
                </p>
              )}
            </div>

            {/* Unidad compra */}
            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Unidad de compra
              </label>
              <select
                value={form.unidad_compra}
                onChange={(e) => setField("unidad_compra", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              >
                {UNIDADES_COMPRA.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Precio compra */}
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Precio de compra (ARS) <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={form.precio_compra}
              onChange={(e) => setField("precio_compra", e.target.value)}
              placeholder="0.00"
              className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                errors.precio_compra ? "border-red-400" : "border-cream-dark"
              }`}
            />
            {errors.precio_compra && (
              <p className="text-xs text-red-500 mt-1">{errors.precio_compra}</p>
            )}
          </div>
        </div>

        {/* Usage info card */}
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Datos de uso
          </h2>

          {/* Unidad uso */}
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Unidad de uso
            </label>
            <select
              value={form.unidad_uso}
              onChange={(e) => setField("unidad_uso", e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            >
              {UNIDADES_USO.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>

          {/* Merma */}
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Merma (%)
            </label>
            <input
              type="text"
              inputMode="decimal"
              value={form.merma_porcentaje}
              onChange={(e) => setField("merma_porcentaje", e.target.value)}
              placeholder="0"
              className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                errors.merma_porcentaje ? "border-red-400" : "border-cream-dark"
              }`}
            />
            {errors.merma_porcentaje && (
              <p className="text-xs text-red-500 mt-1">
                {errors.merma_porcentaje}
              </p>
            )}
            <p className="text-xs text-warm-gray mt-1">
              Porcentaje de pérdida en la preparación (0-100)
            </p>
          </div>
        </div>

        {/* Notes card */}
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
            onClick={() => router.push("/ingredientes")}
            className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Guardando..." : "Crear Ingrediente"}
          </button>
        </div>
      </form>
    </div>
  );
}
