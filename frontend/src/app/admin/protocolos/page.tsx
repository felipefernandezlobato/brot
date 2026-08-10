"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

// ── Types ──────────────────────────────────────────────────────────────────

interface ProtocoloTemplate {
  id: number;
  nombre: string;
  tipo: string;
  seccion: string;
  orden: number;
  activo: boolean;
}

const TIPOS = ["apertura", "cierre", "semanal", "mensual"] as const;
type Tipo = (typeof TIPOS)[number];

const TIPO_LABELS: Record<Tipo, string> = {
  apertura: "Apertura",
  cierre: "Cierre",
  semanal: "Semanal",
  mensual: "Mensual",
};

const EMPTY_FORM: Omit<ProtocoloTemplate, "id"> = {
  nombre: "",
  tipo: "apertura",
  seccion: "General",
  orden: 0,
  activo: true,
};

// ── Page ───────────────────────────────────────────────────────────────────

export default function AdminProtocolosPage() {
  const { toast } = useToast();
  const [templates, setTemplates] = useState<ProtocoloTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState<Tipo | "all">("all");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<ProtocoloTemplate | null>(null);
  const [form, setForm] = useState<Omit<ProtocoloTemplate, "id">>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    apiFetch<ProtocoloTemplate[]>("/api/protocolos/templates")
      .then(setTemplates)
      .catch(() => toast("Error al cargar plantillas", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  const openEdit = (t: ProtocoloTemplate) => {
    setEditing(t);
    setForm({
      nombre: t.nombre,
      tipo: t.tipo,
      seccion: t.seccion,
      orden: t.orden,
      activo: t.activo,
    });
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY_FORM);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.nombre.trim()) return;
    setSaving(true);
    try {
      if (editing) {
        await apiFetch(`/api/protocolos/templates/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(form),
        });
        toast("Plantilla actualizada");
      } else {
        await apiFetch("/api/protocolos/templates", {
          method: "POST",
          body: JSON.stringify(form),
        });
        toast("Plantilla creada");
      }
      closeForm();
      load();
    } catch {
      toast("Error al guardar", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (t: ProtocoloTemplate) => {
    if (!confirm(`¿Eliminar la plantilla "${t.nombre}"?`)) return;
    try {
      await apiFetch(`/api/protocolos/templates/${t.id}`, {
        method: "DELETE",
      });
      toast("Plantilla eliminada");
      load();
    } catch {
      toast("Error al eliminar", "error");
    }
  };

  const handleToggleActivo = async (t: ProtocoloTemplate) => {
    try {
      await apiFetch(`/api/protocolos/templates/${t.id}`, {
        method: "PUT",
        body: JSON.stringify({ ...t, activo: !t.activo }),
      });
      load();
    } catch {
      toast("Error al actualizar estado", "error");
    }
  };

  const filtered =
    filtroTipo === "all"
      ? templates
      : templates.filter((t) => t.tipo === filtroTipo);

  // Group by tipo
  const byTipo = filtered.reduce<Record<string, ProtocoloTemplate[]>>(
    (acc, t) => {
      if (!acc[t.tipo]) acc[t.tipo] = [];
      acc[t.tipo].push(t);
      return acc;
    },
    {}
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Plantillas de Protocolos
        </h2>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors"
        >
          + Nueva Plantilla
        </button>
      </div>

      {/* Type filter */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setFiltroTipo("all")}
          className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
            filtroTipo === "all"
              ? "bg-brot text-white"
              : "bg-white text-warm-gray border border-cream-dark hover:bg-cream"
          }`}
        >
          Todas
        </button>
        {TIPOS.map((t) => (
          <button
            key={t}
            onClick={() => setFiltroTipo(t)}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              filtroTipo === t
                ? "bg-brot text-white"
                : "bg-white text-warm-gray border border-cream-dark hover:bg-cream"
            }`}
          >
            {TIPO_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Create / Edit form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
          <h3 className="font-medium mb-4">
            {editing ? "Editar Plantilla" : "Nueva Plantilla"}
          </h3>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Nombre */}
            <div>
              <label className="block text-sm font-medium text-warm-gray mb-1">
                Nombre *
              </label>
              <input
                type="text"
                required
                value={form.nombre}
                onChange={(e) =>
                  setForm((f) => ({ ...f, nombre: e.target.value }))
                }
                placeholder="Descripción de la tarea"
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            {/* Tipo + Sección */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-warm-gray mb-1">
                  Tipo
                </label>
                <select
                  value={form.tipo}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, tipo: e.target.value }))
                  }
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
                >
                  {TIPOS.map((t) => (
                    <option key={t} value={t}>
                      {TIPO_LABELS[t]}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-warm-gray mb-1">
                  Sección
                </label>
                <input
                  type="text"
                  value={form.seccion}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, seccion: e.target.value }))
                  }
                  placeholder="General"
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
            </div>

            {/* Orden */}
            <div>
              <label className="block text-sm font-medium text-warm-gray mb-1">
                Orden
              </label>
              <input
                type="number"
                value={form.orden}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    orden: parseInt(e.target.value) || 0,
                  }))
                }
                className="w-28 px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            {/* Activo */}
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="activo-check"
                checked={form.activo}
                onChange={(e) =>
                  setForm((f) => ({ ...f, activo: e.target.checked }))
                }
                className="w-4 h-4 accent-brot"
              />
              <label
                htmlFor="activo-check"
                className="text-sm text-warm-gray select-none"
              >
                Plantilla activa
              </label>
            </div>

            {/* Actions */}
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
              >
                {saving
                  ? "Guardando…"
                  : editing
                    ? "Actualizar"
                    : "Crear Plantilla"}
              </button>
              <button
                type="button"
                onClick={closeForm}
                className="px-4 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark transition-colors"
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Template list */}
      {loading ? (
        <div className="py-12 text-center text-warm-gray text-sm">
          Cargando plantillas…
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-warm-gray text-sm">
            {templates.length === 0
              ? "No hay plantillas. Crea la primera con el botón de arriba."
              : "Sin plantillas para este tipo."}
          </p>
        </div>
      ) : (
        Object.entries(byTipo).map(([tipo, tipoItems]) => (
          <div key={tipo} className="mb-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-warm-gray mb-2 px-1">
              {TIPO_LABELS[tipo as Tipo] ?? tipo}
              <span className="ml-1.5 font-normal normal-case">
                ({tipoItems.length})
              </span>
            </h3>
            <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
              {tipoItems
                .slice()
                .sort((a, b) => a.orden - b.orden)
                .map((t, idx) => (
                  <div
                    key={t.id}
                    className={`flex items-center gap-3 px-4 py-3 ${
                      idx < tipoItems.length - 1 ? "border-b border-cream" : ""
                    } ${!t.activo ? "opacity-50" : ""}`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text">
                        {t.nombre}
                      </p>
                      <p className="text-xs text-warm-gray">
                        {t.seccion} · orden {t.orden}
                        {!t.activo && " · inactiva"}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={() => handleToggleActivo(t)}
                        className={`text-xs px-2 py-1 rounded transition-colors min-h-[30px] ${
                          t.activo
                            ? "text-brot hover:bg-cream"
                            : "text-warm-gray hover:bg-cream"
                        }`}
                      >
                        {t.activo ? "Activa" : "Inactiva"}
                      </button>
                      <button
                        onClick={() => openEdit(t)}
                        className="text-xs px-2 py-1 rounded text-warm-gray hover:text-text hover:bg-cream transition-colors min-h-[30px]"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => handleDelete(t)}
                        className="text-xs px-2 py-1 rounded text-red-600 hover:bg-red-50 transition-colors min-h-[30px]"
                      >
                        Eliminar
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
