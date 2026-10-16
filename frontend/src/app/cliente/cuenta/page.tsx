"use client";

import { useState } from "react";
import { CustomerAuthGuard } from "@/components/CustomerAuthGuard";
import { CustomerNav } from "@/components/CustomerNav";
import { useToast } from "@/components/Toast";
import { apiClienteFetch } from "@/lib/api-cliente";
import { Cliente } from "@/lib/types";

const MINIMO = 8;

/** El cliente llega del guard, que ya pidio /me para dejarnos pasar. Pedirlo
 *  otra vez aqui serian dos llamadas identicas en la misma carga. */
function Cuenta({ cliente }: { cliente: Cliente }) {
  const { toast } = useToast();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetir, setRepetir] = useState("");
  const [guardando, setGuardando] = useState(false);

  const corta = nueva.length > 0 && nueva.length < MINIMO;
  const noCoinciden = repetir.length > 0 && nueva !== repetir;
  const puede = actual.length > 0 && nueva.length >= MINIMO && nueva === repetir && !guardando;

  const guardar = async (e: React.FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    try {
      await apiClienteFetch("/api/auth/cliente/cambiar-password", {
        method: "POST",
        body: JSON.stringify({ actual, nueva }),
      });
      toast("Contraseña actualizada", "success");
      setActual("");
      setNueva("");
      setRepetir("");
    } catch (e) {
      // "La contraseña actual no es correcta" llega como 422, no 401: el
      // backend lo devuelve asi justamente porque apiClienteFetch echa al
      // login ante cualquier 401, y teclear mal la contraseña no puede
      // cerrarte la sesion.
      toast(e instanceof Error ? e.message : "No se pudo cambiar", "error");
    } finally {
      setGuardando(false);
    }
  };

  const input =
    "w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text";

  return (
    <div className="max-w-xl mx-auto px-4 py-6 space-y-6">
      <h1 className="titulo text-2xl text-text">Mi cuenta</h1>

      <section className="bg-card rounded-xl border border-cream-dark p-5">
        <h2 className="text-sm font-medium text-warm-gray mb-3">Tus datos</h2>
        <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-warm-gray">Nombre</dt>
              <dd className="text-text text-right">{cliente.nombre}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-warm-gray">Correo</dt>
              <dd className="text-text text-right break-all">{cliente.email}</dd>
            </div>
            {cliente.telefono && (
              <div className="flex justify-between gap-4">
                <dt className="text-warm-gray">Teléfono</dt>
                <dd className="text-text text-right">{cliente.telefono}</dd>
              </div>
            )}
        </dl>
        <p className="text-xs text-warm-gray mt-4 leading-relaxed">
          Para cambiar tu nombre, dirección o teléfono, escribinos y lo
          actualizamos.
        </p>
      </section>

      <section className="bg-card rounded-xl border border-cream-dark p-5">
        <h2 className="text-sm font-medium text-warm-gray mb-4">Cambiar contraseña</h2>
        <form onSubmit={guardar} className="space-y-4">
          <div>
            <label htmlFor="actual" className="block text-sm text-warm-gray mb-1">
              Contraseña actual
            </label>
            <input
              id="actual"
              type="password"
              autoComplete="current-password"
              required
              value={actual}
              onChange={(e) => setActual(e.target.value)}
              className={input}
            />
          </div>

          <div>
            <label htmlFor="nueva" className="block text-sm text-warm-gray mb-1">
              Contraseña nueva
            </label>
            <input
              id="nueva"
              type="password"
              autoComplete="new-password"
              required
              value={nueva}
              onChange={(e) => setNueva(e.target.value)}
              className={input}
            />
            <p className={`text-xs mt-1 ${corta ? "text-red-600" : "text-warm-gray"}`}>
              Mínimo {MINIMO} caracteres.
            </p>
          </div>

          <div>
            <label htmlFor="repetir" className="block text-sm text-warm-gray mb-1">
              Repetila
            </label>
            <input
              id="repetir"
              type="password"
              autoComplete="new-password"
              required
              value={repetir}
              onChange={(e) => setRepetir(e.target.value)}
              className={input}
            />
            {noCoinciden && <p className="text-xs mt-1 text-red-600">No coinciden.</p>}
          </div>

          <button
            type="submit"
            disabled={!puede}
            className="w-full py-3 bg-brot text-white rounded-lg font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]"
          >
            {guardando ? "Guardando..." : "Cambiar contraseña"}
          </button>
        </form>
      </section>
    </div>
  );
}

export default function CuentaPage() {
  return (
    <CustomerAuthGuard>
      {(cliente) => (
        <div className="min-h-screen bg-cream">
          <CustomerNav nombre={cliente.nombre} />
          <Cuenta cliente={cliente} />
        </div>
      )}
    </CustomerAuthGuard>
  );
}
