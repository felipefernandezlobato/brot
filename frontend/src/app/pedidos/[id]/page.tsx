"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatARS, formatDate, formatDateTime } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

type EstadoPedido = "borrador" | "enviado" | "recibido";

interface LineaPedido {
  id: number;
  pedido_id: number;
  ingrediente_id: number;
  cantidad_pedida: number;
  unidad: string;
  cantidad_recibida: number | null;
  precio_unitario: number | null;
}

interface PedidoOut {
  id: number;
  proveedor_id: number;
  proveedor_nombre: string;
  fecha: string;
  estado: EstadoPedido;
  notas: string | null;
  fecha_recepcion: string | null;
  lineas: LineaPedido[];
}

interface IngredienteRef {
  id: number;
  nombre: string;
}

const ESTADO_LABELS: Record<EstadoPedido, string> = {
  borrador: "Borrador",
  enviado: "Enviado",
  recibido: "Recibido",
};

const ESTADO_CLASSES: Record<EstadoPedido, string> = {
  borrador: "bg-gray-100 text-gray-600",
  enviado: "bg-blue-50 text-blue-700",
  recibido: "bg-green-50 text-green-700",
};

function EstadoBadge({ estado }: { estado: EstadoPedido }) {
  return (
    <span
      className={`px-2.5 py-1 rounded-full text-xs font-medium ${ESTADO_CLASSES[estado]}`}
    >
      {ESTADO_LABELS[estado]}
    </span>
  );
}

