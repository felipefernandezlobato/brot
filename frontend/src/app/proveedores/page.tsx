"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

interface Proveedor {
  id: number;
  nombre: string;
  contacto: string | null;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
  notas: string | null;
  activo: boolean;
}

interface ProveedorForm {
  nombre: string;
  contacto: string;
  telefono: string;
  email: string;
  direccion: string;
  notas: string;
}

const EMPTY_FORM: ProveedorForm = {
  nombre: "",
  contacto: "",
  telefono: "",
  email: "",
  direccion: "",
  notas: "",
};

export default function ProveedoresPage() {
  const { toast } = useToast();

  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [loading, setLoading] = useState(true);
  const [buscar, setBuscar] = useState("");

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<ProveedorForm>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);

  // Edit form
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<ProveedorForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Delete
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = () => {
    setLoading(true);
    apiFetch<Proveedor[]>("/api/proveedores")
      .then(setProveedores)
      .catch(() => toast("Error al cargar proveedores", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtrados = proveedores.filter((p) => {
    if (!buscar) return true;
    const q = buscar.toLowerCase();
    return (
      p.nombre.toLowerCase().includes(q) ||
      (p.contacto ?? "").toLowerCase().includes(q) ||
      (p.email ?? "").toLowerCase().includes(q)
    );
  });

  // ---- Create ----
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.nombre.trim()) {
      toast("El nombre es obligatorio", "error");
      return;
    }
    setCreating(true);
    try {
      await apiFetch("/api/proveedores", {
        method: "POST",
        body: JSON.stringify({
          nombre: createForm.nombre.trim(),
          contacto: createForm.contacto || null,
          telefono: createForm.telefono || null,
          email: createForm.email || null,
          direccion: createForm.direccion || null,
          notas: createForm.notas || null,
        }),
      });
      toast("Proveedor creado");
      setShowCreate(false);
      setCreateForm(EMPTY_FORM);
      load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al crear proveedor";
      toast(msg, "error");
    } finally {
      setCreating(false);
    }
  };

  // ---- Edit ----
  const startEdit = (p: Proveedor) => {
    setEditId(p.id);
    setEditForm({
      nombre: p.nombre,
      contacto: p.contacto ?? "",
      telefono: p.telefono ?? "",
      email: p.email ?? "",
      direccion: p.direccion ?? "",
      notas: p.notas ?? "",
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editForm.nombre.trim() || editId === null) return;
    setSaving(true);
    try {
      await apiFetch(`/api/proveedores/${editId}`, {
        method: "PUT",
        body: JSON.stringify({
          nombre: editForm.nombre.trim(),
          contacto: editForm.contacto || null,
          telefono: editForm.telefono || null,
          email: editForm.email || null,
          direccion: editForm.direccion || null,
          notas: editForm.notas || null,
        }),
      });
      toast("Proveedor actualizado");
      setEditId(null);
      load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al guardar";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  // ---- Delete ----
  const handleDelete = async () => {
    if (deleteId === null) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/proveedores/${deleteId}`, { method: "DELETE" });
      toast("Proveedor eliminado");
      setDeleteId(null);
      load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al eliminar";
      toast(msg, "error");
    } finally {
      setDeleting(false);
    }
  };

  const deleteName = proveedores.find((p) => p.id === deleteId)?.nombre ?? "";

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Proveedores
        </h1>
        <PermissionGate module="proveedores" action="create">
          <button
            onClick={() => {
              setShowCreate(true);
              setEditId(null);
            }}
            className="bg-brot text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] whitespace-nowrap"
          >
            + Nuevo Proveedor
          </button>
        </PermissionGate>
      </div>

      {/* Create form (inline) */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-white rounded-xl border border-cream-dark p-5 mb-6 space-y-4"
        >
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Nuevo proveedor
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Nombre *
              </label>
              <input
                type="text"
                value={createForm.nombre}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, nombre: e.target.value }))
                }
                placeholder="Ej: Harinera del Norte"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Contacto
              </label>
              <input
                type="text"
                value={createForm.contacto}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, contacto: e.target.value }))
                }
                placeholder="Nombre de contacto"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Teléfono
              </label>
              <input
                type="tel"
                value={createForm.telefono}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, telefono: e.target.value }))
                }
                placeholder="+54 11 ..."
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text mb-1">
                Email
              </label>
              <input
                type="email"
                value={createForm.email}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, email: e.target.value }))
                }
                placeholder="proveedor@ejemplo.com"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-xs font-medium text-text mb-1">
                Dirección
              </label>
              <input
                type="text"
                value={createForm.direccion}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, direccion: e.target.value }))
                }
                placeholder="Dirección del proveedor"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-xs font-medium text-text mb-1">
                Notas
              </label>
              <textarea
                value={createForm.notas}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, notas: e.target.value }))
                }
                rows={2}
                placeholder="Observaciones adicionales"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={() => {
                setShowCreate(false);
                setCreateForm(EMPTY_FORM);
              }}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={creating}
              className="bg-brot text-white px-5 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {creating ? "Guardando..." : "Crear Proveedor"}
            </button>
          </div>
        </form>
      )}

      {/* Search */}
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar por nombre, contacto o email..."
          value={buscar}
          onChange={(e) => setBuscar(e.target.value)}
          className="w-full px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
        />
      </div>

      {/* List */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : filtrados.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No se encontraron proveedores.
          </div>
        ) : (
          <div className="divide-y divide-cream-dark">
            {filtrados.map((p) =>
              editId === p.id ? (
                /* Inline edit row */
                <form
                  key={p.id}
                  onSubmit={handleSave}
                  className="p-4 bg-cream/30 space-y-3"
                >
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-text mb-1">
                        Nombre *
                      </label>
                      <input
                        type="text"
                        value={editForm.nombre}
                        onChange={(e) =>
                          setEditForm((f) => ({ ...f, nombre: e.target.value }))
                        }
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                        required
                        autoFocus
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-text mb-1">
                        Contacto
                      </label>
                      <input
                        type="text"
                        value={editForm.contacto}
                        onChange={(e) =>
                          setEditForm((f) => ({
                            ...f,
                            contacto: e.target.value,
                          }))
                        }
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-text mb-1">
                        Teléfono
                      </label>
                      <input
                        type="tel"
                        value={editForm.telefono}
                        onChange={(e) =>
                          setEditForm((f) => ({
                            ...f,
                            telefono: e.target.value,
                          }))
                        }
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-text mb-1">
                        Email
                      </label>
                      <input
                        type="email"
                        value={editForm.email}
                        onChange={(e) =>
                          setEditForm((f) => ({ ...f, email: e.target.value }))
                        }
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-xs font-medium text-text mb-1">
                        Dirección
                      </label>
                      <input
                        type="text"
                        value={editForm.direccion}
                        onChange={(e) =>
                          setEditForm((f) => ({
                            ...f,
                            direccion: e.target.value,
                          }))
                        }
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-xs font-medium text-text mb-1">
                        Notas
                      </label>
                      <textarea
                        value={editForm.notas}
                        onChange={(e) =>
                          setEditForm((f) => ({ ...f, notas: e.target.value }))
                        }
                        rows={2}
                        className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setEditId(null)}
                      className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      disabled={saving}
                      className="bg-brot text-white px-5 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
                    >
                      {saving ? "Guardando..." : "Guardar"}
                    </button>
                  </div>
                </form>
              ) : (
                /* View row */
                <div
                  key={p.id}
                  className="px-4 py-4 flex items-start justify-between gap-4 hover:bg-cream/30 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-text">{p.nombre}</p>
                      {!p.activo && (
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                          Inactivo
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-warm-gray">
                      {p.contacto && <span>{p.contacto}</span>}
                      {p.telefono && <span>{p.telefono}</span>}
                      {p.email && <span>{p.email}</span>}
                      {p.direccion && <span>{p.direccion}</span>}
                    </div>
                    {p.notas && (
                      <p className="mt-1 text-xs text-warm-gray italic line-clamp-1">
                        {p.notas}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <PermissionGate module="proveedores" action="update">
                      <button
                        onClick={() => startEdit(p)}
                        className="border border-brot text-brot px-3 py-1.5 rounded-lg text-xs font-medium min-h-[36px] hover:bg-brot hover:text-white transition-colors"
                      >
                        Editar
                      </button>
                    </PermissionGate>
                    <PermissionGate module="proveedores" action="delete">
                      <button
                        onClick={() => setDeleteId(p.id)}
                        className="border border-red-300 text-red-500 px-3 py-1.5 rounded-lg text-xs font-medium min-h-[36px] hover:bg-red-50 transition-colors"
                      >
                        Eliminar
                      </button>
                    </PermissionGate>
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </div>

      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {filtrados.length} proveedor{filtrados.length !== 1 ? "es" : ""}
        </p>
      )}

      {/* Delete confirm modal */}
      {deleteId !== null && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="font-medium text-text text-lg mb-2">
              Eliminar proveedor
            </h3>
            <p className="text-warm-gray text-sm mb-6">
              Esta acción no se puede deshacer. El proveedor{" "}
              <strong className="text-text">{deleteName}</strong> se eliminará
              permanentemente.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteId(null)}
                className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting ? "Eliminando..." : "Eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
