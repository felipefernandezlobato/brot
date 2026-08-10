"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";

interface ClienteB2B {
  id: number;
  nombre: string;
  contacto: string | null;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
}

type EstadoEntrega = "pendiente" | "en_camino" | "entregado" | "cancelado";

interface EntregaB2B {
  id: number;
  cliente_id: number;
  cliente_nombre: string;
  fecha: string;
  estado: EstadoEntrega;
  notas: string | null;
}

const ESTADOS: EstadoEntrega[] = ["pendiente", "en_camino", "entregado", "cancelado"];

const ESTADO_LABEL: Record<EstadoEntrega, string> = {
  pendiente: "Pendiente",
  en_camino: "En camino",
  entregado: "Entregado",
  cancelado: "Cancelado",
};

const ESTADO_CLASS: Record<EstadoEntrega, string> = {
  pendiente: "bg-amber-100 text-amber-800",
  en_camino: "bg-blue-100 text-blue-800",
  entregado: "bg-green-100 text-green-800",
  cancelado: "bg-gray-100 text-gray-600",
};

const EMPTY_FORM = {
  cliente_id: "",
  fecha: new Date().toISOString().slice(0, 10),
  notas: "",
};

export default function EntregasPage() {
  const { toast } = useToast();

  const [entregas, setEntregas] = useState<EntregaB2B[]>([]);
  const [clientes, setClientes] = useState<ClienteB2B[]>([]);
  const [loading, setLoading] = useState(true);

  const [filtroEstado, setFiltroEstado] = useState<EstadoEntrega | "todos">("todos");

  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  const [changingEstadoId, setChangingEstadoId] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<EntregaB2B[]>("/api/entregas-b2b"),
      apiFetch<ClienteB2B[]>("/api/clientes-b2b"),
    ])
      .then(([e, c]) => {
        setEntregas(e);
        setClientes(c);
      })
      .catch(() => toast("Error al cargar entregas", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const filtradas = entregas.filter(
    (e) => filtroEstado === "todos" || e.estado === filtroEstado
  );

  const handleCreate = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!form.cliente_id || !form.fecha) return;
    setSaving(true);
    try {
      await apiFetch<EntregaB2B>("/api/entregas-b2b", {
        method: "POST",
        body: JSON.stringify({
          cliente_id: Number(form.cliente_id),
          fecha: form.fecha,
          notas: form.notas || null,
        }),
      });
      toast("Entrega creada");
      setForm({ ...EMPTY_FORM });
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al crear entrega", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleChangeEstado = async (id: number, estado: EstadoEntrega) => {
    setSaving(true);
    try {
      await apiFetch(`/api/entregas-b2b/${id}/estado`, {
        method: "PUT",
        body: JSON.stringify({ estado }),
      });
      toast("Estado actualizado");
      setChangingEstadoId(null);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al actualizar estado", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/entregas-b2b/${id}`, { method: "DELETE" });
      toast("Entrega eliminada");
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
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Entregas B2B
        </h1>
        <div className="flex gap-3 items-center">
          <Link
            href="/entregas/volumen"
            className="text-sm text-brot hover:text-brot-dark transition-colors"
          >
            Volumen →
          </Link>
          <Link
            href="/entregas/clientes"
            className="text-sm text-brot hover:text-brot-dark transition-colors"
          >
            Clientes →
          </Link>
        </div>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4 scrollbar-hide">
        <button
          onClick={() => setFiltroEstado("todos")}
          className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
            filtroEstado === "todos"
              ? "bg-brot text-white"
              : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
          }`}
        >
          Todas
        </button>
        {ESTADOS.map((est) => (
          <button
            key={est}
            onClick={() => setFiltroEstado(est === filtroEstado ? "todos" : est)}
            className={`px-3 py-1.5 rounded-full text-sm whitespace-nowrap min-h-[36px] transition-colors ${
              filtroEstado === est
                ? "bg-brot text-white"
                : "bg-white border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
            }`}
          >
            {ESTADO_LABEL[est]}
          </button>
        ))}
      </div>

      {/* Entregas list */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-6">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : filtradas.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No hay entregas{filtroEstado !== "todos" ? ` con estado "${ESTADO_LABEL[filtroEstado as EstadoEntrega]}"` : ""}.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Cliente</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Fecha</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Estado</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Notas</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {filtradas.map((entrega, idx) => {
                    if (deleteConfirm === entrega.id) {
                      return (
                        <tr key={entrega.id} className="border-b border-cream-dark bg-red-50">
                          <td colSpan={4} className="px-4 py-3 text-sm">
                            ¿Eliminar entrega de <strong>{entrega.cliente_nombre}</strong> del {formatDate(entrega.fecha)}?
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={() => handleDelete(entrega.id)}
                                disabled={saving}
                                className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 transition-colors disabled:opacity-50"
                              >
                                {saving ? "..." : "Eliminar"}
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="px-3 py-1.5 border border-cream-dark rounded-lg text-xs hover:bg-cream-dark transition-colors"
                              >
                                Cancelar
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    }
                    return (
                      <tr
                        key={entrega.id}
                        className={idx < filtradas.length - 1 ? "border-b border-cream-dark" : ""}
                      >
                        <td className="px-4 py-3 font-medium text-text">{entrega.cliente_nombre}</td>
                        <td className="px-4 py-3 text-warm-gray">{formatDate(entrega.fecha)}</td>
                        <td className="px-4 py-3">
                          {changingEstadoId === entrega.id ? (
                            <div className="flex gap-1 flex-wrap">
                              {ESTADOS.map((est) => (
                                <button
                                  key={est}
                                  onClick={() => handleChangeEstado(entrega.id, est)}
                                  disabled={saving || est === entrega.estado}
                                  className={`px-2 py-0.5 rounded-full text-xs transition-colors disabled:opacity-40 ${
                                    est === entrega.estado
                                      ? ESTADO_CLASS[est]
                                      : "bg-cream border border-cream-dark hover:border-brot hover:text-brot"
                                  }`}
                                >
                                  {ESTADO_LABEL[est]}
                                </button>
                              ))}
                              <button
                                onClick={() => setChangingEstadoId(null)}
                                className="px-2 py-0.5 rounded-full text-xs text-warm-gray hover:text-text"
                              >
                                ×
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => { setChangingEstadoId(entrega.id); setDeleteConfirm(null); }}
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_CLASS[entrega.estado]} hover:opacity-80 transition-opacity`}
                            >
                              {ESTADO_LABEL[entrega.estado]}
                            </button>
                          )}
                        </td>
                        <td className="px-4 py-3 text-warm-gray text-sm">{entrega.notas ?? "—"}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => { setDeleteConfirm(entrega.id); setChangingEstadoId(null); }}
                            className="px-3 py-1.5 text-xs text-red-600 hover:text-red-700 transition-colors min-h-[36px]"
                          >
                            Eliminar
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {filtradas.map((entrega) => {
                if (deleteConfirm === entrega.id) {
                  return (
                    <div key={entrega.id} className="px-4 py-3 bg-red-50 flex items-center gap-3 flex-wrap">
                      <span className="text-sm flex-1">
                        ¿Eliminar entrega de <strong>{entrega.cliente_nombre}</strong>?
                      </span>
                      <button
                        onClick={() => handleDelete(entrega.id)}
                        disabled={saving}
                        className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm min-h-[44px] disabled:opacity-50"
                      >
                        {saving ? "..." : "Eliminar"}
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-3 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px]"
                      >
                        Cancelar
                      </button>
                    </div>
                  );
                }
                return (
                  <div key={entrega.id} className="px-4 py-4">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div>
                        <p className="font-medium text-text">{entrega.cliente_nombre}</p>
                        <p className="text-xs text-warm-gray mt-0.5">{formatDate(entrega.fecha)}</p>
                        {entrega.notas && (
                          <p className="text-xs text-warm-gray mt-0.5">{entrega.notas}</p>
                        )}
                      </div>
                      <button
                        onClick={() => { setDeleteConfirm(entrega.id); setChangingEstadoId(null); }}
                        className="text-xs text-red-600 min-h-[36px] shrink-0"
                      >
                        Eliminar
                      </button>
                    </div>
                    {changingEstadoId === entrega.id ? (
                      <div className="flex gap-1 flex-wrap mt-2">
                        {ESTADOS.map((est) => (
                          <button
                            key={est}
                            onClick={() => handleChangeEstado(entrega.id, est)}
                            disabled={saving || est === entrega.estado}
                            className={`px-2 py-0.5 rounded-full text-xs transition-colors disabled:opacity-40 ${
                              est === entrega.estado
                                ? ESTADO_CLASS[est]
                                : "bg-cream border border-cream-dark hover:border-brot hover:text-brot"
                            }`}
                          >
                            {ESTADO_LABEL[est]}
                          </button>
                        ))}
                        <button
                          onClick={() => setChangingEstadoId(null)}
                          className="px-2 py-0.5 rounded-full text-xs text-warm-gray"
                        >
                          ×
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setChangingEstadoId(entrega.id)}
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${ESTADO_CLASS[entrega.estado]}`}
                      >
                        {ESTADO_LABEL[entrega.estado]}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-cream-dark p-5">
        <h3 className="font-medium mb-4">Nueva entrega</h3>
        <form onSubmit={handleCreate}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Cliente <span className="text-red-500">*</span>
              </label>
              <select
                value={form.cliente_id}
                onChange={(e) => setForm({ ...form, cliente_id: e.target.value })}
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[42px]"
              >
                <option value="">— Seleccionar cliente —</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Fecha <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={form.fecha}
                onChange={(e) => setForm({ ...form, fecha: e.target.value })}
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            <div className="sm:col-span-2 lg:col-span-1">
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Notas
              </label>
              <input
                type="text"
                value={form.notas}
                onChange={(e) => setForm({ ...form, notas: e.target.value })}
                placeholder="Notas opcionales"
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
          </div>

          <div className="mt-4">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {saving ? "Creando..." : "Crear entrega"}
            </button>
          </div>
        </form>
      </div>

      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {filtradas.length} entrega{filtradas.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
