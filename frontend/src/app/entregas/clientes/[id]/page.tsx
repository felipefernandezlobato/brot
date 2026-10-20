"use client";

/* La cuenta de un cliente: qué pidió, cuánto lleva y qué compra más.
 *
 * Antes esto no se podía ver. El dato existía repartido en cuatro pantallas y
 * ninguna respondía "¿qué me compró Creme?": la lista de clientes son datos de
 * contacto, el Historial de /entregas apila a todos los clientes juntos y solo
 * cuenta B2B sin importes, Volumen da una fila agregada, y las ventas por
 * cliente del inicio son un porcentaje del mes sin forma de entrar al detalle.
 *
 * Solo admin, igual que las estadísticas del inicio y por el mismo motivo:
 * enseña facturación por cliente. El gate real está en el backend
 * (`require_admin` en el endpoint); esto evita además pedir datos que van a
 * devolver 403 y dejar la pantalla en un error feo.
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { loadPermissions } from "@/lib/permissions";
import { formatARS, formatCantidad, formatDate } from "@/lib/format";
import { Tarjeta, Panel, Fila } from "@/components/stats/common";
import { EstadoPedidoBadge } from "@/components/EstadoPedidoBadge";

interface LineaHistorial {
  id: number;
  producto_id: number;
  producto_nombre: string | null;
  cantidad: number;
  precio_unitario_snapshot: number;
  subtotal: number;
}

interface Pedido {
  id: number;
  origen: "portal" | "entrega";
  fecha_entrega: string;
  estado: string;
  notas: string | null;
  total: number;
  lineas: LineaHistorial[];
}

interface Cuenta {
  cliente: {
    id: number;
    nombre: string;
    email: string | null;
    telefono: string | null;
    direccion: string | null;
    contacto: string | null;
    notas: string | null;
    dia_entrega_preferido: string | null;
    is_active: boolean;
    tiene_acceso: boolean;
    email_verificado: boolean;
    aprobado: boolean;
    puede_pedir: boolean;
  };
  resumen: {
    facturado_ars: number;
    pedidos: number;
    ticket_promedio_ars: number | null;
    primera_entrega: string | null;
    ultima_entrega: string | null;
  };
  top_productos: { producto_id: number; producto: string | null; cantidad: number; monto_ars: number }[];
  historial: Pedido[];
  advertencias: { sin_ventas_mostrador: boolean };
}


/** Dónde está cada cliente en el camino al portal.
 *
 * Son tres puertas y conviene decir cuál falta: la suya (confirmar el correo),
 * la nuestra (aprobarlo) o ninguna. Es la misma distinción que ve el cliente en
 * su pantalla de cuenta pendiente, contada desde el otro lado. */
function estadoPortal(c: Cuenta["cliente"]): { texto: string; clase: string } {
  if (!c.email) return { texto: "Sin correo cargado", clase: "bg-cream text-warm-gray" };
  if (!c.tiene_acceso) return { texto: "Invitado, sin contraseña aún", clase: "bg-amber-50 text-amber-700" };
  if (!c.email_verificado) return { texto: "Falta que confirme su correo", clase: "bg-amber-50 text-amber-700" };
  if (!c.aprobado) return { texto: "Pendiente de aprobar", clase: "bg-amber-50 text-amber-700" };
  return { texto: "Puede pedir por la web", clase: "bg-green-50 text-green-700" };
}

