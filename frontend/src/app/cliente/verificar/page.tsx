"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BrotLogo } from "@/components/BrotLogo";
import { apiPublicoFetch } from "@/lib/api-cliente";

type Estado = "verificando" | "ok" | "error";

function Verificacion() {
  const token = useSearchParams().get("token") || "";
  const [estado, setEstado] = useState<Estado>("verificando");

  useEffect(() => {
    if (!token) {
      setEstado("error");
      return;
    }
    apiPublicoFetch("/api/auth/cliente/verificar", {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then(() => setEstado("ok"))
      .catch(() => setEstado("error"));
  }, [token]);

  if (estado === "verificando") {
    return <p className="text-sm text-warm-gray">Confirmando tu correo...</p>;
  }

  if (estado === "error") {
    return (
      <>
        <h2 className="titulo text-xl text-text mb-3">No pudimos confirmarlo</h2>
        <p className="text-sm text-warm-gray leading-relaxed">
          El enlace no es válido o ya se usó. Si ya confirmaste antes, no hace
          falta que lo hagas otra vez: entrá y mirá el estado de tu cuenta.
        </p>
        <Link
          href="/cliente"
          className="mt-6 block w-full py-3 bg-brot text-white rounded-lg font-medium text-center hover:bg-brot-dark transition-colors min-h-[44px]"
        >
          Entrar
        </Link>
      </>
    );
  }

  return (
    <>
      <h2 className="titulo text-xl text-text mb-3">Correo confirmado</h2>
      <p className="text-sm text-warm-gray leading-relaxed">
        Gracias. Ahora revisamos tu alta y te avisamos por correo en cuanto
        puedas empezar a pedir.
      </p>
      <Link
        href="/cliente"
        className="mt-6 block w-full py-3 bg-brot text-white rounded-lg font-medium text-center hover:bg-brot-dark transition-colors min-h-[44px]"
      >
        Ir a mi cuenta
      </Link>
    </>
  );
}

export default function VerificarPage() {
  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center text-center">
        <BrotLogo variante="principal" color="crema" className="h-28 w-auto" />
        <p className="text-white/60 text-sm mt-3">Tienda en línea</p>
      </div>
      <div className="bg-card rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <Suspense fallback={<p className="text-sm text-warm-gray">Cargando...</p>}>
          <Verificacion />
        </Suspense>
      </div>
    </div>
  );
}
