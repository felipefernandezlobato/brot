"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Inicio", icon: "🏠" },
  { href: "/ingredientes", label: "Ingredientes", icon: "🧂" },
  { href: "/stock", label: "Stock", icon: "📦" },
  { href: "/escandallos", label: "Escandallos", icon: "📋" },
  { href: "/proveedores", label: "Proveedores", icon: "🏪" },
  { href: "/pedidos", label: "Pedidos", icon: "🛒" },
  { href: "/mermas", label: "Mermas", icon: "♻️" },
  { href: "/produccion", label: "Producción", icon: "🏭" },
  { href: "/congelados", label: "Congelados", icon: "❄️" },
  { href: "/entregas", label: "Entregas B2B", icon: "🚚" },
  { href: "/protocolos", label: "Protocolos", icon: "✅" },
  { href: "/competencia", label: "Competencia", icon: "🏷️", admin: true },
  { href: "/admin", label: "Admin", icon: "⚙️", admin: true },
];

export function Sidebar({ role }: { role: string }) {
  const pathname = usePathname();

  const items = NAV_ITEMS.filter((item) => !item.admin || role === "admin");

  return (
    <aside className="hidden md:flex fixed left-0 top-0 bottom-0 w-56 bg-brot flex-col z-40">
      <div className="p-4 border-b border-white/10">
        <h1 className="font-[family-name:var(--font-garamond)] text-2xl text-white tracking-wider">
          BROT
        </h1>
        <p className="text-white/60 text-xs mt-1">La Panadería</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-white/15 text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-white/10">
        <button
          onClick={() => {
            localStorage.removeItem("brot_token");
            window.location.href = "/login";
          }}
          className="w-full text-left px-3 py-2 text-white/60 hover:text-white text-sm"
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
