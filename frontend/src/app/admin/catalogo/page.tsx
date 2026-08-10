"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

// ── Types ──────────────────────────────────────────────────────────────────

interface Producto {
  id: number;
  nombre: string;
  descripcion: string | null;
  precio: number;
  categoria: string;
  imagen_url: string | null;
  disponible: boolean;
  posicion: number;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatPrice(n: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(n);
}

// ── Row component ─────────────────────────────────────────────────────────────

interface ProductoRowProps {
  producto: Producto;
  editId: number | null;
  editForm: { nombre: string; descripcion: string; precio: string; categoria: string; imagen_url: string; disponible: boolean; posicion: string };
  deleteConfirm: number | null;
  saving: boolean;
  onStartEdit: (p: Producto) => void;
  onCancelEdit: () => void;
  onEditChange: (field: string, value: string | boolean) => void;
  onSaveEdit: (id: number) => void;
  onRequestDelete: (id: number) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (id: number) => void;
}

function ProductoRow({
  producto,
  editId,
  editForm,
  deleteConfirm,
  saving,
  onStartEdit,
  onCancelEdit,
  onEditChange,
  onSaveEdit,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: ProductoRowProps) {
  if (editId === producto.id) {
    return (
      <div className="px-4 py-3 space-y-3 bg-cream/40">
        <div className="flex gap-3 flex-wrap">
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-warm-gray mb-1">Nombre</label>
            <input
              type="text"
              value={editForm.nombre}
              onChange={(e) => onEditChange("nombre", e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              autoFocus
            />
          </div>
          <div className="w-32">
            <label className="block text-xs text-warm-gray mb-1">Precio (ARS)</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={editForm.precio}
              onChange={(e) => onEditChange("precio", e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs text-warm-gray mb-1">Descripción</label>
          <input
            type="text"
            value={editForm.descripcion}
            onChange={(e) => onEditChange("descripcion", e.target.value)}
            placeholder="Opcional"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>
        <div className="flex gap-3 flex-wrap">
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-warm-gray mb-1">Categoría</label>
            <input
              type="text"
              value={editForm.categoria}
              onChange={(e) => onEditChange("categoria", e.target.value)}
              placeholder="Ej: pan"
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>
          <div className="w-24">
            <label className="block text-xs text-warm-gray mb-1">Posición</label>
            <input
              type="number"
              min="0"
              value={editForm.posicion}
              onChange={(e) => onEditChange("posicion", e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs text-warm-gray mb-1">URL de imagen</label>
          <input
            type="text"
            value={editForm.imagen_url}
            onChange={(e) => onEditChange("imagen_url", e.target.value)}
            placeholder="Opcional"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>
        <div className="flex items-center gap-2">
          <input
            id={`disponible-edit-${producto.id}`}
            type="checkbox"
            checked={editForm.disponible}
            onChange={(e) => onEditChange("disponible", e.target.checked)}
            className="w-4 h-4 accent-brot"
          />
          <label
            htmlFor={`disponible-edit-${producto.id}`}
            className="text-sm text-warm-gray"
          >
            Disponible en catálogo
          </label>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onSaveEdit(producto.id)}
            disabled={saving}
            className="px-3 py-2 bg-brot text-white rounded-lg text-sm hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[36px]"
          >
            {saving ? "Guardando..." : "Guardar"}
          </button>
          <button
            onClick={onCancelEdit}
            className="px-3 py-2 border border-cream-dark rounded-lg text-sm hover:bg-cream-dark transition-colors min-h-[36px]"
          >
            Cancelar
          </button>
        </div>
      </div>
    );
  }

  if (deleteConfirm === producto.id) {
    return (
      <div className="px-4 py-3 flex items-center gap-3 flex-wrap bg-red-50">
        <span className="text-sm flex-1">
          ¿Eliminar <strong>{producto.nombre}</strong>?
        </span>
        <button
          onClick={() => onConfirmDelete(producto.id)}
          disabled={saving}
          className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors disabled:opacity-50 min-h-[36px]"
        >
          {saving ? "Eliminando..." : "Sí, eliminar"}
        </button>
        <button
          onClick={onCancelDelete}
          className="px-3 py-2 border border-cream-dark rounded-lg text-sm hover:bg-cream-dark transition-colors min-h-[36px]"
        >
          Cancelar
        </button>
      </div>
    );
  }

  return (
    <div className="px-4 py-3 flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-medium text-text">{producto.nombre}</p>
          {!producto.disponible && (
            <span className="text-xs bg-cream px-1.5 py-0.5 rounded text-warm-gray">
              No disponible
            </span>
          )}
        </div>
        {producto.descripcion && (
          <p className="text-xs text-warm-gray mt-0.5 line-clamp-1">
            {producto.descripcion}
          </p>
        )}
      </div>
      <span className="text-sm font-semibold text-brot shrink-0">
        {formatPrice(producto.precio)}
      </span>
      <button
        onClick={() => onStartEdit(producto)}
        className="text-sm text-brot hover:text-brot-dark min-h-[36px] px-2 transition-colors"
      >
        Editar
      </button>
      <button
        onClick={() => onRequestDelete(producto.id)}
        className="text-sm text-red-600 hover:text-red-700 min-h-[36px] px-2 transition-colors"
      >
        Eliminar
      </button>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

const emptyEditForm = {
  nombre: "",
  descripcion: "",
  precio: "",
  categoria: "",
  imagen_url: "",
  disponible: true,
  posicion: "0",
};

export default function AdminCatalogoPage() {
  const { toast } = useToast();

  const [productos, setProductos] = useState<Producto[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ ...emptyEditForm });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ ...emptyEditForm });

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<Producto[]>("/api/admin/catalogo")
      .then(setProductos)
      .catch(() => toast("Error al cargar catálogo", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  // Edit handlers
  const startEdit = (p: Producto) => {
    setEditId(p.id);
    setEditForm({
      nombre: p.nombre,
      descripcion: p.descripcion ?? "",
      precio: String(p.precio),
      categoria: p.categoria ?? "",
      imagen_url: p.imagen_url ?? "",
      disponible: p.disponible,
      posicion: String(p.posicion ?? 0),
    });
    setDeleteConfirm(null);
    setShowCreate(false);
  };

  const handleEditChange = (field: string, value: string | boolean) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveEdit = async (id: number) => {
    if (!editForm.nombre.trim()) return;
    setSaving(true);
    try {
      await apiFetch<Producto>(`/api/admin/catalogo/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          nombre: editForm.nombre.trim(),
          descripcion: editForm.descripcion.trim() || null,
          precio: parseFloat(editForm.precio),
          categoria: editForm.categoria.trim(),
          imagen_url: editForm.imagen_url.trim() || null,
          disponible: editForm.disponible,
          posicion: parseInt(editForm.posicion) || 0,
        }),
      });
      toast("Producto actualizado");
      setEditId(null);
      load();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al actualizar producto";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/admin/catalogo/${id}`, { method: "DELETE" });
      toast("Producto eliminado");
      setDeleteConfirm(null);
      load();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al eliminar producto";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  // Create handlers
  const handleCreateChange = (field: string, value: string | boolean) => {
    setCreateForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.nombre.trim()) return;
    setSaving(true);
    try {
      await apiFetch<Producto>("/api/admin/catalogo", {
        method: "POST",
        body: JSON.stringify({
          nombre: createForm.nombre.trim(),
          descripcion: createForm.descripcion.trim() || null,
          precio: parseFloat(createForm.precio),
          categoria: createForm.categoria.trim(),
          imagen_url: createForm.imagen_url.trim() || null,
          disponible: createForm.disponible,
          posicion: parseInt(createForm.posicion) || 0,
        }),
      });
      toast("Producto creado");
      setShowCreate(false);
      setCreateForm({ ...emptyEditForm });
      load();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al crear producto";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const disponibles = productos.filter((p) => p.disponible);
  const noDisponibles = productos.filter((p) => !p.disponible);

  const renderSection = (title: string, items: Producto[]) => (
    <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
      <div className="px-4 py-2.5 bg-cream-dark flex items-center justify-between">
        <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
          {title}
        </h3>
        <span className="text-xs text-warm-gray">{items.length}</span>
      </div>
      <div className="divide-y divide-cream-dark">
        {items.length === 0 ? (
          <p className="px-4 py-4 text-sm text-warm-gray">Sin productos.</p>
        ) : (
          items.map((p) => (
            <ProductoRow
              key={p.id}
              producto={p}
              editId={editId}
              editForm={editForm}
              deleteConfirm={deleteConfirm}
              saving={saving}
              onStartEdit={startEdit}
              onCancelEdit={() => setEditId(null)}
              onEditChange={handleEditChange}
              onSaveEdit={handleSaveEdit}
              onRequestDelete={(id) => {
                setDeleteConfirm(id);
                setEditId(null);
              }}
              onCancelDelete={() => setDeleteConfirm(null)}
              onConfirmDelete={handleDelete}
            />
          ))
        )}
      </div>
    </div>
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6 gap-3">
        <div>
          <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
            Catálogo de Productos
          </h2>
          <p className="text-sm text-warm-gray mt-1">
            Gestiona los productos visibles en la tienda de clientes.
          </p>
        </div>
        <button
          onClick={() => {
            setShowCreate((v) => !v);
            setEditId(null);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[40px] whitespace-nowrap"
        >
          + Nuevo Producto
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
          <h3 className="font-medium mb-4">Nuevo Producto</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="flex gap-3 flex-wrap">
              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs font-medium text-warm-gray mb-1">
                  Nombre <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={createForm.nombre}
                  onChange={(e) => handleCreateChange("nombre", e.target.value)}
                  placeholder="Ej: Pan de campaña"
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
              <div className="w-36">
                <label className="block text-xs font-medium text-warm-gray mb-1">
                  Precio (ARS) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  step="0.01"
                  value={createForm.precio}
                  onChange={(e) => handleCreateChange("precio", e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Descripción
              </label>
              <input
                type="text"
                value={createForm.descripcion}
                onChange={(e) => handleCreateChange("descripcion", e.target.value)}
                placeholder="Breve descripción (opcional)"
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="flex gap-3 flex-wrap">
              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs font-medium text-warm-gray mb-1">
                  Categoría <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={createForm.categoria}
                  onChange={(e) => handleCreateChange("categoria", e.target.value)}
                  placeholder="Ej: pan"
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
              <div className="w-24">
                <label className="block text-xs font-medium text-warm-gray mb-1">
                  Posición
                </label>
                <input
                  type="number"
                  min="0"
                  value={createForm.posicion}
                  onChange={(e) => handleCreateChange("posicion", e.target.value)}
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                URL de imagen
              </label>
              <input
                type="text"
                value={createForm.imagen_url}
                onChange={(e) => handleCreateChange("imagen_url", e.target.value)}
                placeholder="URL de imagen (opcional)"
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="disponible-create"
                type="checkbox"
                checked={createForm.disponible}
                onChange={(e) => handleCreateChange("disponible", e.target.checked)}
                className="w-4 h-4 accent-brot"
              />
              <label
                htmlFor="disponible-create"
                className="text-sm text-warm-gray"
              >
                Disponible en catálogo desde el inicio
              </label>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[40px]"
              >
                {saving ? "Creando..." : "Crear"}
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 border border-cream-dark rounded-lg text-sm hover:bg-cream-dark transition-colors min-h-[40px]"
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <p className="text-warm-gray py-8 text-center">Cargando catálogo...</p>
      ) : (
        <>
          {renderSection("Disponibles", disponibles)}
          {noDisponibles.length > 0 && renderSection("No disponibles", noDisponibles)}
        </>
      )}

      {!loading && productos.length === 0 && (
        <div className="text-center py-12 text-warm-gray">
          <p className="text-lg">Sin productos en el catálogo</p>
          <p className="text-sm mt-1">
            Usa el botón de arriba para añadir el primer producto.
          </p>
        </div>
      )}
    </div>
  );
}
