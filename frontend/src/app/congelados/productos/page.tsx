"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface ProductoCongelado {
  id: number;
  nombre: string;
  unidad: string;
}

interface ProductoRowProps {
  producto: ProductoCongelado;
  editId: number | null;
  editNombre: string;
  editUnidad: string;
  deleteConfirm: number | null;
  saving: boolean;
  onStartEdit: (p: ProductoCongelado) => void;
  onCancelEdit: () => void;
  onEditNombreChange: (v: string) => void;
  onEditUnidadChange: (v: string) => void;
  onSaveEdit: (p: ProductoCongelado) => void;
  onRequestDelete: (id: number) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (id: number) => void;
}

function ProductoRow({
  producto,
  editId,
  editNombre,
  editUnidad,
  deleteConfirm,
  saving,
  onStartEdit,
  onCancelEdit,
  onEditNombreChange,
  onEditUnidadChange,
  onSaveEdit,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: ProductoRowProps) {
  if (editId === producto.id) {
    return (
      <div className="px-4 py-3 flex gap-2 flex-wrap items-center">
        <input
          type="text"
          value={editNombre}
          onChange={(e) => onEditNombreChange(e.target.value)}
          placeholder="Nombre"
          autoFocus
          className="flex-1 min-w-[120px] px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
        />
        <input
          type="text"
          value={editUnidad}
          onChange={(e) => onEditUnidadChange(e.target.value)}
          placeholder="Unidad"
          className="w-28 px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
        />
        <button
          onClick={() => onSaveEdit(producto)}
          disabled={saving}
          className="px-3 py-2 bg-brot text-white rounded-lg text-sm min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
        >
          {saving ? "Guardando..." : "Guardar"}
        </button>
        <button
          onClick={onCancelEdit}
          className="px-3 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark transition-colors"
        >
          Cancelar
        </button>
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
          className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm min-h-[44px] hover:bg-red-700 transition-colors disabled:opacity-50"
        >
          {saving ? "Eliminando..." : "Sí, eliminar"}
        </button>
        <button
          onClick={onCancelDelete}
          className="px-3 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark transition-colors"
        >
          Cancelar
        </button>
      </div>
    );
  }

  return (
    <div className="px-4 py-3 flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text">{producto.nombre}</p>
        <p className="text-xs text-warm-gray">{producto.unidad}</p>
      </div>
      <button
        onClick={() => onStartEdit(producto)}
        className="px-3 py-2 text-sm text-brot hover:text-brot-dark min-h-[44px] transition-colors"
      >
        Editar
      </button>
      <button
        onClick={() => onRequestDelete(producto.id)}
        className="px-3 py-2 text-sm text-red-600 hover:text-red-700 min-h-[44px] transition-colors"
      >
        Eliminar
      </button>
    </div>
  );
}

export default function ProductosCongeladosPage() {
  const { toast } = useToast();
  const [productos, setProductos] = useState<ProductoCongelado[]>([]);
  const [loading, setLoading] = useState(true);

  const [editId, setEditId] = useState<number | null>(null);
  const [editNombre, setEditNombre] = useState("");
  const [editUnidad, setEditUnidad] = useState("");

  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const [newNombre, setNewNombre] = useState("");
  const [newUnidad, setNewUnidad] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<ProductoCongelado[]>("/api/congelados/productos")
      .then(setProductos)
      .catch(() => toast("Error al cargar productos", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNombre.trim() || !newUnidad.trim()) return;
    setSaving(true);
    try {
      await apiFetch<ProductoCongelado>("/api/congelados/productos", {
        method: "POST",
        body: JSON.stringify({ nombre: newNombre.trim(), unidad: newUnidad.trim() }),
      });
      toast("Producto creado");
      setNewNombre("");
      setNewUnidad("");
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al crear", "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (p: ProductoCongelado) => {
    setEditId(p.id);
    setEditNombre(p.nombre);
    setEditUnidad(p.unidad);
    setDeleteConfirm(null);
  };

  const handleSaveEdit = async (p: ProductoCongelado) => {
    if (!editNombre.trim() || !editUnidad.trim()) return;
    setSaving(true);
    try {
      await apiFetch<ProductoCongelado>(`/api/congelados/productos/${p.id}`, {
        method: "PUT",
        body: JSON.stringify({ nombre: editNombre.trim(), unidad: editUnidad.trim() }),
      });
      toast("Producto actualizado");
      setEditId(null);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al actualizar", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/congelados/productos/${id}`, { method: "DELETE" });
      toast("Producto eliminado");
      setDeleteConfirm(null);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al eliminar", "error");
      setDeleteConfirm(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Productos Congelados
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Gestiona el catálogo de productos que pueden ser congelados.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-6">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : productos.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            Sin productos. Añade el primero abajo.
          </div>
        ) : (
          <div className="divide-y divide-cream-dark">
            {productos.map((p) => (
              <ProductoRow
                key={p.id}
                producto={p}
                editId={editId}
                editNombre={editNombre}
                editUnidad={editUnidad}
                deleteConfirm={deleteConfirm}
                saving={saving}
                onStartEdit={startEdit}
                onCancelEdit={() => setEditId(null)}
                onEditNombreChange={setEditNombre}
                onEditUnidadChange={setEditUnidad}
                onSaveEdit={handleSaveEdit}
                onRequestDelete={(id) => { setDeleteConfirm(id); setEditId(null); }}
                onCancelDelete={() => setDeleteConfirm(null)}
                onConfirmDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-cream-dark p-5">
        <h3 className="font-medium mb-4">Nuevo Producto</h3>
        <form onSubmit={handleCreate}>
          <div className="flex gap-3 flex-wrap items-end">
            <div className="flex-1 min-w-[140px]">
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Nombre <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={newNombre}
                onChange={(e) => setNewNombre(e.target.value)}
                placeholder="Nombre del producto"
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="w-36">
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Unidad <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={newUnidad}
                onChange={(e) => setNewUnidad(e.target.value)}
                placeholder="kg, unid, porciones…"
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {saving ? "Creando..." : "Crear"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
