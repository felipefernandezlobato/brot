"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { User } from "@/lib/types";

const TABS = [
  { href: "/admin/equipo", label: "Equipo" },
  { href: "/admin/permisos", label: "Permisos" },
  { href: "/admin/categorias", label: "Categorías" },
  { href: "/admin/catalogo", label: "Catálogo" },
  { href: "/admin/pedidos-clientes", label: "Pedidos Clientes" },
  { href: "/admin/protocolos", label: "Protocolos" },
  { href: "/admin/importar", label: "Importar" },
  { href: "/admin/configuracion", label: "Configuración" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const pathname = usePathname();

  useEffect(() => {
    apiFetch<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-warm-gray">Cargando...</p>
      </div>
    );
  }

  if (!user || user.role !== "admin") {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
        <div className="text-4xl">🔒</div>
        <p className="text-xl font-medium text-text">Acceso denegado</p>
        <p className="text-sm text-warm-gray">
          Solo los administradores pueden acceder a esta sección.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Page heading */}
      <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mb-4">
        Administración
      </h1>

      {/* Tab navigation — sticky below AppShell content area top */}
      <nav className="sticky top-0 bg-cream z-30 -mx-4 px-4 border-b border-cream-dark mb-6">
        <div className="flex gap-0 overflow-x-auto">
          {TABS.map((tab) => {
            const active = pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`flex-shrink-0 px-5 py-3 text-sm font-medium border-b-2 transition-colors min-h-[44px] flex items-center ${
                  active
                    ? "border-brot text-brot"
                    : "border-transparent text-warm-gray hover:text-text hover:border-cream-dark"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {children}
    </div>
  );
}
