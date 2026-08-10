"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Inicio" },
  { href: "/ingredientes", label: "Ingredientes" },
  { href: "/stock", label: "Stock" },
  { href: "/escandallos", label: "Escandallos" },
  { href: "/proveedores", label: "Proveedores" },
  { href: "/pedidos", label: "Pedidos" },
  { href: "/mermas", label: "Mermas" },
  { href: "/produccion", label: "Producción" },
  { href: "/congelados", label: "Congelados" },
  { href: "/entregas", label: "Entregas" },
  { href: "/protocolos", label: "Protocolos" },
  { href: "/admin", label: "Admin", admin: true },
];

export function BottomNav({ role }: { role: string }) {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((item) => !item.admin || role === "admin");

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-cream-dark z-40 pb-[env(safe-area-inset-bottom)]">
      <div className="flex justify-around">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-col items-center py-2 px-3 min-w-[64px] min-h-[44px] ${
                active ? "text-brot" : "text-warm-gray"
              }`}
            >
              <span className="text-[10px]">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
