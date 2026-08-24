"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface UsuarioBasico {
  id: number;
  name: string;
}

interface UsuarioCreado {
  id: number;
  name: string;
  role: string;
}

export default function EquipoPage() {
  const [usuarios, setUsuarios] = useState<UsuarioBasico[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [nombre, setNombre] = useState("");
  const [pin, setPin] = useState("");
  const [rol, setRol] = useState<"staff" | "admin">("staff");
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const reload = () => {
    setLoading(true);
    apiFetch<UsuarioBasico[]>("/api/auth/users")
      .then(setUsuarios)
      .catch(() => toast("Error al cargar usuarios", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    reload();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await apiFetch<UsuarioCreado>("/api/auth/users", {
        method: "POST",
        body: JSON.stringify({ name: nombre.trim(), pin, role: rol }),
      });
      toast("Usuario creado");
      setShowForm(false);
      setNombre("");
      setPin("");
      setRol("staff");
      reload();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al crear usuario", "error");
    } finally {
      setSaving(false);
    }
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

      {/* Create form */}
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
            <div>
              <label className="block text-sm font-medium text-warm-gray mb-1">
                PIN (4 dígitos)
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
                placeholder="1234"
                required
                pattern="\d{4}"
                maxLength={4}
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-warm-gray mb-1">
                Rol
              </label>
              <select
                value={rol}
                onChange={(e) => setRol(e.target.value as "staff" | "admin")}
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30"
              >
                <option value="staff">Staff</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving || pin.length !== 4}
                className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
              >
                {saving ? "Guardando..." : "Crear Usuario"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setNombre("");
                  setPin("");
                  setRol("staff");
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
