"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Inicio" },
  { href: "/ingredientes", label: "Ingredientes" },
  { href: "/escandallos", label: "Escandallos" },
  { href: "/proveedores", label: "Proveedores" },
  // Mismo orden que Sidebar.tsx -- si cambia uno, cambiar el otro.
  { href: "/pedidos", label: "Compras" },
  { href: "/stock", label: "Stock MP" },
  { href: "/produccion", label: "Produccion" },
  { href: "/mermas", label: "Mermas" },
  { href: "/congelados", label: "Congelado" },
  { href: "/entregas", label: "Entregas" },
  { href: "/protocolos", label: "Protocolos" },
  { href: "/competencia", label: "Competencia", admin: true },
  { href: "/admin", label: "Admin", admin: true },
];

export function BottomNav({ role }: { role: string }) {
  const pathname = usePathname();
  const items = NAV_ITEMS.filter((item) => !item.admin || role === "admin");

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-cream-dark z-40 pb-[env(safe-area-inset-bottom)]">
      {/* Scrollable, NOT justify-around. 13 items at 64px minimum need 832px
          and a phone is 390: with the old `flex justify-around` and no
          overflow the last six (Produccion onwards, Competencia and Admin
          included) rendered off-screen and were simply unreachable on a
          phone -- nothing scrolled them into view. `justify-around` must not
          come back here either: on an overflowing flex row it pushes the
          first item off the left edge too, where scrolling can't reach it. */}
      <div className="flex overflow-x-auto">
        {items.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex shrink-0 flex-col items-center justify-center py-2 px-3 min-w-[64px] min-h-[44px] ${
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
