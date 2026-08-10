"use client";

import { useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";

export default function ClienteRegistroPage() {
  const [form, setForm] = useState({
    nombre: "",
    email: "",
    password: "",
    telefono: "",
    direccion: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/cliente/registro`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const msg = await res.text();
        setError(msg || "Error al crear la cuenta");
        return;
      }
      const data = await res.json();
      localStorage.setItem("brot_customer_token", data.token);
      window.location.href = "/cliente";
    } catch {
      setError("Error de conexión. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-brot flex flex-col items-center justify-center p-4 py-10">
      <div className="mb-8 text-center">
        <h1 className="font-[family-name:var(--font-garamond)] text-4xl text-white mb-1">
          BROT
        </h1>
        <p className="text-white/60 text-sm">Tienda en línea · La Panadería</p>
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <h2 className="text-xl font-semibold text-text mb-6">Crear cuenta</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="nombre"
              className="block text-sm font-medium text-warm-gray mb-1"
            >
              Nombre completo <span className="text-red-500">*</span>
            </label>
            <input
              id="nombre"
              name="nombre"
              type="text"
              autoComplete="name"
              required
              value={form.nombre}
              onChange={handleChange}
              placeholder="Tu nombre"
              className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
            />
          </div>

          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-warm-gray mb-1"
            >
              Correo electrónico <span className="text-red-500">*</span>
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={form.email}
              onChange={handleChange}
              placeholder="tu@email.com"
              className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-warm-gray mb-1"
            >
              Contraseña <span className="text-red-500">*</span>
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={form.password}
              onChange={handleChange}
              placeholder="Mínimo 6 caracteres"
              className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
            />
          </div>

          <div>
            <label
              htmlFor="telefono"
              className="block text-sm font-medium text-warm-gray mb-1"
            >
              Teléfono
            </label>
            <input
              id="telefono"
              name="telefono"
              type="tel"
              autoComplete="tel"
              value={form.telefono}
              onChange={handleChange}
              placeholder="+54 11 0000-0000"
              className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
            />
          </div>

          <div>
            <label
              htmlFor="direccion"
              className="block text-sm font-medium text-warm-gray mb-1"
            >
              Dirección de entrega
            </label>
            <input
              id="direccion"
              name="direccion"
              type="text"
              autoComplete="street-address"
              value={form.direccion}
              onChange={handleChange}
              placeholder="Calle, número, ciudad"
              className="w-full px-3 py-2.5 border border-cream-dark rounded-lg bg-cream focus:outline-none focus:ring-2 focus:ring-brot/30 text-text"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-brot text-white rounded-lg font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[44px]"
          >
            {loading ? "Creando cuenta..." : "Crear cuenta"}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-warm-gray">
          ¿Ya tienes cuenta?{" "}
          <Link
            href="/cliente/login"
            className="text-brot font-medium hover:underline"
          >
            Inicia sesión
          </Link>
        </p>
      </div>
    </div>
  );
}
