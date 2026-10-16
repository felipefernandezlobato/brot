"use client";

import Link from "next/link";
import { BrotLogo } from "@/components/BrotLogo";

/** El alta abierta se cerro el 2026-10-16.
 *
 * La pagina se queda en lugar de borrarse porque la ruta puede estar en un
 * marcador o en un mensaje viejo, y un 404 no le explica nada a nadie. El
 * formulario de antes creaba la cuenta contra POST /api/auth/cliente/registro,
 * que ahora responde 410.
 */
export default function RegistroCerradoPage() {
  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4">
      <div className="mb-8 flex flex-col items-center text-center">
        <BrotLogo variante="principal" color="crema" className="h-28 w-auto" />
        <p className="text-white/60 text-sm mt-3">Tienda en línea</p>
      </div>

      <div className="bg-card rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <h2 className="titulo text-xl text-text mb-3">El acceso es por invitación</h2>
        <p className="text-sm text-warm-gray leading-relaxed">
          Las cuentas del portal las damos de alta nosotros. Escribinos y te
          enviamos un correo con un enlace para que elijas tu contraseña.
        </p>

        <Link
          href="/cliente/login"
          className="mt-6 block w-full py-3 bg-brot text-white rounded-lg font-medium text-center hover:bg-brot-dark transition-colors min-h-[44px]"
        >
          Ya tengo cuenta, entrar
        </Link>

        <p className="mt-4 text-center text-sm">
          <Link href="/cliente/recuperar" className="text-brot font-medium hover:underline">
            ¿Olvidaste tu contraseña?
          </Link>
        </p>
      </div>
    </div>
  );
}
