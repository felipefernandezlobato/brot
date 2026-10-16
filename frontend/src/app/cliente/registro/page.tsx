"use client";

import { useState } from "react";
import Link from "next/link";
import { BrotLogo } from "@/components/BrotLogo";
import { apiPublicoFetch } from "@/lib/api-cliente";

const MINIMO = 8;

export default function RegistroPage() {
  const [form, setForm] = useState({
    nombre: "",
    email: "",
    telefono: "",
    direccion: "",
    password: "",
    repetir: "",
  });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const corta = form.password.length > 0 && form.password.length < MINIMO;
  const noCoinciden = form.repetir.length > 0 && form.password !== form.repetir;
  const puede =
    form.nombre.trim() &&
    form.email.trim() &&
    form.password.length >= MINIMO &&
    form.password === form.repetir &&
    !enviando;

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      const { token } = await apiPublicoFetch<{ token: string }>(
        "/api/auth/cliente/registro",
        {
          method: "POST",
          body: JSON.stringify({
            nombre: form.nombre.trim(),
            email: form.email.trim(),
            telefono: form.telefono.trim() || null,
            direccion: form.direccion.trim() || null,
            password: form.password,
          }),
        }
      );
      // Entra con la sesion ya iniciada para ver en que estado quedo su alta,
      // en vez de registrarse y toparse con un login.
      localStorage.setItem("brot_customer_token", token);
      window.location.href = "/cliente";
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo completar el registro.");
      setEnviando(false);
    }
  };

  const input =
    "w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text";

  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4 py-10">
      <div className="mb-8 flex flex-col items-center text-center">
        <BrotLogo variante="principal" color="crema" className="h-28 w-auto" />
        <p className="text-white/60 text-sm mt-3">Tienda en línea</p>
      </div>

      <div className="bg-card rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <h2 className="titulo text-xl text-text mb-2">Crear cuenta</h2>
        <p className="text-sm text-warm-gray mb-6 leading-relaxed">
          Registrate y revisamos tu alta. Te avisamos por correo en cuanto
          puedas empezar a pedir.
        </p>

        <form onSubmit={enviar} className="space-y-4">
          <div>
            <label htmlFor="nombre" className="block text-sm font-medium text-warm-gray mb-1">
              Nombre del negocio <span className="text-red-500">*</span>
            </label>
            <input id="nombre" required value={form.nombre} onChange={set("nombre")}
              placeholder="Panadería Olula" className={input} />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-warm-gray mb-1">
              Correo electrónico <span className="text-red-500">*</span>
            </label>
            <input id="email" type="email" required value={form.email} onChange={set("email")}
              autoComplete="email" inputMode="email" autoCapitalize="none"
              autoCorrect="off" spellCheck={false}
              placeholder="tu@email.com" className={input} />
            <p className="text-xs text-warm-gray mt-1">
              Te vamos a enviar un enlace para confirmarlo.
            </p>
          </div>

          <div>
            <label htmlFor="telefono" className="block text-sm font-medium text-warm-gray mb-1">
              Teléfono
            </label>
            <input id="telefono" type="tel" value={form.telefono} onChange={set("telefono")}
              autoComplete="tel" placeholder="+54 9 260 400 0000" className={input} />
          </div>

          <div>
            <label htmlFor="direccion" className="block text-sm font-medium text-warm-gray mb-1">
              Dirección de entrega
            </label>
            <input id="direccion" value={form.direccion} onChange={set("direccion")}
              placeholder="Calle y número" className={input} />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-warm-gray mb-1">
              Contraseña <span className="text-red-500">*</span>
            </label>
            <input id="password" type="password" required value={form.password}
              onChange={set("password")} autoComplete="new-password"
              placeholder="••••••••" className={input} />
            <p className={`text-xs mt-1 ${corta ? "text-red-600" : "text-warm-gray"}`}>
              Mínimo {MINIMO} caracteres.
            </p>
          </div>

          <div>
            <label htmlFor="repetir" className="block text-sm font-medium text-warm-gray mb-1">
              Repetila <span className="text-red-500">*</span>
            </label>
            <input id="repetir" type="password" required value={form.repetir}
              onChange={set("repetir")} autoComplete="new-password"
              placeholder="••••••••" className={input} />
            {noCoinciden && <p className="text-xs mt-1 text-red-600">No coinciden.</p>}
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button type="submit" disabled={!puede}
            className="w-full py-3 bg-brot text-white rounded-lg font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]">
            {enviando ? "Creando cuenta..." : "Crear cuenta"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-warm-gray">
          ¿Ya tenés cuenta?{" "}
          <Link href="/cliente/login" className="text-brot font-medium hover:underline">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}
