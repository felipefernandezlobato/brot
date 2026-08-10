"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { User } from "@/lib/types";

interface Props {
  children: (user: User) => React.ReactNode;
}

export function AuthGuard({ children }: Props) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const pathname = usePathname();
  const router = useRouter();

  const isPublic = pathname === "/login" || pathname.startsWith("/cliente");

  useEffect(() => {
    if (isPublic) {
      setLoading(false);
      return;
    }
    const token = localStorage.getItem("brot_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    apiFetch<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("brot_token");
        router.replace("/login");
      })
      .finally(() => setLoading(false));
  }, [isPublic, router]);

  if (isPublic) return <>{(children as any)}</>;
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-warm-gray">Cargando...</p>
      </div>
    );
  }
  if (!user) return null;
  return <>{children(user)}</>;
}
