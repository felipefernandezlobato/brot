"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS } from "@/lib/format";
import { IngredientOrSubrecetaPicker, PickerOption } from "@/components/IngredientOrSubrecetaPicker";

export type Motivo = "caducado" | "dañado" | "produccion" | "otro";

interface Ingrediente {
  id: number;
  nombre: string;
  unidad_uso: string;
  costo_por_unidad_uso: number;
}

interface ProductoCongelado {
  id: number;
  nombre: string;
  categoria: string;
  unidad: string;
  costo_unitario: number;
}

const MOTIVOS: { value: Motivo; label: string }[] = [
  { value: "caducado", label: "Caducado" },
  { value: "dañado", label: "Dañado" },
  { value: "produccion", label: "Merma de produccion" },
  { value: "otro", label: "Otro" },
];

const UNIDADES = ["g", "kg", "ml", "litro", "unidad"];

export interface MermaFormData {
  modo: "ingrediente" | "producto" | "libre";
  ingrediente_id: string;
  producto_congelado_id: string;
  nombre_libre: string;
  cantidad: string;
  unidad: string;
  motivo: Motivo;
  notas: string;
  fecha: string;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export const EMPTY_MERMA_FORM: MermaFormData = {
  modo: "producto",
  ingrediente_id: "",
  producto_congelado_id: "",
  nombre_libre: "",
  cantidad: "",
  unidad: "unidad",
  motivo: "caducado",
  notas: "",
  fecha: today(),
};

interface MermaFormProps {
  initialValues?: MermaFormData;
  submitLabel: string;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
}

export default function MermaForm({
  initialValues,
  submitLabel,
  onCancel,
  onSubmit,
}: MermaFormProps) {
  const { toast } = useToast();
  const isEdit = Boolean(initialValues);

  const [ingredientes, setIngredientes] = useState<Ingrediente[]>([]);
  const [productos, setProductos] = useState<ProductoCongelado[]>([]);
  const [form, setForm] = useState<MermaFormData>(initialValues ?? EMPTY_MERMA_FORM);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch<Ingrediente[]>("/api/ingredientes"),
      apiFetch<ProductoCongelado[]>("/api/congelados/productos"),
    ])
      .then(([ings, prods]) => {
        setIngredientes(ings);
        setProductos(prods);
      })
      .catch(() => toast("Error al cargar datos", "error"));
  }, []);

  function setField<K extends keyof MermaFormData>(field: K, value: MermaFormData[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  const selectedIngredient = ingredientes.find(
    (i) => String(i.id) === form.ingrediente_id
  );
  const selectedProducto = productos.find(
    (p) => String(p.id) === form.producto_congelado_id
  );

  const ingredientesOpts: PickerOption[] = ingredientes.map((i) => ({
    id: i.id,
    nombre: i.nombre,
    unidad: i.unidad_uso,
    costoPorUnidad: i.costo_por_unidad_uso,
  }));
  const productosOpts: PickerOption[] = productos.map((p) => ({
    id: p.id,
    nombre: p.nombre,
    unidad: p.unidad,
    costoPorUnidad: p.costo_unitario,
  }));

  const costPreview = (() => {
    const qty = Number(form.cantidad);
    if (!qty || qty <= 0) return null;
    if (form.modo === "ingrediente" && selectedIngredient) {
      return selectedIngredient.costo_por_unidad_uso * qty;
    }
    if (form.modo === "producto" && selectedProducto) {
      return selectedProducto.costo_unitario * qty;
    }
    return null;
  })();

  function validate(): boolean {
    const errs: Partial<Record<string, string>> = {};
    if (form.modo === "ingrediente" && !form.ingrediente_id) {
      errs.ingrediente_id = "Seleccione un ingrediente";
    }
    if (form.modo === "producto" && !form.producto_congelado_id) {
      errs.producto_congelado_id = "Seleccione un producto";
    }
    if (form.modo === "libre" && !form.nombre_libre.trim()) {
      errs.nombre_libre = "Ingrese el nombre del item";
    }
    if (!form.cantidad || Number(form.cantidad) <= 0) {
      errs.cantidad = "Debe ser mayor a 0";
    }
    if (!form.fecha) {
      errs.fecha = "Seleccione una fecha";
    } else if (form.fecha > today()) {
      errs.fecha = "La fecha no puede ser futura";
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
      } else if (form.modo === "producto" && selectedProducto) {
        unidad = selectedProducto.unidad;
        costeUnitario = selectedProducto.costo_unitario;
      }

      const body: Record<string, unknown> = {
        motivo: form.motivo,
        notas: form.notas.trim() || null,
      };

      if (!isEdit) {
        // Creating: always send the full record, cost computed from today's price.
        body.cantidad = cantidad;
        body.unidad = unidad;
        body.fecha = form.fecha;
        body.coste_unitario = costeUnitario;
        body.coste_total = costeUnitario * cantidad;
        if (form.modo === "ingrediente") {
          body.ingrediente_id = Number(form.ingrediente_id);
        } else if (form.modo === "producto") {
          body.producto_congelado_id = Number(form.producto_congelado_id);
        } else {
          body.nombre_libre = form.nombre_libre.trim();
        }
      } else {
        // Editing: only send what actually changed. The item link and the
        // cost snapshot are only touched together, when the item itself
        // changed -- otherwise the original coste_unitario (the price at
        // the time the waste happened) must survive untouched, and
        // switching items must fully replace the old link instead of
        // leaving a stale ingrediente_id/producto_congelado_id/nombre_libre
        // behind for a mode nothing points at anymore.
        const init = initialValues!;
        const itemChanged =
          form.modo !== init.modo ||
          form.ingrediente_id !== init.ingrediente_id ||
          form.producto_congelado_id !== init.producto_congelado_id ||
          (form.modo === "libre" && form.nombre_libre.trim() !== init.nombre_libre.trim());

        if (Number(form.cantidad) !== Number(init.cantidad)) {
          body.cantidad = cantidad;
        }
        if (form.fecha !== init.fecha) {
          body.fecha = form.fecha;
        }
        if (itemChanged) {
          body.ingrediente_id = form.modo === "ingrediente" ? Number(form.ingrediente_id) : null;
          body.producto_congelado_id = form.modo === "producto" ? Number(form.producto_congelado_id) : null;
          body.nombre_libre = form.modo === "libre" ? form.nombre_libre.trim() : null;
          body.unidad = unidad;
          body.coste_unitario = costeUnitario;
          body.coste_total = costeUnitario * cantidad;
        } else if (form.unidad !== init.unidad) {
          body.unidad = form.unidad;
        }
      }

      await onSubmit(body);
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al guardar merma",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
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

        {/* Product picker */}
        {form.modo === "producto" && (
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Producto
            </label>
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              className={`w-full px-3 py-2.5 rounded-lg border bg-white text-left focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                errors.producto_congelado_id ? "border-red-400" : "border-cream-dark"
              } ${selectedProducto ? "text-text" : "text-warm-gray"}`}
            >
              {selectedProducto ? selectedProducto.nombre : "Seleccionar producto..."}
            </button>
            {errors.producto_congelado_id && (
              <p className="text-xs text-red-500 mt-1">{errors.producto_congelado_id}</p>
            )}
            {selectedProducto && (
              <p className="text-xs text-warm-gray mt-1">
                Unidad: {selectedProducto.unidad} · Costo: {formatARS(selectedProducto.costo_unitario)}/{selectedProducto.unidad}
              </p>
            )}
          </div>
        )}

        {/* Ingredient picker */}
        {form.modo === "ingrediente" && (
          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Ingrediente <span className="text-red-500">*</span>
            </label>
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              className={`w-full px-3 py-2.5 rounded-lg border bg-white text-left focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
                errors.ingrediente_id ? "border-red-400" : "border-cream-dark"
              } ${selectedIngredient ? "text-text" : "text-warm-gray"}`}
            >
              {selectedIngredient ? selectedIngredient.nombre : "Seleccionar ingrediente..."}
            </button>
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

      {/* Quantity, unit & date */}
      <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
        <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
          Cantidad y fecha
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
            ) : form.modo === "producto" && selectedProducto ? (
              <div className="px-3 py-2.5 rounded-lg border border-cream-dark bg-cream text-warm-gray text-sm min-h-[44px] flex items-center">
                {selectedProducto.unidad}
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

        <div>
          <label className="block text-sm font-medium text-text mb-1">
            Fecha de la merma <span className="text-red-500">*</span>
          </label>
          <input
            type="date"
            value={form.fecha}
            max={today()}
            onChange={(e) => setField("fecha", e.target.value)}
            className={`w-full px-3 py-2.5 rounded-lg border bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
              errors.fecha ? "border-red-400" : "border-cream-dark"
            }`}
          />
          {errors.fecha && (
            <p className="text-xs text-red-500 mt-1">{errors.fecha}</p>
          )}
          <p className="text-xs text-warm-gray mt-1">
            Si la merma ocurrió otro día, elegí esa fecha en vez de hoy.
          </p>
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
          onClick={onCancel}
          className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={saving}
          className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? "Guardando..." : submitLabel}
        </button>
      </div>

      <IngredientOrSubrecetaPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(item) => {
          if (form.modo === "producto") {
            setField("producto_congelado_id", String(item.id));
          } else {
            setField("ingrediente_id", String(item.id));
          }
        }}
        ingredientes={form.modo === "producto" ? productosOpts : ingredientesOpts}
        title={form.modo === "producto" ? "Seleccionar producto" : "Seleccionar ingrediente"}
        searchPlaceholder={form.modo === "producto" ? "Buscar producto..." : "Buscar ingrediente..."}
      />
    </form>
  );
}
