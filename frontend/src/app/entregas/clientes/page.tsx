"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface ClienteB2B {
  id: number;
  nombre: string;
  contacto: string | null;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
  notas: string | null;
  activo: boolean;
}

const EMPTY_FORM = {
  nombre: "",
  contacto: "",
  telefono: "",
  email: "",
  direccion: "",
  notas: "",
};

type FormState = typeof EMPTY_FORM;

function ClienteForm({
  form,
  onChange,
  onSubmit,
  saving,
  submitLabel,
  onCancel,
}: {
  form: FormState;
  onChange: (f: FormState) => void;
  onSubmit: (e: React.FormEvent) => void;
  saving: boolean;
  submitLabel: string;
  onCancel?: () => void;
}) {
  return (
    <form onSubmit={onSubmit}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-warm-gray mb-1">
            Nombre <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.nombre}
            onChange={(e) => onChange({ ...form, nombre: e.target.value })}
            placeholder="Nombre del cliente"
            required
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-warm-gray mb-1">Contacto</label>
          <input
            type="text"
            value={form.contacto}
            onChange={(e) => onChange({ ...form, contacto: e.target.value })}
            placeholder="Persona de contacto"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-warm-gray mb-1">Teléfono</label>
          <input
            type="tel"
            value={form.telefono}
            onChange={(e) => onChange({ ...form, telefono: e.target.value })}
            placeholder="+34 600 000 000"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-warm-gray mb-1">Email</label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => onChange({ ...form, email: e.target.value })}
            placeholder="cliente@empresa.com"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="block text-xs font-medium text-warm-gray mb-1">Dirección</label>
          <input
            type="text"
            value={form.direccion}
            onChange={(e) => onChange({ ...form, direccion: e.target.value })}
            placeholder="Dirección de entrega"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="block text-xs font-medium text-warm-gray mb-1">Notas</label>
          <input
            type="text"
            value={form.notas}
            onChange={(e) => onChange({ ...form, notas: e.target.value })}
            placeholder="Notas adicionales"
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>
      </div>

      <div className="flex gap-3 mt-4">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
        >
          {saving ? "Guardando..." : submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark transition-colors"
          >
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

export default function ClientesB2BPage() {
  const { toast } = useToast();
  const [clientes, setClientes] = useState<ClienteB2B[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<FormState>({ ...EMPTY_FORM });

  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const [newForm, setNewForm] = useState<FormState>({ ...EMPTY_FORM });

  const load = useCallback(() => {
    setLoading(true);
    apiFetch<ClienteB2B[]>("/api/clientes-b2b")
      .then(setClientes)
      .catch(() => toast("Error al cargar clientes", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newForm.nombre.trim()) return;
    setSaving(true);
    try {
      await apiFetch<ClienteB2B>("/api/clientes-b2b", {
        method: "POST",
        body: JSON.stringify({
          nombre: newForm.nombre.trim(),
          contacto: newForm.contacto || null,
          telefono: newForm.telefono || null,
          email: newForm.email || null,
          direccion: newForm.direccion || null,
          notas: newForm.notas || null,
        }),
      });
      toast("Cliente creado");
      setNewForm({ ...EMPTY_FORM });
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al crear cliente", "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (c: ClienteB2B) => {
    setEditId(c.id);
    setEditForm({
      nombre: c.nombre,
      contacto: c.contacto ?? "",
      telefono: c.telefono ?? "",
      email: c.email ?? "",
      direccion: c.direccion ?? "",
      notas: c.notas ?? "",
    });
    setDeleteConfirm(null);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editId || !editForm.nombre.trim()) return;
    setSaving(true);
    try {
      await apiFetch<ClienteB2B>(`/api/clientes-b2b/${editId}`, {
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
      toast("Cliente actualizado");
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
      await apiFetch(`/api/clientes-b2b/${id}`, { method: "DELETE" });
      toast("Cliente eliminado");
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
          Clientes B2B
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Gestiona los clientes para entregas B2B.
        </p>
      </div>

      {/* Client list */}
      <div className="space-y-3 mb-6">
        {loading ? (
          <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
            Cargando...
          </div>
        ) : clientes.length === 0 ? (
          <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
            Sin clientes registrados.
          </div>
        ) : (
          clientes.map((c) => {
            if (editId === c.id) {
              return (
                <div key={c.id} className="bg-white rounded-xl border border-brot/30 p-5">
                  <h3 className="font-medium mb-4 text-sm">Editando: {c.nombre}</h3>
                  <ClienteForm
                    form={editForm}
                    onChange={setEditForm}
                    onSubmit={handleSaveEdit}
                    saving={saving}
                    submitLabel="Guardar cambios"
                    onCancel={() => setEditId(null)}
                  />
                </div>
              );
            }

            if (deleteConfirm === c.id) {
              return (
                <div key={c.id} className="bg-red-50 rounded-xl border border-red-200 p-4 flex items-center gap-3 flex-wrap">
                  <span className="text-sm flex-1">
                    ¿Eliminar cliente <strong>{c.nombre}</strong>?
                  </span>
                  <button
                    onClick={() => handleDelete(c.id)}
                    disabled={saving}
                    className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm min-h-[44px] hover:bg-red-700 disabled:opacity-50"
                  >
                    {saving ? "..." : "Sí, eliminar"}
                  </button>
                  <button
                    onClick={() => setDeleteConfirm(null)}
                    className="px-3 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark"
                  >
                    Cancelar
                  </button>
                </div>
              );
            }

            return (
              <div key={c.id} className="bg-white rounded-xl border border-cream-dark p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-text">{c.nombre}</p>
                      {!c.activo && (
                        <span className="text-xs text-warm-gray bg-cream px-1.5 py-0.5 rounded">
                          Inactivo
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-warm-gray">
                      {c.contacto && <span>{c.contacto}</span>}
                      {c.telefono && <span>{c.telefono}</span>}
                      {c.email && <span>{c.email}</span>}
                    </div>
                    {c.direccion && (
                      <p className="text-xs text-warm-gray mt-0.5">{c.direccion}</p>
                    )}
                    {c.notas && (
                      <p className="text-xs text-warm-gray italic mt-0.5">{c.notas}</p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => startEdit(c)}
                      className="px-3 py-2 text-sm text-brot hover:text-brot-dark transition-colors min-h-[44px]"
                    >
                      Editar
                    </button>
                    <button
                      onClick={() => { setDeleteConfirm(c.id); setEditId(null); }}
                      className="px-3 py-2 text-sm text-red-600 hover:text-red-700 transition-colors min-h-[44px]"
                    >
                      Eliminar
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-cream-dark p-5">
        <h3 className="font-medium mb-4">Nuevo cliente</h3>
        <ClienteForm
          form={newForm}
          onChange={setNewForm}
          onSubmit={handleCreate}
          saving={saving}
          submitLabel="Crear cliente"
        />
      </div>
    </div>
  );
}
