"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Categoria } from "@/lib/types";
import { useToast } from "@/components/Toast";

// ---- Subcomponent: individual category row ----

interface CategoriaRowProps {
  cat: Categoria;
  editId: number | null;
  editNombre: string;
  editMargen: string;
  deleteConfirm: number | null;
  saving: boolean;
  onStartEdit: (cat: Categoria) => void;
  onCancelEdit: () => void;
  onEditNombreChange: (v: string) => void;
  onEditMargenChange: (v: string) => void;
  onSaveEdit: (cat: Categoria) => void;
  onRequestDelete: (id: number) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (id: number) => void;
}

function CategoriaRow({
  cat,
  editId,
  editNombre,
  editMargen,
  deleteConfirm,
  saving,
  onStartEdit,
  onCancelEdit,
  onEditNombreChange,
  onEditMargenChange,
  onSaveEdit,
  onRequestDelete,
  onCancelDelete,
  onConfirmDelete,
}: CategoriaRowProps) {
  if (editId === cat.id) {
    return (
      <div className="px-4 py-3 flex gap-2 flex-wrap items-center">
        <input
          type="text"
          value={editNombre}
          onChange={(e) => onEditNombreChange(e.target.value)}
          className="flex-1 min-w-[120px] px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          autoFocus
        />
        {cat.tipo === "receta" && (
          <input
            type="number"
            value={editMargen}
            onChange={(e) => onEditMargenChange(e.target.value)}
            placeholder="Margen %"
            step="0.01"
            min="0"
            max="100"
            className="w-28 px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        )}
        <button
          onClick={() => onSaveEdit(cat)}
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

  if (deleteConfirm === cat.id) {
    return (
      <div className="px-4 py-3 flex items-center gap-3 flex-wrap bg-red-50">
        <span className="text-sm flex-1">
          ¿Eliminar <strong>{cat.nombre}</strong>?
        </span>
        <button
          onClick={() => onConfirmDelete(cat.id)}
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
        <p className="text-sm font-medium text-text">{cat.nombre}</p>
        {cat.tipo === "receta" && cat.margen_objetivo != null && (
          <p className="text-xs text-warm-gray">
            Margen objetivo: {cat.margen_objetivo}%
          </p>
        )}
      </div>
      <button
        onClick={() => onStartEdit(cat)}
        className="px-3 py-2 text-sm text-brot hover:text-brot-dark min-h-[44px] transition-colors"
      >
        Editar
      </button>
      <button
        onClick={() => onRequestDelete(cat.id)}
        className="px-3 py-2 text-sm text-red-600 hover:text-red-700 min-h-[44px] transition-colors"
      >
        Eliminar
      </button>
    </div>
  );
}

// ---- Main page ----

export default function CategoriasPage() {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [loading, setLoading] = useState(true);

  // Edit state
  const [editId, setEditId] = useState<number | null>(null);
  const [editNombre, setEditNombre] = useState("");
  const [editMargen, setEditMargen] = useState("");

  // Delete confirm state
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  // Create form state
  const [newNombre, setNewNombre] = useState("");
  const [newTipo, setNewTipo] = useState<"ingrediente" | "receta">("ingrediente");
  const [newMargen, setNewMargen] = useState("");

  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const loadCategorias = useCallback(() => {
    setLoading(true);
    apiFetch<Categoria[]>("/api/categorias")
      .then(setCategorias)
      .catch(() => toast("Error al cargar categorías", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    loadCategorias();
  }, [loadCategorias]);

  const ingredientes = categorias.filter((c) => c.tipo === "ingrediente");
  const recetas = categorias.filter((c) => c.tipo === "receta");

  // ---- Handlers ----

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNombre.trim()) return;
    setSaving(true);
    try {
      await apiFetch<Categoria>("/api/categorias", {
        method: "POST",
        body: JSON.stringify({
          nombre: newNombre.trim(),
          tipo: newTipo,
          ...(newTipo === "receta" && newMargen
            ? { margen_objetivo: parseFloat(newMargen) }
            : {}),
        }),
      });
      toast("Categoría creada");
      setNewNombre("");
      setNewMargen("");
      loadCategorias();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al crear categoría";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (cat: Categoria) => {
    setEditId(cat.id);
    setEditNombre(cat.nombre);
    setEditMargen(cat.margen_objetivo?.toString() ?? "");
    setDeleteConfirm(null);
  };

  const handleSaveEdit = async (cat: Categoria) => {
    if (!editNombre.trim()) return;
    setSaving(true);
    try {
      await apiFetch<Categoria>(`/api/categorias/${cat.id}`, {
        method: "PUT",
        body: JSON.stringify({
          nombre: editNombre.trim(),
          tipo: cat.tipo,
          ...(cat.tipo === "receta" && editMargen
            ? { margen_objetivo: parseFloat(editMargen) }
            : {}),
        }),
      });
      toast("Categoría actualizada");
      setEditId(null);
      loadCategorias();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al actualizar";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/categorias/${id}`, { method: "DELETE" });
      toast("Categoría eliminada");
      setDeleteConfirm(null);
      loadCategorias();
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : "";
      // API returns 409 when category has linked items
      const isConflict =
        raw.includes("409") ||
        raw.toLowerCase().includes("conflict") ||
        raw.toLowerCase().includes("tiene") ||
        raw.toLowerCase().includes("asociad");
      toast(
        isConflict
          ? "No se puede eliminar: la categoría tiene elementos asociados"
          : raw || "Error al eliminar",
        "error"
      );
      setDeleteConfirm(null);
    } finally {
      setSaving(false);
    }
  };

  // ---- Render ----

  const renderSection = (
    title: string,
    items: Categoria[],
    tipo: "ingrediente" | "receta"
  ) => (
    <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-6">
      <div className="px-4 py-2.5 bg-cream-dark flex items-center justify-between">
        <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
          {title}
        </h3>
        <span className="text-xs text-warm-gray">{items.length}</span>
      </div>
      <div className="divide-y divide-cream-dark">
        {items.length === 0 ? (
          <p className="px-4 py-4 text-sm text-warm-gray">
            Sin categorías de tipo {tipo}. Añade una con el formulario de abajo.
          </p>
        ) : (
          items.map((cat) => (
            <CategoriaRow
              key={cat.id}
              cat={cat}
              editId={editId}
              editNombre={editNombre}
              editMargen={editMargen}
              deleteConfirm={deleteConfirm}
              saving={saving}
              onStartEdit={startEdit}
              onCancelEdit={() => setEditId(null)}
              onEditNombreChange={setEditNombre}
              onEditMargenChange={setEditMargen}
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
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Categorías
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Gestiona las categorías de ingredientes y recetas.
        </p>
      </div>

      {loading ? (
        <p className="text-warm-gray py-8 text-center">Cargando categorías...</p>
      ) : (
        <>
          {renderSection("Ingredientes", ingredientes, "ingrediente")}
          {renderSection("Recetas", recetas, "receta")}
        </>
      )}

      {/* Create form */}
      <div className="bg-white rounded-xl border border-cream-dark p-5">
        <h3 className="font-medium mb-4">Nueva Categoría</h3>
        <form onSubmit={handleCreate}>
          <div className="flex gap-3 flex-wrap items-end">
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Nombre
              </label>
              <input
                type="text"
                value={newNombre}
                onChange={(e) => setNewNombre(e.target.value)}
                placeholder="Nombre de la categoría"
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Tipo
              </label>
              <select
                value={newTipo}
                onChange={(e) =>
                  setNewTipo(e.target.value as "ingrediente" | "receta")
                }
                className="px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[42px]"
              >
                <option value="ingrediente">Ingrediente</option>
                <option value="receta">Receta</option>
              </select>
            </div>

            {newTipo === "receta" && (
              <div>
                <label className="block text-xs font-medium text-warm-gray mb-1">
                  Margen objetivo (%)
                </label>
                <input
                  type="number"
                  value={newMargen}
                  onChange={(e) => setNewMargen(e.target.value)}
                  placeholder="0.00"
                  step="0.01"
                  min="0"
                  max="100"
                  className="w-28 px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
            )}

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
