"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CustomerAuthGuard } from "@/components/CustomerAuthGuard";
import { CustomerNav } from "@/components/CustomerNav";
import { apiClienteFetch } from "@/lib/api-cliente";
import { useToast } from "@/components/Toast";
import { Cliente } from "@/lib/types";

// ── Types ──────────────────────────────────────────────────────────────────

interface Producto {
  id: number;
  nombre: string;
  descripcion?: string;
  precio: number;
  disponible: boolean;
}

interface CartItem {
  producto: Producto;
  cantidad: number;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Returns the next N Wed (3) and Sat (6) delivery dates from today */
function getNextDeliveryDates(count = 8): string[] {
  const dates: string[] = [];
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  // Start from tomorrow
  d.setDate(d.getDate() + 1);
  while (dates.length < count) {
    const dow = d.getDay();
    if (dow === 3 || dow === 6) {
      dates.push(d.toISOString().slice(0, 10));
    }
    d.setDate(d.getDate() + 1);
  }
  return dates;
}

function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString("es-AR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function formatPrice(n: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(n);
}

// ── Page ─────────────────────────────────────────────────────────────────────

function ClienteDashboard({ cliente }: { cliente: Cliente }) {
  const { toast } = useToast();

  const [productos, setProductos] = useState<Producto[]>([]);
  const [loadingProductos, setLoadingProductos] = useState(true);

  const [cart, setCart] = useState<CartItem[]>([]);
  const [fechaEntrega, setFechaEntrega] = useState("");
  const [showCart, setShowCart] = useState(false);
  const [placing, setPlacing] = useState(false);

  const deliveryDates = useMemo(() => getNextDeliveryDates(8), []);

  const loadProductos = useCallback(() => {
    setLoadingProductos(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003"}/api/catalogo`)
      .then((r) => {
        if (!r.ok) throw new Error("Error al cargar catálogo");
        return r.json() as Promise<Producto[]>;
      })
      .then((data) => setProductos(data.filter((p) => p.disponible)))
      .catch(() => toast("Error al cargar el catálogo", "error"))
      .finally(() => setLoadingProductos(false));
  }, [toast]);

  useEffect(() => {
    loadProductos();
    setFechaEntrega(deliveryDates[0] ?? "");
  }, [loadProductos, deliveryDates]);

  // Cart helpers
  const getQty = (id: number) =>
    cart.find((c) => c.producto.id === id)?.cantidad ?? 0;

  const addToCart = (producto: Producto) => {
    setCart((prev) => {
      const existing = prev.find((c) => c.producto.id === producto.id);
      if (existing) {
        return prev.map((c) =>
          c.producto.id === producto.id
            ? { ...c, cantidad: c.cantidad + 1 }
            : c
        );
      }
      return [...prev, { producto, cantidad: 1 }];
    });
  };

  const removeFromCart = (id: number) => {
    setCart((prev) => {
      const item = prev.find((c) => c.producto.id === id);
      if (!item) return prev;
      if (item.cantidad <= 1) return prev.filter((c) => c.producto.id !== id);
      return prev.map((c) =>
        c.producto.id === id ? { ...c, cantidad: c.cantidad - 1 } : c
      );
    });
  };

  const cartTotal = useMemo(
    () => cart.reduce((s, c) => s + c.producto.precio * c.cantidad, 0),
    [cart]
  );
  const cartCount = useMemo(
    () => cart.reduce((s, c) => s + c.cantidad, 0),
    [cart]
  );

  const handlePlaceOrder = async () => {
    if (cart.length === 0) {
      toast("Agrega al menos un producto", "error");
      return;
    }
    if (!fechaEntrega) {
      toast("Selecciona una fecha de entrega", "error");
      return;
    }
    setPlacing(true);
    try {
      await apiClienteFetch("/api/cliente/pedidos", {
        method: "POST",
        body: JSON.stringify({
          fecha_entrega: fechaEntrega,
          lineas: cart.map((c) => ({
            producto_id: c.producto.id,
            cantidad: c.cantidad,
          })),
        }),
      });
      toast("¡Pedido realizado con éxito!");
      setCart([]);
      setShowCart(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al realizar el pedido";
      toast(msg, "error");
    } finally {
      setPlacing(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <CustomerNav nombre={cliente.nombre} />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
        {/* Greeting */}
        <div className="mb-6">
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Hola, {cliente.nombre.split(" ")[0]}
          </h1>
          <p className="text-warm-gray text-sm mt-1">
            Elige tus panes y selecciona el día de entrega.
          </p>
        </div>

        {/* Delivery date picker */}
        <div className="bg-white rounded-xl border border-cream-dark p-4 mb-6">
          <p className="text-sm font-medium text-warm-gray mb-3">
            Fecha de entrega (miércoles o sábado)
          </p>
          <div className="flex gap-2 flex-wrap">
            {deliveryDates.map((date) => (
              <button
                key={date}
                onClick={() => setFechaEntrega(date)}
                className={`px-3 py-2 rounded-lg text-sm capitalize transition-colors min-h-[40px] ${
                  fechaEntrega === date
                    ? "bg-brot text-white font-medium"
                    : "bg-cream border border-cream-dark text-warm-gray hover:border-brot hover:text-brot"
                }`}
              >
                {formatDate(date)}
              </button>
            ))}
          </div>
        </div>

        {/* Product grid */}
        {loadingProductos ? (
          <p className="text-warm-gray text-center py-12">
            Cargando catálogo...
          </p>
        ) : productos.length === 0 ? (
          <div className="text-center py-12 text-warm-gray">
            <p className="text-lg">No hay productos disponibles</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {productos.map((p) => {
              const qty = getQty(p.id);
              return (
                <div
                  key={p.id}
                  className="bg-white rounded-xl border border-cream-dark p-4 flex flex-col gap-3"
                >
                  {/* Product info */}
                  <div className="flex-1">
                    <h3 className="font-medium text-text">{p.nombre}</h3>
                    {p.descripcion && (
                      <p className="text-xs text-warm-gray mt-1 line-clamp-2">
                        {p.descripcion}
                      </p>
                    )}
                  </div>

                  {/* Price + actions */}
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-lg font-semibold text-brot">
                      {formatPrice(p.precio)}
                    </span>

                    {qty === 0 ? (
                      <button
                        onClick={() => addToCart(p)}
                        className="px-4 py-1.5 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[36px]"
                      >
                        Agregar
                      </button>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => removeFromCart(p.id)}
                          className="w-8 h-8 rounded-full bg-cream-dark hover:bg-cream-dark/80 flex items-center justify-center text-lg font-medium leading-none transition-colors"
                          aria-label="Quitar uno"
                        >
                          −
                        </button>
                        <span className="w-6 text-center font-medium text-text">
                          {qty}
                        </span>
                        <button
                          onClick={() => addToCart(p)}
                          className="w-8 h-8 rounded-full bg-brot hover:bg-brot-dark text-white flex items-center justify-center text-lg font-medium leading-none transition-colors"
                          aria-label="Agregar uno"
                        >
                          +
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Floating cart bar */}
      {cartCount > 0 && (
        <div className="sticky bottom-0 bg-white border-t border-cream-dark shadow-lg">
          <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <button
              onClick={() => setShowCart((v) => !v)}
              className="flex items-center gap-2 text-sm text-brot font-medium"
            >
              <span className="bg-brot text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {cartCount}
              </span>
              {showCart ? "Ocultar carrito" : "Ver carrito"}
            </button>
            <span className="font-semibold text-brot">{formatPrice(cartTotal)}</span>
            <button
              onClick={handlePlaceOrder}
              disabled={placing}
              className="px-5 py-2 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[40px]"
            >
              {placing ? "Enviando..." : "Hacer pedido"}
            </button>
          </div>

          {/* Cart detail */}
          {showCart && (
            <div className="border-t border-cream-dark max-w-5xl mx-auto px-4 pb-3 pt-2">
              <div className="divide-y divide-cream-dark">
                {cart.map((item) => (
                  <div
                    key={item.producto.id}
                    className="flex items-center justify-between py-2 gap-3"
                  >
                    <span className="text-sm text-text flex-1">
                      {item.producto.nombre}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => removeFromCart(item.producto.id)}
                        className="w-7 h-7 rounded-full bg-cream-dark hover:bg-cream-dark/80 flex items-center justify-center text-sm leading-none"
                      >
                        −
                      </button>
                      <span className="w-5 text-center text-sm font-medium">
                        {item.cantidad}
                      </span>
                      <button
                        onClick={() => addToCart(item.producto)}
                        className="w-7 h-7 rounded-full bg-brot hover:bg-brot-dark text-white flex items-center justify-center text-sm leading-none"
                      >
                        +
                      </button>
                    </div>
                    <span className="text-sm text-brot font-medium w-20 text-right">
                      {formatPrice(item.producto.precio * item.cantidad)}
                    </span>
                  </div>
                ))}
              </div>
              {fechaEntrega && (
                <p className="text-xs text-warm-gray mt-2 capitalize">
                  Entrega: {formatDate(fechaEntrega)}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ClientePage() {
  return (
    <CustomerAuthGuard>
      {(cliente) => <ClienteDashboard cliente={cliente} />}
    </CustomerAuthGuard>
  );
}
