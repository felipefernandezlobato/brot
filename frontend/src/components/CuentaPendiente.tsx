"use client";

import { useState } from "react";
import { CustomerNav } from "@/components/CustomerNav";
import { useToast } from "@/components/Toast";
import { apiClienteFetch } from "@/lib/api-cliente";
import { Cliente } from "@/lib/types";

/** Lo que ve un cliente que se registró y todavía no puede pedir.
 *
 * Deliberadamente NO muestra catálogo ni precios: el motivo de poner una
 * aprobación es que registrarse no dé acceso a la lista de precios B2B. El
 * backend lo bloquea igual (`get_cliente_aprobado`), esto evita además que la
 * pantalla pida datos que le van a dar 403.
 *
 * Hay dos puertas y conviene decir cuál falta: si es la suya (confirmar el
 * correo) puede actuar; si es la de BROT, solo esperar. Mezclarlas dejaría al
 * cliente sin saber si la pelota está en su tejado.
 */
export function CuentaPendiente({ cliente }: { cliente: Cliente }) {
  const { toast } = useToast();
  const [reenviando, setReenviando] = useState(false);

  const reenviar = async () => {
    setReenviando(true);
    try {
      await apiClienteFetch("/api/auth/cliente/reenviar-verificacion", { method: "POST" });
      toast("Te enviamos el enlace de nuevo");
    } catch {
      toast("No se pudo enviar. Probá en un rato.", "error");
    } finally {
      setReenviando(false);
    }
  };

  const faltaVerificar = !cliente.email_verificado;

  return (
    <div className="min-h-screen bg-cream">
      <CustomerNav nombre={cliente.nombre} pendiente />
      <div className="max-w-xl mx-auto px-4 py-10">
        <div className="bg-card rounded-xl border border-cream-dark p-6">
          <h1 className="titulo text-xl text-text mb-4">
            {faltaVerificar ? "Confirmá tu correo" : "Estamos revisando tu alta"}
          </h1>

          {faltaVerificar ? (
            <>
              <p className="text-sm text-warm-gray leading-relaxed">
                Te enviamos un enlace a{" "}
                <span className="text-text">{cliente.email}</span>. Abrilo para
                confirmar que el correo es tuyo; hasta entonces no podemos dar
                de alta tu cuenta.
              </p>
              <p className="text-sm text-warm-gray leading-relaxed mt-3">
                Si no lo ves, mirá en la carpeta de spam.
              </p>
              <button
                onClick={reenviar}
                disabled={reenviando}
                className="mt-5 w-full py-3 bg-brot text-white rounded-lg font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]"
              >
                {reenviando ? "Enviando..." : "Enviarme el enlace otra vez"}
              </button>
            </>
          ) : (
            <>
              <p className="text-sm text-warm-gray leading-relaxed">
                Ya confirmaste tu correo, gracias. Ahora nos toca a nosotros:
                estamos revisando tu alta y te avisamos a{" "}
                <span className="text-text">{cliente.email}</span> en cuanto
                puedas empezar a pedir.
              </p>
              <p className="text-sm text-warm-gray leading-relaxed mt-3">
                No hace falta que hagas nada más.
              </p>
            </>
          )}

          <div className="mt-6 pt-5 border-t border-cream-dark">
            <h2 className="text-sm font-medium text-warm-gray mb-2">Tus datos</h2>
            <dl className="space-y-1.5 text-sm">
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
              {cliente.direccion && (
                <div className="flex justify-between gap-4">
                  <dt className="text-warm-gray">Dirección</dt>
                  <dd className="text-text text-right">{cliente.direccion}</dd>
                </div>
              )}
            </dl>
            <p className="text-xs text-warm-gray mt-4 leading-relaxed">
              ¿Algún dato mal? Escribinos y lo corregimos.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
