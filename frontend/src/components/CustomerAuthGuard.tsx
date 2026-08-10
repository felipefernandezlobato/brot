"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClienteFetch } from "@/lib/api-cliente";
import { Cliente } from "@/lib/types";

interface Props {
  children: (cliente: Cliente) => React.ReactNode;
}

export function CustomerAuthGuard({ children }: Props) {
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("brot_customer_token");
    if (!token) {
      router.replace("/cliente/login");
      return;
    }
    apiClienteFetch<Cliente>("/api/auth/cliente/me")
      .then(setCliente)
      .catch(() => {
        localStorage.removeItem("brot_customer_token");
        router.replace("/cliente/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-cream">
        <p className="text-warm-gray">Cargando...</p>
      </div>
    );
  }
  if (!cliente) return null;
  return <>{children(cliente)}</>;
}
