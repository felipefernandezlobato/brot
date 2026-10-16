"use client";

import { useState } from "react";
import Link from "next/link";
import { BrotLogo } from "@/components/BrotLogo";
import { apiPublicoFetch } from "@/lib/api-cliente";

export default function RecuperarPage() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(false);
  const [error, setError] = useState("");

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      await apiPublicoFetch("/api/auth/cliente/recuperar", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setListo(true);
    } catch {
      setError("No pudimos conectar. Intentá de nuevo en un momento.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center text-center">
        <BrotLogo variante="principal" color="crema" className="h-28 w-auto" />
        <p className="text-white/60 text-sm mt-3">Tienda en línea</p>
      </div>

      <div className="bg-card rounded-2xl shadow-xl p-8 w-full max-w-sm">
        {listo ? (
          /* El mismo mensaje exista o no el correo: el backend responde igual
             en los dos casos a proposito, y la pantalla no puede delatar la
             diferencia o cualquiera podria averiguar quienes son los clientes
             de BROT probando direcciones. */
          <>
            <h2 className="titulo text-xl text-text mb-3">Revisá tu correo</h2>
            <p className="text-sm text-warm-gray leading-relaxed">
              Si <span className="text-text">{email}</span> tiene una cuenta en
              el portal, te acabamos de enviar un enlace para elegir una
              contraseña nueva.
            </p>
            <p className="text-sm text-warm-gray leading-relaxed mt-3">
              El enlace vale una hora. Si no te llega en unos minutos, mirá en
              la carpeta de spam.
            </p>
            <Link
              href="/cliente/login"
              className="mt-6 block w-full py-3 bg-brot text-white rounded-lg font-medium text-center hover:bg-brot-dark transition-colors min-h-[44px]"
            >
              Volver a entrar
            </Link>
          </>
        ) : (
          <>
            <h2 className="titulo text-xl text-text mb-2">Recuperar contraseña</h2>
            <p className="text-sm text-warm-gray mb-6">
              Poné tu correo y te mandamos un enlace para elegir una nueva.
            </p>

            <form onSubmit={enviar} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-warm-gray mb-1">
                  Correo electrónico
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                  className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
                />
              </div>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
              )}

              <button
                type="submit"
                disabled={enviando}
                className="w-full py-3 bg-brot text-white rounded-lg font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]"
              >
                {enviando ? "Enviando..." : "Enviarme el enlace"}
              </button>
            </form>

            <p className="mt-5 text-center text-sm text-warm-gray">
              <Link href="/cliente/login" className="text-brot font-medium hover:underline">
                Volver a entrar
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
