"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { BrotLogo } from "@/components/BrotLogo";
import { apiPublicoFetch } from "@/lib/api-cliente";

const MINIMO = 8;

function Formulario() {
  const token = useSearchParams().get("token") || "";
  const [password, setPassword] = useState("");
  const [repetir, setRepetir] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const corta = password.length > 0 && password.length < MINIMO;
  const noCoinciden = repetir.length > 0 && password !== repetir;
  const puedeGuardar = password.length >= MINIMO && password === repetir && !guardando;

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setGuardando(true);
    try {
      const { token: sesion } = await apiPublicoFetch<{ token: string }>(
        "/api/auth/cliente/establecer",
        { method: "POST", body: JSON.stringify({ token, password }) }
      );
      // El backend devuelve ya la sesion iniciada, asi que entra directo sin
      // volver a escribir el correo que acaba de usar para llegar aca.
      localStorage.setItem("brot_customer_token", sesion);
      window.location.href = "/cliente";
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo guardar la contraseña.");
      setGuardando(false);
    }
  };

  if (!token) {
    return (
      <>
        <h2 className="titulo text-xl text-text mb-3">Enlace incompleto</h2>
        <p className="text-sm text-warm-gray leading-relaxed">
          Este enlace no trae la información necesaria. Copialo entero desde el
          correo, o pedí uno nuevo.
        </p>
        <Link
          href="/cliente/recuperar"
          className="mt-6 block w-full py-3 bg-brot text-white rounded-lg font-medium text-center hover:bg-brot-dark transition-colors min-h-[44px]"
        >
          Pedir un enlace nuevo
        </Link>
      </>
    );
  }

  return (
    <>
      <h2 className="titulo text-xl text-text mb-2">Elegí tu contraseña</h2>
      <p className="text-sm text-warm-gray mb-6">
        Con ella vas a entrar al portal de pedidos de BROT.
      </p>

      <form onSubmit={guardar} className="space-y-4">
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-warm-gray mb-1">
            Contraseña nueva
          </label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
          />
          <p className={`text-xs mt-1 ${corta ? "text-red-600" : "text-warm-gray"}`}>
            Mínimo {MINIMO} caracteres.
          </p>
        </div>

        <div>
          <label htmlFor="repetir" className="block text-sm font-medium text-warm-gray mb-1">
            Repetila
          </label>
          <input
            id="repetir"
            type="password"
            autoComplete="new-password"
            required
            value={repetir}
            onChange={(e) => setRepetir(e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
          />
          {noCoinciden && <p className="text-xs mt-1 text-red-600">No coinciden.</p>}
        </div>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
            <p>{error}</p>
            <Link href="/cliente/recuperar" className="underline font-medium">
              Pedir un enlace nuevo
            </Link>
          </div>
        )}

        <button
          type="submit"
          disabled={!puedeGuardar}
          className="w-full py-3 bg-brot text-white rounded-lg font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]"
        >
          {guardando ? "Guardando..." : "Guardar y entrar"}
        </button>
      </form>
    </>
  );
}

export default function EstablecerPage() {
  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center text-center">
        <BrotLogo variante="principal" color="crema" className="h-28 w-auto" />
        <p className="text-white/60 text-sm mt-3">Tienda en línea</p>
      </div>
      <div className="bg-card rounded-2xl shadow-xl p-8 w-full max-w-sm">
        {/* useSearchParams obliga a un limite de Suspense en el App Router o
            el build falla al prerenderizar la pagina. */}
        <Suspense fallback={<p className="text-sm text-warm-gray">Cargando...</p>}>
          <Formulario />
        </Suspense>
      </div>
    </div>
  );
}