export default function CuentaCliente() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [esAdmin, setEsAdmin] = useState<boolean | null>(null);
  const [data, setData] = useState<Cuenta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadPermissions()
      .then((p) => setEsAdmin(p.role === "admin"))
      .catch(() => setEsAdmin(false));
  }, []);

  useEffect(() => {
    if (esAdmin !== true) return;
    apiFetch<Cuenta>(`/api/clientes-b2b/${id}/cuenta`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "No se pudo cargar la cuenta"));
  }, [id, esAdmin]);

  // `origen` + `id` como clave: las dos tablas tienen secuencias distintas y
  // sus ids se solapan, asi que el id solo no identifica una fila.
  const clave = (p: Pedido) => `${p.origen}-${p.id}`;
  const alternar = (p: Pedido) =>
    setAbierto((prev) => {
      const next = new Set(prev);
      next.has(clave(p)) ? next.delete(clave(p)) : next.add(clave(p));
      return next;
    });

  if (esAdmin === null) return <p className="text-center text-warm-gray py-10">Cargando...</p>;
  if (!esAdmin) {
    return (
      <div className="bg-card border border-cream-dark rounded-xl p-8 text-center">
        <p className="text-text">Esta pantalla es solo para administradores.</p>
        <p className="text-sm text-warm-gray mt-2">
          Las entregas del día las ves en{" "}
          <Link href="/entregas" className="text-brot underline">Entregas B2B</Link>.
        </p>
      </div>
    );
  }
  if (error) return <p className="text-center text-red-600 py-10">{error}</p>;
  if (!data) return <p className="text-center text-warm-gray py-10">Cargando...</p>;

  const { cliente, resumen, top_productos, historial } = data;
  const portal = estadoPortal(cliente);

  return (
    <div>
      <button
        onClick={() => router.push("/entregas/clientes")}
        className="text-sm text-warm-gray hover:text-brot mb-3"
      >
        ← Clientes
      </button>

      {/* Cabecera: quién es y en qué punto está con el portal */}
      <div className="bg-card border border-cream-dark rounded-xl p-5 mb-4">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h1 className="titulo text-2xl text-brot">{cliente.nombre}</h1>
            <p className="text-sm text-warm-gray mt-1">
              {[cliente.email, cliente.telefono, cliente.direccion].filter(Boolean).join(" · ") ||
                "Sin datos de contacto"}
            </p>
          </div>
          <span className={`text-xs px-2 py-1 rounded-full ${portal.clase}`}>{portal.texto}</span>
        </div>
        {cliente.notas && (
          <p className="text-xs text-warm-gray mt-3 pt-3 border-t border-cream-dark">{cliente.notas}</p>
        )}
      </div>

      {/* Resumen */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Tarjeta
          label="Facturado"
          valor={formatARS(resumen.facturado_ars)}
          detalle="solo lo entregado"
        />
        <Tarjeta label="Pedidos" valor={String(resumen.pedidos)} detalle="entregados" />
        <Tarjeta
          label="Ticket promedio"
          valor={resumen.ticket_promedio_ars != null ? formatARS(resumen.ticket_promedio_ars) : "—"}
        />
        <Tarjeta
          label="Último pedido"
          valor={resumen.ultima_entrega ? formatDate(resumen.ultima_entrega) : "—"}
          detalle={resumen.primera_entrega ? `desde ${formatDate(resumen.primera_entrega)}` : undefined}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Qué compra más — por plata, no por unidades */}
        <Panel titulo="Qué compra más" nota="por importe" vacio={top_productos.length === 0}>
          {top_productos.map((t) => (
            <Fila
              key={t.producto_id}
              nombre={t.producto ?? `Producto ${t.producto_id}`}
              sub={`${formatCantidad(t.cantidad)} u`}
              derecha={formatARS(t.monto_ars)}
            />
          ))}
        </Panel>

        {/* Historial: TODO, incluido lo pendiente */}
        <div className="bg-card border border-cream-dark rounded-xl p-4">
          <div className="flex items-baseline justify-between mb-2">
            <h3 className="font-medium text-text text-sm">Historial</h3>
            <span className="text-xs text-warm-gray">{historial.length} en total</span>
          </div>
          {historial.length === 0 ? (
            <p className="text-xs text-warm-gray">Todavía no hay pedidos ni entregas.</p>
          ) : (
            <div className="divide-y divide-cream-dark max-h-[420px] overflow-y-auto">
              {historial.map((p) => {
                const open = abierto.has(clave(p));
                return (
                  <div key={clave(p)} className="py-2">
                    <button
                      onClick={() => alternar(p)}
                      className="w-full flex items-center justify-between gap-2 text-sm text-left min-h-[44px]"
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="text-warm-gray tabular-nums">{formatDate(p.fecha_entrega)}</span>
                        <span className="text-xs text-warm-gray">
                          {p.origen === "portal" ? "web" : "obrador"}
                        </span>
                        <EstadoPedidoBadge estado={p.estado} />
                      </span>
                      <span className="text-text tabular-nums whitespace-nowrap">
                        {formatARS(p.total)}
                        <span className="text-warm-gray ml-2">{open ? "▾" : "▸"}</span>
                      </span>
                    </button>
                    {open && (
                      <div className="mt-1.5 pl-2 space-y-1">
                        {p.lineas.map((l) => (
                          <div key={l.id} className="flex items-center justify-between text-xs gap-3">
                            <span className="text-warm-gray truncate">
                              {formatCantidad(l.cantidad)} × {l.producto_nombre ?? `producto ${l.producto_id}`}
                            </span>
                            <span className="text-warm-gray tabular-nums whitespace-nowrap">
                              {formatARS(l.subtotal)}
                            </span>
                          </div>
                        ))}
                        {p.notas && <p className="text-xs text-warm-gray pt-1 italic">{p.notas}</p>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <p className="text-xs text-warm-gray mt-4 leading-relaxed">
        El facturado y el ticket promedio cuentan solo lo entregado; el historial muestra
        también lo pendiente. Las ventas de mostrador no se registran en el sistema, así que
        lo que compró este cliente en el local no está acá.
      </p>
    </div>
  );
}
