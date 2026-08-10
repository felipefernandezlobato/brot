"use client";

import { useCallback, useEffect, useState } from "react";
import { CustomerAuthGuard } from "@/components/CustomerAuthGuard";
import { CustomerNav } from "@/components/CustomerNav";
import { apiClienteFetch } from "@/lib/api-cliente";
import { useToast } from "@/components/Toast";
import { Cliente } from "@/lib/types";

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

interface LineaRecurrente {
  id: number;
  pedido_recurrente_id: number;
  producto_id: number;
  cantidad_default: number;
}

interface PedidoRecurrente {
  id: number;
  cliente_id: number;
  dia_entrega: string;
  activo: boolean;
  fecha_inicio: string;
  notas: string | null;
  lineas: LineaRecurrente[];
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatPrice(n: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    maximumFractionDigits: 0,
  }).format(n);
}

const DIA_LABELS: Record<string, string> = {
  miercoles: "Miércoles",
  sabado: "Sábado",
};

// ── Page ─────────────────────────────────────────────────────────────────────

function RecurrentesContent({ cliente }: { cliente: Cliente }) {
  const { toast } = useToast();

  const [recurrentes, setRecurrentes] = useState<PedidoRecurrente[]>([]);
  const [productos, setProductos] = useState<Producto[]>([]);
  const [loading, setLoading] = useState(true);

  // New form state
  const [showForm, setShowForm] = useState(false);
  const [newProductoId, setNewProductoId] = useState("");
  const [newCantidad, setNewCantidad] = useState("1");
  const [newDia, setNewDia] = useState<"miercoles" | "sabado">("miercoles");
  const [saving, setSaving] = useState(false);

  // Edit state
  const [editId, setEditId] = useState<number | null>(null);
  const [editCantidad, setEditCantidad] = useState("1");
  const [editActivo, setEditActivo] = useState(true);

  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClienteFetch<PedidoRecurrente[]>("/api/cliente/recurrentes"),
      fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003"}/api/catalogo`
      ).then((r) => r.json() as Promise<Producto[]>),
    ])
      .then(([recs, prods]) => {
        setRecurrentes(recs);
        setProductos(prods.filter((p) => p.disponible));
        if (prods.length > 0) setNewProductoId(String(prods[0].id));
      })
      .catch(() => toast("Error al cargar pedidos recurrentes", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProductoId) return;
    setSaving(true);
    try {
      await apiClienteFetch("/api/cliente/recurrentes", {
        method: "POST",
        body: JSON.stringify({
          dia_entrega: newDia,
          activo: true,
          lineas: [
            {
              producto_id: Number(newProductoId),
              cantidad_default: Number(newCantidad),
            },
          ],
        }),
      });
      toast("Pedido recurrente creado");
      setShowForm(false);
      setNewCantidad("1");
      load();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al crear pedido recurrente";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (rec: PedidoRecurrente) => {
    setEditId(rec.id);
    setEditCantidad(String(rec.lineas[0]?.cantidad_default ?? 1));
    setEditActivo(rec.activo);
    setDeleteConfirm(null);
  };

  const handleSaveEdit = async () => {
    if (editId === null) return;
    setSaving(true);
    try {
      const rec = recurrentes.find((r) => r.id === editId);
      await apiClienteFetch(`/api/cliente/recurrentes/${editId}`, {
        method: "PUT",
        body: JSON.stringify({
          dia_entrega: rec?.dia_entrega,
          activo: editActivo,
          lineas: rec?.lineas.map((l) => ({
            producto_id: l.producto_id,
            cantidad_default: Number(editCantidad),
          })) ?? [],
        }),
      });
      toast("Pedido recurrente actualizado");
      setEditId(null);
      load();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al actualizar pedido recurrente";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiClienteFetch(`/api/cliente/recurrentes/${id}`, {
        method: "DELETE",
      });
      toast("Pedido recurrente eliminado");
      setDeleteConfirm(null);
      load();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al eliminar pedido recurrente";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  const miercoles = recurrentes.filter((r) => r.dia_entrega === "miercoles");
  const sabados = recurrentes.filter((r) => r.dia_entrega === "sabado");

  const renderRow = (rec: PedidoRecurrente) => {
    if (editId === rec.id) {
      return (
        <div key={rec.id} className="px-4 py-3 flex gap-3 flex-wrap items-center bg-cream/40">
          <div>
            <label className="block text-xs text-warm-gray mb-1">Cantidad</label>
            <input
              type="number"
              min="1"
              value={editCantidad}
              onChange={(e) => setEditCantidad(e.target.value)}
              className="w-20 px-2 py-1.5 border border-cream-dark rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>
          <div className="flex items-center gap-2 mt-4">
            <input
              id={`activo-${rec.id}`}
              type="checkbox"
              checked={editActivo}
              onChange={(e) => setEditActivo(e.target.checked)}
              className="w-4 h-4 accent-brot"
            />
            <label
              htmlFor={`activo-${rec.id}`}
              className="text-sm text-warm-gray"
            >
              Activo
            </label>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSaveEdit}
              disabled={saving}
              className="px-3 py-1.5 bg-brot text-white rounded-lg text-sm hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[36px]"
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
            <button
              onClick={() => setEditId(null)}
              className="px-3 py-1.5 border border-cream-dark rounded-lg text-sm hover:bg-cream-dark transition-colors min-h-[36px]"
            >
              Cancelar
            </button>
          </div>
        </div>
      );
    }

    if (deleteConfirm === rec.id) {
      return (
        <div key={rec.id} className="px-4 py-3 flex items-center gap-3 flex-wrap bg-red-50">
          <span className="text-sm flex-1">
            ¿Eliminar pedido recurrente <strong>#{rec.id}</strong> ({rec.lineas.map((l) => {
              const prod = productos.find((p) => p.id === l.producto_id);
              return prod?.nombre ?? `Producto #${l.producto_id}`;
            }).join(", ")})?
          </span>
          <button
            onClick={() => handleDelete(rec.id)}
            disabled={saving}
            className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors disabled:opacity-50 min-h-[36px]"
          >
            {saving ? "Eliminando..." : "Sí, eliminar"}
          </button>
          <button
            onClick={() => setDeleteConfirm(null)}
            className="px-3 py-1.5 border border-cream-dark rounded-lg text-sm hover:bg-cream-dark transition-colors min-h-[36px]"
          >
            Cancelar
          </button>
        </div>
      );
    }

    return (
      <div key={rec.id} className="px-4 py-3 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          {rec.lineas.map((l) => {
            const prod = productos.find((p) => p.id === l.producto_id);
            return (
              <p key={l.id} className="text-sm font-medium text-text">
                {prod?.nombre ?? `Producto #${l.producto_id}`} — Cantidad: {l.cantidad_default}
              </p>
            );
          })}
          {!rec.activo && (
            <p className="text-xs text-warm-gray">
              <span className="bg-cream px-1.5 py-0.5 rounded text-warm-gray">
                Pausado
              </span>
            </p>
          )}
        </div>
        {!rec.activo && (
          <span className="text-xs text-warm-gray bg-cream px-2 py-1 rounded-full">
            Inactivo
          </span>
        )}
        <button
          onClick={() => startEdit(rec)}
          className="text-sm text-brot hover:text-brot-dark min-h-[36px] px-2 transition-colors"
        >
          Editar
        </button>
        <button
          onClick={() => {
            setDeleteConfirm(rec.id);
            setEditId(null);
          }}
          className="text-sm text-red-600 hover:text-red-700 min-h-[36px] px-2 transition-colors"
        >
          Eliminar
        </button>
      </div>
    );
  };

  const renderGroup = (title: string, items: PedidoRecurrente[]) => (
    <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
      <div className="px-4 py-2.5 bg-cream-dark flex items-center justify-between">
        <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
          {title}
        </h3>
        <span className="text-xs text-warm-gray">{items.length}</span>
      </div>
      <div className="divide-y divide-cream-dark">
        {items.length === 0 ? (
          <p className="px-4 py-4 text-sm text-warm-gray">
            Sin pedidos recurrentes para {title.toLowerCase()}.
          </p>
        ) : (
          items.map(renderRow)
        )}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-cream flex flex-col">
      <CustomerNav nombre={cliente.nombre} />

      <main className="flex-1 max-w-3xl mx-auto w-full px-4 py-6">
        <div className="flex items-center justify-between mb-6 gap-3">
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Pedidos Recurrentes
          </h1>
          <button
            onClick={() => setShowForm((v) => !v)}
            className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[40px] whitespace-nowrap"
          >
            + Nuevo
          </button>
        </div>

        <p className="text-sm text-warm-gray mb-6">
          Los pedidos recurrentes se generan automáticamente cada semana en el
          día que elijas (miércoles o sábado).
        </p>

        {/* Create form */}
        {showForm && (
          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
            <h3 className="font-medium mb-4">Nuevo pedido recurrente</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-warm-gray mb-1">
                  Producto
                </label>
                <select
                  value={newProductoId}
                  onChange={(e) => setNewProductoId(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[42px]"
                >
                  {productos.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nombre} — {formatPrice(p.precio)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex gap-4 flex-wrap">
                <div>
                  <label className="block text-sm font-medium text-warm-gray mb-1">
                    Cantidad
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={newCantidad}
                    onChange={(e) => setNewCantidad(e.target.value)}
                    className="w-24 px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-warm-gray mb-1">
                    Día de entrega
                  </label>
                  <select
                    value={newDia}
                    onChange={(e) =>
                      setNewDia(e.target.value as "miercoles" | "sabado")
                    }
                    className="px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[42px]"
                  >
                    <option value="miercoles">Miércoles</option>
                    <option value="sabado">Sábado</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors disabled:opacity-50 min-h-[40px]"
                >
                  {saving ? "Guardando..." : "Crear"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border border-cream-dark rounded-lg text-sm hover:bg-cream-dark transition-colors min-h-[40px]"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        )}

        {loading ? (
          <p className="text-warm-gray text-center py-12">Cargando...</p>
        ) : (
          <>
            {renderGroup(DIA_LABELS.miercoles, miercoles)}
            {renderGroup(DIA_LABELS.sabado, sabados)}
          </>
        )}
      </main>
    </div>
  );
}

export default function RecurrentesPage() {
  return (
    <CustomerAuthGuard>
      {(cliente) => <RecurrentesContent cliente={cliente} />}
    </CustomerAuthGuard>
  );
}
