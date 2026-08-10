"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Permission } from "@/lib/types";
import { useToast } from "@/components/Toast";

const ACTIONS: { key: string; label: string }[] = [
  { key: "view", label: "Ver" },
  { key: "create", label: "Crear" },
  { key: "edit", label: "Editar" },
  { key: "delete", label: "Eliminar" },
];

// Module groupings — keys should match the `module` values from the API
const GROUPS: { label: string; modules: string[] }[] = [
  { label: "Inventario", modules: ["ingredientes", "categorias"] },
  { label: "Producción", modules: ["escandallos", "recetas"] },
  { label: "Ventas", modules: ["pedidos", "clientes"] },
  { label: "Administración", modules: ["usuarios", "permisos"] },
];

interface ToggleSwitchProps {
  enabled: boolean;
  loading: boolean;
  label: string;
  onToggle: () => void;
}

function ToggleSwitch({ enabled, loading, label, onToggle }: ToggleSwitchProps) {
  return (
    <button
      onClick={onToggle}
      disabled={loading}
      aria-label={label}
      className={`relative inline-flex w-11 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-brot/40 ${
        enabled ? "bg-brot" : "bg-cream-dark"
      } ${loading ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
    >
      <span
        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
          enabled ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

export default function PermisosPage() {
  const [permisos, setPermisos] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    apiFetch<Permission[]>("/api/permisos")
      .then(setPermisos)
      .catch(() => toast("Error al cargar permisos", "error"))
      .finally(() => setLoading(false));
  }, []);

  const getPerm = (module: string, action: string): Permission | undefined =>
    permisos.find((p) => p.module === module && p.action === action);

  const handleToggle = async (perm: Permission) => {
    if (savingId !== null) return;
    const newValue = !perm.allowed;
    setSavingId(perm.id);
    try {
      await apiFetch(`/api/permisos/${perm.id}`, {
        method: "PUT",
        body: JSON.stringify({ allowed: newValue }),
      });
      setPermisos((prev) =>
        prev.map((p) => (p.id === perm.id ? { ...p, allowed: newValue } : p))
      );
      toast(newValue ? "Permiso activado" : "Permiso desactivado");
    } catch {
      toast("Error al actualizar permiso", "error");
    } finally {
      setSavingId(null);
    }
  };

  // Determine which modules exist in the API response
  const knownModules = new Set(permisos.map((p) => p.module));

  // Split into grouped + ungrouped
  const groupedModules = new Set(GROUPS.flatMap((g) => g.modules));
  const extraModules = [...knownModules].filter((m) => !groupedModules.has(m));

  const allGroups = [
    ...GROUPS.map((g) => ({
      ...g,
      modules: g.modules.filter((m) => knownModules.has(m)),
    })).filter((g) => g.modules.length > 0),
    ...(extraModules.length > 0
      ? [{ label: "Otros", modules: extraModules }]
      : []),
  ];

  if (loading) {
    return (
      <p className="text-warm-gray py-8 text-center">Cargando permisos...</p>
    );
  }

  if (permisos.length === 0) {
    return (
      <div className="text-center py-12 text-warm-gray">
        <p className="text-lg">Sin permisos configurados</p>
        <p className="text-sm mt-1">
          Ejecuta el seed de permisos en el backend para inicializar la matriz.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Permisos
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Matriz de permisos para el rol <strong>staff</strong>. Los administradores tienen acceso completo.
        </p>
      </div>

      <div className="space-y-6">
        {allGroups.map((group) => (
          <div
            key={group.label}
            className="bg-white rounded-xl border border-cream-dark overflow-hidden"
          >
            {/* Group header */}
            <div className="px-4 py-2.5 bg-cream-dark">
              <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
                {group.label}
              </h3>
            </div>

            {/* Matrix table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark">
                    <th className="text-left px-4 py-2 font-medium text-warm-gray w-1/3 min-w-[120px]">
                      Módulo
                    </th>
                    {ACTIONS.map((a) => (
                      <th
                        key={a.key}
                        className="px-4 py-2 font-medium text-warm-gray text-center min-w-[80px]"
                      >
                        {a.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {group.modules.map((module) => (
                    <tr
                      key={module}
                      className="border-b border-cream-dark last:border-0 hover:bg-cream/50 transition-colors"
                    >
                      <td className="px-4 py-3 capitalize font-medium text-text">
                        {module}
                      </td>
                      {ACTIONS.map((a) => {
                        const perm = getPerm(module, a.key);
                        return (
                          <td key={a.key} className="px-4 py-3 text-center">
                            {perm ? (
                              <div className="flex justify-center">
                                <ToggleSwitch
                                  enabled={perm.allowed}
                                  loading={savingId === perm.id}
                                  label={`${perm.allowed ? "Desactivar" : "Activar"} ${module} — ${a.label}`}
                                  onToggle={() => handleToggle(perm)}
                                />
                              </div>
                            ) : (
                              <span className="text-warm-gray/30 text-lg select-none">
                                —
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
