"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

export function CustomerNav({ nombre }: { nombre?: string }) {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("brot_customer_token");
    router.push("/cliente/login");
  };

  const navLinks = [
    { href: "/cliente", label: "Inicio" },
    { href: "/cliente/pedidos", label: "Mis Pedidos" },
    { href: "/cliente/recurrentes", label: "Recurrentes" },
  ];

  return (
    <header className="bg-brot text-white shadow-md">
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Logo */}
        <Link
          href="/cliente"
          className="font-[family-name:var(--font-garamond)] text-2xl tracking-wide"
        >
          BROT
        </Link>

        {/* Nav links */}
        <nav className="hidden sm:flex items-center gap-1">
          {navLinks.map((link) => {
            const active =
              link.href === "/cliente"
                ? pathname === "/cliente"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  active
                    ? "bg-white/20 text-white font-medium"
                    : "text-white/70 hover:text-white hover:bg-white/10"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-3">
          {nombre && (
            <span className="hidden sm:block text-sm text-white/70 truncate max-w-[120px]">
              {nombre}
            </span>
          )}
          <button
            onClick={handleLogout}
            className="text-sm text-white/80 hover:text-white transition-colors min-h-[36px] px-2"
          >
            Salir
          </button>
        </div>
      </div>

      {/* Mobile nav */}
      <nav className="sm:hidden flex border-t border-white/10">
        {navLinks.map((link) => {
          const active =
            link.href === "/cliente"
              ? pathname === "/cliente"
              : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex-1 text-center py-2 text-xs transition-colors ${
                active
                  ? "text-white font-medium border-b-2 border-white"
                  : "text-white/60 hover:text-white"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
