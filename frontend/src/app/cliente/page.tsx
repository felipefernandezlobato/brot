"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CustomerAuthGuard } from "@/components/CustomerAuthGuard";
import { CuentaPendiente } from "@/components/CuentaPendiente";
import { CustomerNav } from "@/components/CustomerNav";
import { apiClienteFetch } from "@/lib/api-cliente";
import { useToast } from "@/components/Toast";
import { Cliente } from "@/lib/types";
import { ilustracionProducto, PERSONAJE } from "@/lib/ilustraciones";

// ── Types ──────────────────────────────────────────────────────────────────

interface Producto {
  id: number;
  nombre: string;
  descripcion: string | null;
  precio: number;
  categoria: string;
  imagen_url: string | null;
  disponible: boolean;
  posicion: number;
}

interface CartItem {
  producto: Producto;
  cantidad: number;
}

/** Lo que manda GET /api/cliente/pedidos/config. El porcentaje NO se escribe
 *  aca: viene del backend, que es el que lo cobra. `hoy` tambien, para que el
 *  calendario no clasifique los dias con el reloj del dispositivo -- un reloj
 *  mal puesto habilitaria fechas que el servidor va a rechazar. */
interface PedidoConfig {
  recargo_express_pct: number;
  dias_anticipacion_normal: number;
  hoy: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function toLocalISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function isDeliveryDay(d: Date): boolean {
  const dow = d.getDay();
  return dow === 3 || dow === 6; // Wed or Sat
}

/** Dias enteros entre dos fechas ISO. Via Date.UTC para que ningun cambio de
 *  huso ni de horario de verano pueda convertir una diferencia de 1 dia en
 *  0,958. */
function margenDias(iso: string, hoyIso: string): number {
  const [hy, hm, hd] = hoyIso.split("-").map(Number);
  const [y, m, d] = iso.split("-").map(Number);
  return Math.round((Date.UTC(y, m - 1, d) - Date.UTC(hy, hm - 1, hd)) / 86400000);
}

type Tramo = "pasada" | "express" | "normal";

/** Los mismos tres tramos que `evaluar()` en services/pedido_express.py. El
 *  umbral de dias y el "hoy" llegan desde el backend (`/pedidos/config`) para
 *  que las dos mitades no puedan discrepar; lo unico que se repite aca es la
 *  comparacion, que es aritmetica de UI. */
function tramoDe(iso: string, hoyIso: string, diasNormal: number): Tramo {
  const margen = margenDias(iso, hoyIso);
  if (margen < 1) return "pasada";
  if (margen < diasNormal) return "express";
  return "normal";
}

function buildCalendarWeeks(): Date[][] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Start from this week's Monday
  const start = new Date(today);
  while (start.getDay() !== 1) start.setDate(start.getDate() - 1);