export default function PedidoDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const id = params.id as string;

  const [pedido, setPedido] = useState<PedidoOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [ingredientesMap, setIngredientesMap] = useState<Record<number, string>>({});

  // Receive mode: quantity inputs per line
  const [receiveMode, setReceiveMode] = useState(false);
  const [cantidadesRecibidas, setCantidadesRecibidas] = useState<
    Record<number, string>
  >({});
  const [receiving, setReceiving] = useState(false);

  // Send action
  const [sending, setSending] = useState(false);

  // Delete
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Edit fecha de recepción
  const [editingFecha, setEditingFecha] = useState(false);
  const [fechaRecepcionDraft, setFechaRecepcionDraft] = useState("");
  const [savingFecha, setSavingFecha] = useState(false);

  const load = () => {
    setLoading(true);
    apiFetch<PedidoOut>(`/api/pedidos/${id}`)
      .then(setPedido)
      .catch(() => toast("Error al cargar el pedido", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    apiFetch<IngredienteRef[]>("/api/ingredientes")
      .then((ings) => {
        const map: Record<number, string> = {};
        ings.forEach((i) => (map[i.id] = i.nombre));
        setIngredientesMap(map);
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const startReceive = () => {
    if (!pedido) return;
    const initial: Record<number, string> = {};
    pedido.lineas.forEach((l) => {
      initial[l.id] = String(l.cantidad_recibida ?? l.cantidad_pedida);
    });
    setCantidadesRecibidas(initial);
    setReceiveMode(true);
  };

  const handleEnviar = async () => {
    setSending(true);
    try {
      const updated = await apiFetch<PedidoOut>(`/api/pedidos/${id}/enviar`, {
        method: "POST",
      });
      setPedido(updated);
      toast("Pedido marcado como enviado");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al enviar";
      toast(msg, "error");
    } finally {
      setSending(false);
    }
  };

  const handleRecibir = async () => {
    if (!pedido) return;
    setReceiving(true);
    try {
      const lineas = pedido.lineas.map((l) => ({
        linea_id: l.id,
        cantidad_recibida: parseFloat(cantidadesRecibidas[l.id] ?? "0") || 0,
      }));
      const updated = await apiFetch<PedidoOut>(`/api/pedidos/${id}/recibir`, {
        method: "POST",
        body: JSON.stringify({ lineas }),
      });
      setPedido(updated);
      setReceiveMode(false);
      toast("Pedido recibido correctamente");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al recibir";
      toast(msg, "error");
    } finally {
      setReceiving(false);
    }
  };

  const startEditFecha = () => {
    if (!pedido?.fecha_recepcion) return;
    setFechaRecepcionDraft(pedido.fecha_recepcion);
    setEditingFecha(true);
  };

  const cancelEditFecha = () => {
    setEditingFecha(false);
  };

  const saveFecha = async () => {
    if (!fechaRecepcionDraft) return;
    setSavingFecha(true);
    try {
      const updated = await apiFetch<PedidoOut>(`/api/pedidos/${id}`, {
        method: "PUT",
        body: JSON.stringify({ fecha_recepcion: fechaRecepcionDraft }),
      });
      setPedido(updated);
      setEditingFecha(false);
      toast("Fecha de recepción actualizada");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al actualizar la fecha";
      toast(msg, "error");
    } finally {
      setSavingFecha(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await apiFetch(`/api/pedidos/${id}`, { method: "DELETE" });
      toast("Pedido eliminado");
      router.push("/pedidos");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al eliminar";
      toast(msg, "error");
      setDeleting(false);
      setShowDelete(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-16">
        <p className="text-warm-gray">Cargando...</p>
      </div>
    );
  }

  if (!pedido) {
    return (
      <div className="text-center p-16">
        <p className="text-warm-gray mb-4">Pedido no encontrado.</p>
        <Link href="/pedidos" className="text-brot hover:underline">
          ← Volver a pedidos
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <Link
            href="/pedidos"
            className="text-warm-gray hover:text-brot text-sm transition-colors"
          >
            ← Pedidos
          </Link>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
              Pedido #{pedido.id}
            </h1>
            <EstadoBadge estado={pedido.estado} />
          </div>
          <p className="text-sm text-warm-gray mt-1">
            {pedido.proveedor_nombre} · {formatDateTime(pedido.fecha)}
          </p>
        </div>

        {/* Actions */}
        {!receiveMode && (
          <div className="flex gap-2 shrink-0 flex-wrap justify-end">
            {pedido.estado === "borrador" && (
              <>
                <PermissionGate module="pedidos_proveedores" action="edit">
                  <button
                    onClick={handleEnviar}
                    disabled={sending}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-blue-700 transition-colors disabled:opacity-50"
                  >
                    {sending ? "Enviando..." : "Marcar Enviado"}
                  </button>
                </PermissionGate>
                <PermissionGate module="pedidos_proveedores" action="delete">
                  <button
                    onClick={() => setShowDelete(true)}
                    className="border border-red-300 text-red-500 px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-red-50 transition-colors"
                  >
                    Eliminar
                  </button>
                </PermissionGate>
              </>
            )}
            {pedido.estado === "enviado" && (
              <PermissionGate module="pedidos_proveedores" action="edit">
                <button
                  onClick={startReceive}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-green-700 transition-colors"
                >
                  Registrar Recepción
                </button>
              </PermissionGate>
            )}
          </div>
        )}
      </div>

      {/* Summary card */}
      <div className="bg-white rounded-xl p-5 shadow-sm mb-6">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="bg-cream rounded-lg p-4">
            <p className="text-xs text-warm-gray mb-1">Proveedor</p>
            <p className="font-medium text-text">{pedido.proveedor_nombre}</p>
          </div>
          <div className="bg-cream rounded-lg p-4">
            <p className="text-xs text-warm-gray mb-1">Total estimado</p>
            <p className="font-medium text-text">
              {formatARS(
                pedido.lineas.reduce(
                  (sum, l) => sum + l.cantidad_pedida * (l.precio_unitario ?? 0),
                  0
                )
              )}
            </p>
          </div>
          <div className="bg-cream rounded-lg p-4">
            <p className="text-xs text-warm-gray mb-1">Estado</p>
            <EstadoBadge estado={pedido.estado} />
          </div>
          {pedido.estado === "recibido" && pedido.fecha_recepcion && (
            <div
              className="bg-cream rounded-lg p-4 group relative"
              onBlur={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                  cancelEditFecha();
                }
              }}
            >
              <p className="text-xs text-warm-gray mb-1">Fecha de recepción</p>
              {editingFecha ? (
                <div className="flex items-center gap-1.5">
                  <input
                    type="date"
                    value={fechaRecepcionDraft}
                    onChange={(e) => setFechaRecepcionDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveFecha();
                      if (e.key === "Escape") cancelEditFecha();
                    }}
                    autoFocus
                    className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                  />
                  <button
                    type="button"
                    onClick={saveFecha}
                    disabled={savingFecha}
                    className="text-green-600 hover:text-green-700 px-1 disabled:opacity-50"
                    title="Guardar"
                  >
                    ✓
                  </button>
                  <button
                    type="button"
                    onClick={cancelEditFecha}
                    className="text-warm-gray hover:text-red-500 px-1"
                    title="Cancelar"
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <p className="font-medium text-text">
                    {formatDate(pedido.fecha_recepcion)}
                  </p>
                  <PermissionGate module="pedidos_proveedores" action="edit">
                    <button
                      type="button"
                      onClick={startEditFecha}
                      className="opacity-0 group-hover:opacity-100 text-warm-gray hover:text-brot transition-opacity"
                      title="Editar fecha de recepción"
                    >
                      ✎
                    </button>
                  </PermissionGate>
                </div>
              )}
            </div>
          )}
        </div>
        {pedido.notas && (
          <p className="mt-4 text-sm text-warm-gray italic">
            Notas: {pedido.notas}
          </p>
        )}
      </div>

      {/* Line items */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
            Ítems del pedido
          </h2>
          {receiveMode && (
            <span className="text-xs text-blue-600 font-medium">
              Ingresa las cantidades recibidas
            </span>
          )}
        </div>

        {pedido.lineas.length === 0 ? (
          <p className="p-6 text-center text-warm-gray text-sm">
            Sin ítems registrados.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-warm-gray text-xs uppercase tracking-wide">
                  <th className="text-left px-6 py-3">Ingrediente</th>
                  <th className="text-right px-6 py-3">Cantidad</th>
                  <th className="text-left px-4 py-3">Unidad</th>
                  <th className="text-right px-6 py-3">Precio unit.</th>
                  <th className="text-right px-6 py-3">Subtotal</th>
                  {(pedido.estado === "recibido" || receiveMode) && (
                    <th className="text-right px-6 py-3">
                      {receiveMode ? "Cant. recibida" : "Recibido"}
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {pedido.lineas.map((l) => {
                  const subtotal =
                    l.precio_unitario !== null
                      ? l.cantidad_pedida * l.precio_unitario
                      : null;
                  return (
                    <tr
                      key={l.id}
                      className="border-b border-gray-50 last:border-0"
                    >
                      <td className="px-6 py-3 font-medium text-text">
                        {ingredientesMap[l.ingrediente_id] ?? `Ingrediente #${l.ingrediente_id}`}
                      </td>
                      <td className="px-6 py-3 text-right font-mono">
                        {l.cantidad_pedida}
                      </td>
                      <td className="px-4 py-3 text-warm-gray">{l.unidad}</td>
                      <td className="px-6 py-3 text-right font-mono text-warm-gray">
                        {l.precio_unitario !== null
                          ? formatARS(l.precio_unitario)
                          : "—"}
                      </td>
                      <td className="px-6 py-3 text-right font-mono">
                        {subtotal !== null ? formatARS(subtotal) : "—"}
                      </td>
                      {receiveMode && (
                        <td className="px-6 py-3 text-right">
                          <input
                            type="number"
                            value={cantidadesRecibidas[l.id] ?? ""}
                            onChange={(e) =>
                              setCantidadesRecibidas((prev) => ({
                                ...prev,
                                [l.id]: e.target.value,
                              }))
                            }
                            min="0"
                            step="0.01"
                            className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 text-right"
                          />
                        </td>
                      )}
                      {!receiveMode && pedido.estado === "recibido" && (
                        <td className="px-6 py-3 text-right font-mono text-green-700">
                          {l.cantidad_recibida !== null
                            ? `${l.cantidad_recibida} ${l.unidad}`
                            : "—"}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="border-t border-gray-200 bg-cream/50">
                  <td
                    colSpan={receiveMode || pedido.estado === "recibido" ? 5 : 4}
                    className="px-6 py-3 text-right font-medium text-text text-sm"
                  >
                    Total estimado
                  </td>
                  <td className="px-6 py-3 text-right font-medium text-brot font-mono">
                    {formatARS(
                      pedido.lineas.reduce(
                        (sum, l) => sum + l.cantidad_pedida * (l.precio_unitario ?? 0),
                        0
                      )
                    )}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* Receive mode actions */}
      {receiveMode && (
        <div className="mt-4 flex gap-3 justify-end pb-4">
          <button
            type="button"
            onClick={() => setReceiveMode(false)}
            className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
          >
            Cancelar
          </button>
          <button
            onClick={handleRecibir}
            disabled={receiving}
            className="bg-green-600 text-white px-6 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-green-700 transition-colors disabled:opacity-50"
          >
            {receiving ? "Confirmando..." : "Confirmar Recepción"}
          </button>
        </div>
      )}

      {/* Delete confirm modal */}
      {showDelete && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="font-medium text-text text-lg mb-2">
              Eliminar pedido
            </h3>
            <p className="text-warm-gray text-sm mb-6">
              Esta acción no se puede deshacer. El pedido{" "}
              <strong className="text-text">#{pedido.id}</strong> se eliminará
              permanentemente.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDelete(false)}
                className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleting ? "Eliminando..." : "Eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
