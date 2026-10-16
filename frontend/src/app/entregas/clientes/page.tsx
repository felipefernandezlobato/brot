"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface ClienteB2B {
  id: number;
  nombre: string;
  email: string | null;
  // Calculado en el backend a partir de password_hash: distingue al cliente
  // de reparto del que ademas entra al portal.
  tiene_acceso: boolean;
  email_verificado: boolean;
  aprobado: boolean;
  direccion: string | null;
  telefono: string | null;
  contacto: string | null;
  notas: string | null;
  dia_entrega_preferido: string | null;
  is_active: boolean;
}

const EMPTY_FORM = {
  nombre: "",
  email: "",
  contacto: "",
  telefono: "",
  direccion: "",
  notas: "",
  dia_entrega_preferido: "",
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
          <label className="block text-xs font-medium text-warm-gray mb-1">
            Correo electrónico
          </label>
          <input
            type="email"
            value={form.email}
            onChange={(e) => onChange({ ...form, email: e.target.value })}
            placeholder="cliente@email.com"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
          <p className="text-[11px] text-warm-gray mt-1">
            Hace falta para darle acceso al portal de pedidos.
          </p>
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
          <label className="block text-xs font-medium text-warm-gray mb-1">Día entrega preferido</label>
          <input
            type="text"
            value={form.dia_entrega_preferido}
            onChange={(e) => onChange({ ...form, dia_entrega_preferido: e.target.value })}
            placeholder="Ej: Lunes, Miércoles"
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
          email: newForm.email.trim() || null,
          contacto: newForm.contacto || null,
          telefono: newForm.telefono || null,
          direccion: newForm.direccion || null,
          notas: newForm.notas || null,
          dia_entrega_preferido: newForm.dia_entrega_preferido || null,
          is_active: true,
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

  const [invitando, setInvitando] = useState<number | null>(null);

  const invitar = async (c: ClienteB2B) => {
    const reenvio = c.tiene_acceso;
    if (reenvio && !confirm(
      `${c.nombre} ya tiene acceso. Enviarle un enlace nuevo no le borra la contraseña actual, ` +
      `pero el enlace anterior deja de servir. ¿Seguimos?`
    )) return;
    setInvitando(c.id);
    try {
      const r = await apiFetch<{ enviado: boolean; email: string }>(
        `/api/clientes-b2b/${c.id}/invitar`, { method: "POST" }
      );
      // El backend crea el token aunque el correo falle, asi que decirlo
      // importa: si no sale, nadie va a usar ese enlace y el cliente se queda
      // esperando sin que nos enteremos.
      if (r.enviado) toast(`Enlace enviado a ${r.email}`);
      else toast("No se pudo enviar el correo. Revisá la configuración de envío.", "error");
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "No se pudo invitar", "error");
    } finally {
      setInvitando(null);
    }
  };

  const [decidiendo, setDecidiendo] = useState<number | null>(null);

  // Pendiente = se registro solo y todavia no se aprobo. Los que crea Felipe
  // nacen aprobados, asi que nunca caen aqui.
  const pendientes = clientes.filter((c) => !c.aprobado && c.is_active);

  const aprobar = async (c: ClienteB2B) => {
    setDecidiendo(c.id);
    try {
      const r = await apiFetch<{ aprobado: boolean; avisado: boolean }>(
        `/api/clientes-b2b/${c.id}/aprobar`, { method: "POST" }
      );
      toast(r.avisado ? `${c.nombre} ya puede pedir, le avisamos por correo`
                      : `${c.nombre} ya puede pedir (no se pudo enviar el aviso)`);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "No se pudo aprobar", "error");
    } finally {
      setDecidiendo(null);
    }
  };

  const rechazar = async (c: ClienteB2B) => {
    if (!confirm(
      `¿Rechazar el alta de ${c.nombre}?\n\n` +
      `Queda desactivado y no podrá entrar. No se le avisa por correo, y la ` +
      `cuenta no se borra: podés reactivarla más adelante.`
    )) return;
    setDecidiendo(c.id);
    try {
      await apiFetch(`/api/clientes-b2b/${c.id}/rechazar`, { method: "POST" });
      toast(`Alta de ${c.nombre} rechazada`);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "No se pudo rechazar", "error");
    } finally {
      setDecidiendo(null);
    }
  };

  const startEdit = (c: ClienteB2B) => {
    setEditId(c.id);
    setEditForm({
      nombre: c.nombre,
      email: c.email ?? "",
      contacto: c.contacto ?? "",
      telefono: c.telefono ?? "",
      direccion: c.direccion ?? "",
      notas: c.notas ?? "",
      dia_entrega_preferido: c.dia_entrega_preferido ?? "",
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
          email: editForm.email.trim() || null,
          contacto: editForm.contacto || null,
          telefono: editForm.telefono || null,
          direccion: editForm.direccion || null,
          notas: editForm.notas || null,
          dia_entrega_preferido: editForm.dia_entrega_preferido || null,
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
      <div className="flex items-center justify-between mb-6 gap-4">
        <div>
          <h2 className="titulo text-2xl text-brot">
            Clientes B2B
          </h2>
          <p className="text-sm text-warm-gray mt-1">
            Gestiona los clientes para entregas B2B.
          </p>
        </div>
        <Link
          href="/entregas"
          className="text-sm text-brot hover:text-brot-dark transition-colors min-h-[44px] flex items-center"
        >
          ← Entregas B2B
        </Link>
      </div>

      {/* Altas pendientes: arriba y aparte, porque es lo unico de esta
          pantalla que pide una decision. Mezclados en la lista general se
          pasarian por alto, y un cliente esperando no puede pedir. */}
      {pendientes.length > 0 && (
        <div className="mb-6 rounded-xl border border-brot/40 bg-brot/5 p-4">
          <h2 className="titulo text-sm text-brot mb-3">
            {pendientes.length === 1
              ? "1 alta esperando tu aprobación"
              : `${pendientes.length} altas esperando tu aprobación`}
          </h2>
          <div className="space-y-3">
            {pendientes.map((c) => (
              <div key={c.id} className="bg-card rounded-lg border border-cream-dark p-4">
                <p className="font-medium text-text">{c.nombre}</p>
                <div className="mt-1 space-y-0.5 text-xs text-warm-gray">
                  <p className="break-all">{c.email}</p>
                  {c.telefono && <p>{c.telefono}</p>}
                  {c.direccion && <p>{c.direccion}</p>}
                </div>
                {c.email_verificado ? (
                  <p className="text-xs text-brot mt-2">Correo confirmado</p>
                ) : (
                  <p className="text-xs text-orange-600 mt-2">
                    Todavía no confirmó su correo. No se puede aprobar hasta
                    que lo haga.
                  </p>
                )}
                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => aprobar(c)}
                    disabled={!c.email_verificado || decidiendo === c.id}
                    className="px-4 py-2 bg-brot text-white rounded-lg text-sm min-h-[44px] hover:bg-brot-dark disabled:opacity-40"
                  >
                    {decidiendo === c.id ? "..." : "Aprobar"}
                  </button>
                  <button
                    onClick={() => rechazar(c)}
                    disabled={decidiendo === c.id}
                    className="px-4 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark disabled:opacity-40"
                  >
                    Rechazar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Client list */}
      <div className="space-y-3 mb-6">
        {loading ? (
          <div className="bg-card rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
            Cargando...
          </div>
        ) : clientes.length === 0 ? (
          <div className="bg-card rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
            Sin clientes registrados.
          </div>
        ) : (
          clientes.filter((c) => c.aprobado || !c.is_active).map((c) => {
            if (editId === c.id) {
              return (
                <div key={c.id} className="bg-card rounded-xl border border-brot/30 p-5">
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
              <div key={c.id} className="bg-card rounded-xl border border-cream-dark p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-text">{c.nombre}</p>
                      {!c.is_active && (
                        <span className="text-xs text-warm-gray bg-cream px-1.5 py-0.5 rounded">
                          Inactivo
                        </span>
                      )}
                      {c.tiene_acceso && (
                        <span className="text-xs text-brot bg-brot/10 px-1.5 py-0.5 rounded">
                          Portal
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-warm-gray">
                      {c.contacto && <span>{c.contacto}</span>}
                      {c.email && <span>{c.email}</span>}
                      {c.telefono && <span>{c.telefono}</span>}
                      {c.dia_entrega_preferido && <span>Entrega: {c.dia_entrega_preferido}</span>}
                    </div>
                    {c.direccion && (
                      <p className="text-xs text-warm-gray mt-0.5">{c.direccion}</p>
                    )}
                    {c.notas && (
                      <p className="text-xs text-warm-gray italic mt-0.5">{c.notas}</p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    {c.email && c.is_active && (
                      <button
                        onClick={() => invitar(c)}
                        disabled={invitando === c.id}
                        title={c.tiene_acceso
                          ? "Reenviar el enlace para cambiar la contraseña"
                          : "Darle acceso al portal de pedidos"}
                        className="px-3 py-2 text-sm text-brot hover:text-brot-dark transition-colors min-h-[44px] disabled:opacity-50"
                      >
                        {invitando === c.id ? "Enviando..." : c.tiene_acceso ? "Reenviar" : "Dar acceso"}
                      </button>
                    )}
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
      <div className="bg-card rounded-xl border border-cream-dark p-5">
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