  const weeks: Date[][] = [];
  const cursor = new Date(start);
  for (let w = 0; w < 5; w++) {
    const week: Date[] = [];
    for (let d = 0; d < 7; d++) {
      week.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }
  return weeks;
}

function formatDateShort(iso: string): string {
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

const DAY_LABELS = ["L", "M", "X", "J", "V", "S", "D"];
const MONTH_NAMES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

// ── Page ─────────────────────────────────────────────────────────────────────

function ClienteDashboard({ cliente }: { cliente: Cliente }) {
  const { toast } = useToast();

  const [productos, setProductos] = useState<Producto[]>([]);
  const [loadingProductos, setLoadingProductos] = useState(true);

  const [cart, setCart] = useState<CartItem[]>([]);
  const [fechaEntrega, setFechaEntrega] = useState("");
  const [showCart, setShowCart] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [config, setConfig] = useState<PedidoConfig | null>(null);

  const calendarWeeks = useMemo(() => buildCalendarWeeks(), []);

  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  // El "hoy" y el umbral salen del backend; mientras no llegue la respuesta se
  // usa el reloj del navegador y 2 dias, que es como se comportaba antes de
  // que existiera el tramo express. Asi un /config caido (Render free tier
  // duerme y el primer request tarda) deja el portal funcionando como siempre
  // en vez de bloquear el alta de pedidos.
  const hoyIso = config?.hoy ?? toLocalISODate(today);
  const diasNormal = config?.dias_anticipacion_normal ?? 2;

  // Auto-selecciona la primera fecha SIN recargo. El express tiene que ser una
  // eleccion del cliente, nunca un default que se encuentre ya puesto.
  useEffect(() => {
    for (const week of calendarWeeks) {
      for (const day of week) {
        const iso = toLocalISODate(day);
        if (isDeliveryDay(day) && tramoDe(iso, hoyIso, diasNormal) === "normal") {
          setFechaEntrega(iso);
          return;
        }
      }
    }
  }, [calendarWeeks, hoyIso, diasNormal]);

  const loadProductos = useCallback(() => {
    setLoadingProductos(true);
    // apiClienteFetch y no un fetch pelado: /api/catalogo dejo de ser publico
    // el 2026-10-16 y ahora exige el token del cliente. Con el fetch crudo
    // respondia 401 y la pantalla mostraba "Error al cargar el catalogo".
    apiClienteFetch<Producto[]>("/api/catalogo")
      .then((data) => setProductos(data.filter((p) => p.disponible)))
      .catch(() => toast("Error al cargar el catalogo", "error"))
      .finally(() => setLoadingProductos(false));
  }, [toast]);

  useEffect(() => {
    loadProductos();
  }, [loadProductos]);

  const cargarConfig = useCallback(
    () =>
      apiClienteFetch<PedidoConfig>("/api/cliente/pedidos/config")
        .then(setConfig)
        // Sin toast: el portal sigue andando con los valores por defecto (ver
        // `hoyIso`/`diasNormal`), asi que no hay nada que el cliente pueda
        // hacer con el aviso salvo preocuparse. Lo que si cambia es que el
        // tramo express queda deshabilitado, porque sin el porcentaje no se le
        // puede decir cuanto va a pagar.
        .catch(() => setConfig(null)),
    []
  );

  useEffect(() => {
    cargarConfig();
  }, [cargarConfig]);

  // Group products by category
  const productsByCategory = useMemo(() => {
    const groups: Record<string, Producto[]> = {};
    for (const p of productos) {
      if (!groups[p.categoria]) groups[p.categoria] = [];
      groups[p.categoria].push(p);
    }
    return Object.entries(groups);
  }, [productos]);

  // Cart helpers
  const getQty = (id: number) =>
    cart.find((c) => c.producto.id === id)?.cantidad ?? 0;

  const setCartQty = (producto: Producto, qty: number) => {
    setCart((prev) => {
      if (qty <= 0) return prev.filter((c) => c.producto.id !== producto.id);
      const existing = prev.find((c) => c.producto.id === producto.id);
      if (existing) {
        return prev.map((c) =>
          c.producto.id === producto.id ? { ...c, cantidad: qty } : c
        );
      }
      return [...prev, { producto, cantidad: qty }];
    });
  };

  const addToCart = (producto: Producto) =>
    setCartQty(producto, getQty(producto.id) + 1);

  const removeFromCart = (id: number) => {
    const item = cart.find((c) => c.producto.id === id);
    if (item) setCartQty(item.producto, item.cantidad - 1);
  };

  const cartTotal = useMemo(
    () => cart.reduce((s, c) => s + c.producto.precio * c.cantidad, 0),
    [cart]
  );
  const cartCount = useMemo(
    () => cart.reduce((s, c) => s + c.cantidad, 0),
    [cart]
  );

  // El tramo de la fecha elegida, y lo que cuesta. El numero autoritativo lo
  // calcula el backend al crear el pedido; esto es la vista previa, con el
  // mismo porcentaje que el servidor va a usar y nunca un 0,05 escrito aca.
  const esExpress =
    fechaEntrega !== "" && tramoDe(fechaEntrega, hoyIso, diasNormal) === "express";
  const recargoPct = config?.recargo_express_pct ?? 0;
  const recargoMonto = esExpress ? Math.round(cartTotal * recargoPct) / 100 : 0;
  const totalConRecargo = cartTotal + recargoMonto;

  const handlePlaceOrder = async () => {
    if (cart.length === 0) {
      toast("Agrega al menos un producto", "error");
      return;
    }
    if (!fechaEntrega) {
      toast("Selecciona una fecha de entrega", "error");
      return;
    }
    // Segunda capa sobre el aviso del calendario: el cliente pudo elegir la
    // fecha y seguir comprando un rato, con el aviso ya fuera de pantalla.
    // Nadie deberia enterarse del recargo al ver la factura.
    if (esExpress) {
      const ok = window.confirm(
        `Pedido express para el ${formatDateShort(fechaEntrega)}.\n\n` +
          `Productos: ${formatPrice(cartTotal)}\n` +
          `Recargo express (${recargoPct}%): ${formatPrice(recargoMonto)}\n` +
          `Total: ${formatPrice(totalConRecargo)}\n\n` +
          `¿Confirmas el pedido?`
      );
      if (!ok) return;
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
            precio_unitario_snapshot: c.producto.precio,
            subtotal: c.producto.precio * c.cantidad,
          })),
        }),
      });
      toast("Pedido realizado con exito!");
      setCart([]);
      setShowCart(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al realizar el pedido";
      toast(msg, "error");
      // Borde real: la pestana quedo abierta y cruzo la medianoche, asi que la
      // fecha elegida ya no tiene la antelacion que tenia al elegirla. Se
      // relee el "hoy" del servidor y se suelta la fecha, para que el cliente
      // tenga que elegir una vigente en vez de reintentar contra la rechazada.
      cargarConfig();
      setFechaEntrega("");
    } finally {
      setPlacing(false);
    }
  };

  // Calendar month label
  const calendarMonthLabel = useMemo(() => {
    if (calendarWeeks.length === 0) return "";
    const first = calendarWeeks[0][0];
    const last = calendarWeeks[calendarWeeks.length - 1][6];
    if (first.getMonth() === last.getMonth()) {
      return `${MONTH_NAMES[first.getMonth()]} ${first.getFullYear()}`;
    }
    return `${MONTH_NAMES[first.getMonth()]} - ${MONTH_NAMES[last.getMonth()]} ${last.getFullYear()}`;
  }, [calendarWeeks]);

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <CustomerNav nombre={cliente.nombre} />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
        {/* Greeting */}
        <div className="mb-6">
          <h1 className="titulo text-3xl text-brot">
            Hola, {cliente.nombre.split(" ")[0]}
          </h1>
          <p className="text-warm-gray text-sm mt-1">
            Elige tus productos y selecciona el dia de entrega.
          </p>
        </div>

        {/* Delivery calendar */}
        <div className="bg-card rounded-xl border border-cream-dark p-4 mb-6">
          <p className="text-sm font-medium text-warm-gray mb-1">
            Fecha de entrega
          </p>
          <p className="text-xs text-warm-gray/70 mb-3 capitalize">
            {calendarMonthLabel} &middot; Miercoles y sabados disponibles
          </p>

          {/* Day headers */}
          <div className="grid grid-cols-7 gap-1 mb-1">
            {DAY_LABELS.map((label) => (
              <div
                key={label}
                className="text-center text-xs font-medium text-warm-gray py-1"
              >
                {label}
              </div>
            ))}
          </div>

          {/* Calendar grid */}
          {calendarWeeks.map((week, wi) => (
            <div key={wi} className="grid grid-cols-7 gap-1">
              {week.map((day) => {
                const iso = toLocalISODate(day);
                const delivery = isDeliveryDay(day);
                const past = day < today;
                const tramo = tramoDe(iso, hoyIso, diasNormal);
                const selected = iso === fechaEntrega;
                // Un dia express no se habilita hasta saber el porcentaje: es
                // preferible esperar a /config unos milisegundos antes que
                // dejar confirmar un recargo que nunca se le mostro.
                const expressDisponible = tramo === "express" && config !== null;
                const selectable =
                  delivery && (tramo === "normal" || expressDisponible);

                return (
                  <button
                    key={iso}
                    disabled={!selectable}
                    onClick={() => selectable && setFechaEntrega(iso)}
                    title={
                      expressDisponible
                        ? `Entrega express: +${recargoPct}% de recargo`
                        : undefined
                    }
                    className={`
                      py-2 rounded-lg text-sm transition-colors min-h-[40px]
                      ${selected
                        ? expressDisponible
                          ? "bg-amber-500 text-white font-semibold"
                          : "bg-brot text-white font-semibold"
                        : expressDisponible
                          ? "bg-amber-100 text-amber-800 font-medium hover:bg-amber-200"
                          : selectable
                            ? "bg-brot/10 text-brot font-medium hover:bg-brot/20"
                            : past
                              ? "text-warm-gray/20"
                              : "text-warm-gray/40"
                      }
                      ${toLocalISODate(day) === toLocalISODate(today) ? "ring-1 ring-warm-gray/30" : ""}
                    `}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          ))}

          {fechaEntrega && (
            <p className="text-sm text-brot font-medium mt-3 capitalize">
              Entrega: {formatDateShort(fechaEntrega)}
            </p>
          )}

          {/* Visible todo el tiempo que la fecha este elegida, no un toast que
              se pierde: el cliente puede elegir el dia y bajar al carrito un
              rato despues. */}
          {esExpress && (
            <div className="mt-3 p-3 rounded-lg bg-amber-50 border border-amber-200">
              <p className="text-sm font-medium text-amber-900">
                Pedido express &middot; recargo del {recargoPct}%
              </p>
              <p className="text-xs text-amber-800 mt-1">
                Estas pidiendo con un dia de anticipacion. Se suma un{" "}
                {recargoPct}% al total
                {cartTotal > 0 && <> ({formatPrice(recargoMonto)} sobre tu pedido actual)</>}.
                Para no pagarlo, elegi una fecha con {diasNormal} dias o mas.
              </p>
            </div>
          )}
        </div>

        {/* Product grid by category */}
        {loadingProductos ? (
          <p className="text-warm-gray text-center py-12">
            Cargando catalogo...
          </p>
        ) : productos.length === 0 ? (
          <div className="text-center py-12 text-warm-gray">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={PERSONAJE.bandeja}
              alt=""
              aria-hidden="true"
              className="w-28 h-28 mx-auto mb-4 opacity-70"
            />
            <p className="text-lg">No hay productos disponibles</p>
          </div>
        ) : (
          <div className="space-y-8">
            {productsByCategory.map(([categoria, items]) => (
              <div key={categoria}>
                <h2 className="text-sm font-semibold text-brot uppercase tracking-wider mb-3">
                  {categoria}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((p) => {
                    const qty = getQty(p.id);
                    return (
                      <div
                        key={p.id}
                        className={`bg-card rounded-xl border p-4 flex flex-col gap-3 transition-colors ${
                          qty > 0
                            ? "border-brot/40 bg-brot/5"
                            : "border-cream-dark"
                        }`}
                      >
                        <div className="flex-1 flex items-start gap-3">
                          {/* Ilustracion de marca (seccion 5.3). Decorativa:
                              el nombre del producto esta al lado, asi que va
                              con alt vacio para que el lector de pantalla no
                              lo lea dos veces. */}
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={ilustracionProducto(p.nombre, p.categoria, p.imagen_url)}
                            alt=""
                            aria-hidden="true"
                            className="w-12 h-12 shrink-0 object-contain"
                            draggable={false}
                          />
                          <div className="min-w-0">
                            <h3 className="font-medium text-text">{p.nombre}</h3>
                            {p.descripcion && (
                              <p className="text-xs text-warm-gray mt-1 line-clamp-2">
                                {p.descripcion}
                              </p>
                            )}
                          </div>
                        </div>

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
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => removeFromCart(p.id)}
                                className="w-8 h-8 rounded-full bg-cream-dark hover:bg-cream-dark/80 flex items-center justify-center text-lg font-medium leading-none transition-colors"
                                aria-label="Quitar uno"
                              >
                                -
                              </button>
                              <input
                                type="text"
                                inputMode="numeric"
                                value={qty}
                                onChange={(e) => {
                                  const v = e.target.value.replace(/\D/g, "");
                                  setCartQty(p, v === "" ? 0 : Math.min(parseInt(v, 10), 999));
                                }}
                                className="w-12 text-center font-medium text-text bg-transparent border border-cream-dark rounded-lg py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brot/30"
                              />
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
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Floating cart bar */}
      {cartCount > 0 && (
        <div className="sticky bottom-0 bg-card border-t border-cream-dark shadow-lg">
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
            {esExpress ? (
              <span className="text-right leading-tight">
                <span className="block font-semibold text-brot">
                  {formatPrice(totalConRecargo)}
                </span>
                <span className="block text-xs text-amber-700">
                  incluye +{recargoPct}% express
                </span>
              </span>
            ) : (
              <span className="font-semibold text-brot">{formatPrice(cartTotal)}</span>
            )}
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
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => removeFromCart(item.producto.id)}
                        className="w-7 h-7 rounded-full bg-cream-dark hover:bg-cream-dark/80 flex items-center justify-center text-sm leading-none"
                      >
                        -
                      </button>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={item.cantidad}
                        onChange={(e) => {
                          const v = e.target.value.replace(/\D/g, "");
                          setCartQty(item.producto, v === "" ? 0 : Math.min(parseInt(v, 10), 999));
                        }}
                        className="w-10 text-center text-sm font-medium bg-transparent border border-cream-dark rounded-lg py-0.5 focus:outline-none focus:ring-1 focus:ring-brot/30"
                      />
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
              {/* Desglose solo cuando hay recargo: si no, el total de arriba
                  ya es la suma de las lineas y repetirlo no agrega nada. */}
              {esExpress && (
                <div className="mt-2 pt-2 border-t border-cream-dark space-y-1 text-sm">
                  <div className="flex justify-between text-warm-gray">
                    <span>Productos</span>
                    <span className="tabular-nums">{formatPrice(cartTotal)}</span>
                  </div>
                  <div className="flex justify-between text-amber-700">
                    <span>Recargo express ({recargoPct}%)</span>
                    <span className="tabular-nums">+{formatPrice(recargoMonto)}</span>
                  </div>
                  <div className="flex justify-between font-semibold text-text">
                    <span>Total</span>
                    <span className="tabular-nums">{formatPrice(totalConRecargo)}</span>
                  </div>
                </div>
              )}
              {fechaEntrega && (
                <p className="text-xs text-warm-gray mt-2 capitalize">
                  Entrega: {formatDateShort(fechaEntrega)}
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
      {(cliente) =>
        // Sin el alta completa no se monta el dashboard: no es solo que no
        // pueda confirmar el pedido, es que no puede ver el catalogo ni los
        // precios. El backend tambien lo bloquea (get_cliente_aprobado); esto
        // evita que la pantalla pida datos que le van a dar 403.
        cliente.puede_pedir ? (
          <ClienteDashboard cliente={cliente} />
        ) : (
          <CuentaPendiente cliente={cliente} />
        )
      }
    </CustomerAuthGuard>
  );
}
