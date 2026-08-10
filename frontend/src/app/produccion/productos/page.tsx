"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface ProductoProduccion {
  id: number;
  nombre: string;
  categoria: string;
  unidad: string;
  shelf_life_days: number;
  default_qty: number | null;
  is_active: boolean;
  position: number;
}

interface ProductoForm {
  nombre: string;
  unidad: string;
  is_active: boolean;
}

const EMPTY_FORM: ProductoForm = {
  nombre: "",
  unidad: "unidad",
  is_active: true,
};

const UNIDADES = ["unidad", "kg", "g", "litro", "ml", "bandeja", "caja"];

export default function ProductosProduccionPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [productos, setProductos] = useState<ProductoProduccion[]>([]);
  const [loading, setLoading] = useState(true);
  const [buscar, setBuscar] = useState("");
  const [soloActivos, setSoloActivos] = useState(true);

  // Modal state
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<ProductoForm>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof ProductoForm, string>>>({});
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function loadProductos() {
    setLoading(true);
    try {
      const data = await apiFetch<ProductoProduccion[]>(
        "/api/produccion/productos"
      );
      setProductos(data);
    } catch {
      toast("Error al cargar productos", "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProductos();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtrados = productos.filter((p) => {
    const matchBuscar =
      buscar === "" || p.nombre.toLowerCase().includes(buscar.toLowerCase());
    const matchActivo = !soloActivos || p.is_active;
    return matchBuscar && matchActivo;
  });

  function openCreate() {
    setForm(EMPTY_FORM);
    setErrors({});
    setEditId(null);
    setModal("create");
  }

  function openEdit(p: ProductoProduccion) {
    setForm({
      nombre: p.nombre,
      unidad: p.unidad,
      is_active: p.is_active,
    });
    setErrors({});
    setEditId(p.id);
    setModal("edit");
  }

  function closeModal() {
    setModal(null);
    setEditId(null);
  }

  function setField(field: keyof ProductoForm, value: string | boolean) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  function validate(): boolean {
    const newErrors: Partial<Record<keyof ProductoForm, string>> = {};
    if (!form.nombre.trim()) newErrors.nombre = "El nombre es obligatorio";
    if (!form.unidad) newErrors.unidad = "La unidad es obligatoria";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      const body = {
        nombre: form.nombre.trim(),
        unidad: form.unidad,
        is_active: form.is_active,
      };
      if (modal === "create") {
        await apiFetch("/api/produccion/productos", {
          method: "POST",
          body: JSON.stringify(body),
        });
        toast("Producto creado correctamente");
      } else {
        await apiFetch(`/api/produccion/productos/${editId}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        toast("Producto actualizado correctamente");
      }
      closeModal();
      await loadProductos();
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al guardar el producto",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("¿Eliminar este producto? Esta acción no se puede deshacer."))
      return;
    setDeletingId(id);
    try {
      await apiFetch(`/api/produccion/productos/${id}`, { method: "DELETE" });
      toast("Producto eliminado");
      await loadProductos();
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al eliminar el producto",
        "error"
      );
    } finally {
      setDeletingId(null);
    }
  }

  const inputCls = (hasError?: boolean) =>
    `w-full px-3 py-2.5 rounded-lg border bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] ${
      hasError ? "border-red-400" : "border-cream-dark"
    }`;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/produccion")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <div className="flex-1">
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Productos de Producción
          </h1>
        </div>
        <button
          onClick={openCreate}
          className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] whitespace-nowrap"
        >
          + Nuevo Producto
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="search"
          placeholder="Buscar producto..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="flex-1 px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
        <button
          onClick={() => setSoloActivos((v) => !v)}
          className={`px-4 py-2.5 rounded-lg text-sm font-medium border min-h-[44px] transition-colors whitespace-nowrap ${
            soloActivos
              ? "bg-brot text-white border-brot"
              : "bg-white text-warm-gray border-cream-dark hover:bg-cream"
          }`}
        >
          {soloActivos ? "Solo activos" : "Todos"}
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : filtrados.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No se encontraron productos.
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
                      Unidad
                    </th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">
                      Categoría
                    </th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((p, idx) => (
                    <tr
                      key={p.id}
                      className={`${
                        idx < filtrados.length - 1
                          ? "border-b border-cream-dark"
                          : ""
                      } hover:bg-cream/30 transition-colors`}
                    >
                      <td className="px-4 py-3">
                        <span className="font-medium text-text">{p.nombre}</span>
                        {!p.is_active && (
                          <span className="ml-2 text-xs text-warm-gray bg-cream px-1.5 py-0.5 rounded">
                            Inactivo
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-warm-gray">{p.unidad}</td>
                      <td className="px-4 py-3 text-warm-gray text-sm">
                        {p.categoria ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => openEdit(p)}
                          className="text-sm text-brot hover:text-brot-dark transition-colors px-2 py-1 min-h-[36px]"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleDelete(p.id)}
                          disabled={deletingId === p.id}
                          className="text-sm text-red-500 hover:text-red-700 transition-colors px-2 py-1 min-h-[36px] ml-2 disabled:opacity-50"
                        >
                          {deletingId === p.id ? "..." : "Eliminar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {filtrados.map((p) => (
                <div key={p.id} className="px-4 py-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-text">{p.nombre}</p>
                      <p className="text-xs text-warm-gray mt-0.5">
                        {p.unidad}
                        {!p.is_active && " · Inactivo"}
                      </p>
                      {p.categoria && (
                        <p className="text-xs text-warm-gray mt-0.5">{p.categoria}</p>
                      )}
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => openEdit(p)}
                        className="text-sm text-brot hover:text-brot-dark min-h-[44px] px-2"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(p.id)}
                        disabled={deletingId === p.id}
                        className="text-sm text-red-500 hover:text-red-700 min-h-[44px] px-2 disabled:opacity-50"
                      >
                        {deletingId === p.id ? "..." : "Eliminar"}
                      </button>
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
          {filtrados.length} producto{filtrados.length !== 1 ? "s" : ""}
        </p>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-cream-dark">
              <h2 className="font-[family-name:var(--font-garamond)] text-xl text-brot">
                {modal === "create" ? "Nuevo Producto" : "Editar Producto"}
              </h2>
              <button
                onClick={closeModal}
                className="text-warm-gray hover:text-text transition-colors text-xl min-h-[44px] min-w-[44px] flex items-center justify-center"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-5 space-y-4" noValidate>
              {/* Nombre */}
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Nombre <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={form.nombre}
                  onChange={(e) => setField("nombre", e.target.value)}
                  placeholder="Ej. Pan de molde"
                  className={inputCls(!!errors.nombre)}
                  autoFocus
                />
                {errors.nombre && (
                  <p className="text-xs text-red-500 mt-1">{errors.nombre}</p>
                )}
              </div>

              {/* Unidad */}
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Unidad <span className="text-red-500">*</span>
                </label>
                <select
                  value={form.unidad}
                  onChange={(e) => setField("unidad", e.target.value)}
                  className={inputCls(!!errors.unidad)}
                >
                  {UNIDADES.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
                {errors.unidad && (
                  <p className="text-xs text-red-500 mt-1">{errors.unidad}</p>
                )}
              </div>

              {/* Activo */}
              <label className="flex items-center gap-3 cursor-pointer min-h-[44px]">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setField("is_active", e.target.checked)}
                    className="sr-only"
                  />
                  <div
                    className={`w-11 h-6 rounded-full transition-colors ${
                      form.is_active ? "bg-brot" : "bg-gray-200"
                    }`}
                  >
                    <div
                      className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                        form.is_active ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </div>
                </div>
                <span className="text-sm text-text">Producto activo</span>
              </label>

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving
                    ? "Guardando..."
                    : modal === "create"
                    ? "Crear Producto"
                    : "Guardar cambios"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
