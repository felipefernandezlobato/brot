"use client";

import { usePathname } from "next/navigation";
import { AuthGuard } from "@/components/AuthGuard";
import { Sidebar } from "@/components/Sidebar";
import { BottomNav } from "@/components/BottomNav";
import { ToastProvider } from "@/components/Toast";
import { User } from "@/lib/types";

export function AppShell({
  children,
}: {
  children: ((user: User) => React.ReactNode) | React.ReactNode;
}) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";
  const isCliente = pathname.startsWith("/cliente");

  if (isLogin || isCliente) {
    return <ToastProvider>{children as React.ReactNode}</ToastProvider>;
  }

  return (
    <ToastProvider>
      <AuthGuard>
        {(user) => (
          <>
            <Sidebar role={user.role} />
            <BottomNav role={user.role} />
            <main className="flex-1 md:ml-56 pb-24 md:pb-0">
              <div className="max-w-6xl mx-auto px-4 py-6">
                {typeof children === "function" ? children(user) : children}
              </div>
            </main>
          </>
        )}
      </AuthGuard>
    </ToastProvider>
  );
}
