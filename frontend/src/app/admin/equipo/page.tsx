"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface UsuarioBasico {
  id: number;
  name: string;
}

export default function EquipoPage() {
  const [usuarios, setUsuarios] = useState<UsuarioBasico[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [nombre, setNombre] = useState("");
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    apiFetch<UsuarioBasico[]>("/api/auth/users")
      .then(setUsuarios)
      .catch(() => toast("Error al cargar usuarios", "error"))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    // API endpoint not yet implemented — placeholder
    setSaving(true);
    await new Promise((r) => setTimeout(r, 300));
    setSaving(false);
    toast("El endpoint de creación de usuarios estará disponible próximamente", "error");
  };

  const initials = (name: string) => name.trim()[0]?.toUpperCase() ?? "?";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Equipo
        </h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors"
        >
          + Nuevo Usuario
        </button>
      </div>

      {/* Create form (placeholder — API not yet available) */}
      {showForm && (
        <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
          <h3 className="font-medium mb-4">Nuevo Usuario</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-warm-gray mb-1">
                Nombre
              </label>
              <input
                type="text"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Nombre del usuario"
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <p className="text-xs text-warm-gray bg-cream rounded-lg px-3 py-2">
              El PIN, rol y permisos se asignarán una vez el endpoint de creación esté disponible.
            </p>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
              >
                {saving ? "Guardando..." : "Crear Usuario"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setNombre("");
                }}
                className="px-4 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream-dark transition-colors"
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* User list */}
      {loading ? (
        <p className="text-warm-gray py-8 text-center">Cargando equipo...</p>
      ) : usuarios.length === 0 ? (
        <div className="text-center py-12 text-warm-gray">
          <p className="text-lg">Sin usuarios registrados</p>
          <p className="text-sm mt-1">Añade el primer usuario con el botón de arriba.</p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {usuarios.map((u) => (
            <div
              key={u.id}
              className="flex items-center gap-4 bg-white rounded-xl border border-cream-dark p-4"
            >
              {/* Avatar */}
              <div className="w-11 h-11 rounded-full bg-brot flex items-center justify-center text-white font-semibold text-lg flex-shrink-0">
                {initials(u.name)}
              </div>
              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="font-medium text-text truncate">{u.name}</p>
                <p className="text-xs text-warm-gray">ID: {u.id}</p>
              </div>
              {/* Placeholder actions — will connect when API is ready */}
              <div className="flex flex-col gap-1 text-right">
                <button
                  disabled
                  title="Próximamente"
                  className="text-xs text-warm-gray/50 cursor-not-allowed"
                >
                  Editar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
