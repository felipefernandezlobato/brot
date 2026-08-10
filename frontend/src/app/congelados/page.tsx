"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatDate } from "@/lib/format";

interface ProductoCongelado {
  id: number;
  nombre: string;
  unidad: string;
}

interface StockCongelado {
  id: number;
  producto_id: number;
  producto_nombre: string;
  cantidad: number;
  fecha_entrada: string;
  fecha_vencimiento: string;
  notas: string | null;
}

interface AlertaVencimiento {
  id: number;
  producto_nombre: string;
  fecha_vencimiento: string;
  dias_restantes: number;
}

function expiryClass(fecha: string): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exp = new Date(fecha + "T00:00:00");
  const diffMs = exp.getTime() - today.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return "text-red-600 font-semibold";
  if (diffDays <= 7) return "text-amber-600 font-semibold";
  return "text-text";
}

function expiryBadge(fecha: string): string | null {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const exp = new Date(fecha + "T00:00:00");
  const diffMs = exp.getTime() - today.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays < 0) return "Vencido";
  if (diffDays === 0) return "Vence hoy";
  if (diffDays <= 7) return `${diffDays}d`;
  return null;
}

const EMPTY_FORM = {
  producto_id: "",
  cantidad: "",
  fecha_entrada: new Date().toISOString().slice(0, 10),
  fecha_vencimiento: "",
  notas: "",
};

export default function CongeladosPage() {
  const { toast } = useToast();

  const [stock, setStock] = useState<StockCongelado[]>([]);
  const [productos, setProductos] = useState<ProductoCongelado[]>([]);
  const [alertas, setAlertas] = useState<AlertaVencimiento[]>([]);
  const [loading, setLoading] = useState(true);

  // Create form
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  // Edit state
  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ ...EMPTY_FORM });

  // Delete confirm
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<StockCongelado[]>("/api/congelados"),
      apiFetch<ProductoCongelado[]>("/api/congelados/productos"),
      apiFetch<AlertaVencimiento[]>("/api/congelados/alertas-vencimiento"),
    ])
      .then(([s, p, a]) => {
        setStock(s);
        setProductos(p);
        setAlertas(a);
      })
      .catch(() => toast("Error al cargar stock congelado", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.producto_id || !form.cantidad || !form.fecha_vencimiento) return;
    setSaving(true);
    try {
      await apiFetch("/api/congelados", {
        method: "POST",
        body: JSON.stringify({
          producto_id: Number(form.producto_id),
          cantidad: Number(form.cantidad),
          fecha_entrada: form.fecha_entrada,
          fecha_vencimiento: form.fecha_vencimiento,
          notas: form.notas || null,
        }),
      });
      toast("Entrada creada");
      setForm({ ...EMPTY_FORM });
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al crear entrada", "error");
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (entry: StockCongelado) => {
    setEditId(entry.id);
    setEditForm({
      producto_id: String(entry.producto_id),
      cantidad: String(entry.cantidad),
      fecha_entrada: entry.fecha_entrada,
      fecha_vencimiento: entry.fecha_vencimiento,
      notas: entry.notas ?? "",
    });
    setDeleteConfirm(null);
  };

  const handleSaveEdit = async () => {
    if (!editId || !editForm.producto_id || !editForm.cantidad || !editForm.fecha_vencimiento) return;
    setSaving(true);
    try {
      await apiFetch(`/api/congelados/${editId}`, {
        method: "PUT",
        body: JSON.stringify({
          producto_id: Number(editForm.producto_id),
          cantidad: Number(editForm.cantidad),
          fecha_entrada: editForm.fecha_entrada,
          fecha_vencimiento: editForm.fecha_vencimiento,
          notas: editForm.notas || null,
        }),
      });
      toast("Entrada actualizada");
      setEditId(null);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al actualizar", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await apiFetch(`/api/congelados/${id}`, { method: "DELETE" });
      toast("Entrada eliminada");
      setDeleteConfirm(null);
      load();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Error al eliminar", "error");
      setDeleteConfirm(null);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Stock Congelado
        </h1>
        <Link
          href="/congelados/productos"
          className="text-sm text-brot hover:text-brot-dark transition-colors"
        >
          Gestionar productos →
        </Link>
      </div>

      {/* Expiry alerts */}
      {alertas.length > 0 && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-sm font-medium text-amber-800 mb-2">
            ⚠️ Alertas de vencimiento ({alertas.length})
          </p>
          <ul className="space-y-1">
            {alertas.map((a) => (
              <li key={a.id} className="text-xs text-amber-700">
                <span className="font-medium">{a.producto_nombre}</span>
                {" — "}
                {a.dias_restantes < 0
                  ? `Vencido hace ${Math.abs(a.dias_restantes)} día${Math.abs(a.dias_restantes) !== 1 ? "s" : ""}`
                  : a.dias_restantes === 0
                  ? "Vence hoy"
                  : `Vence en ${a.dias_restantes} día${a.dias_restantes !== 1 ? "s" : ""}`}{" "}
                ({formatDate(a.fecha_vencimiento)})
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Stock list */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-6">
        {loading ? (
          <div className="p-8 text-center text-warm-gray">Cargando...</div>
        ) : stock.length === 0 ? (
          <div className="p-8 text-center text-warm-gray">
            No hay entradas de stock congelado.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Producto</th>
                    <th className="text-right px-4 py-3 font-medium text-warm-gray">Cantidad</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Fecha entrada</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Vencimiento</th>
                    <th className="text-left px-4 py-3 font-medium text-warm-gray">Notas</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {stock.map((entry, idx) => {
                    if (editId === entry.id) {
                      return (
                        <tr key={entry.id} className="border-b border-cream-dark bg-cream/30">
                          <td className="px-4 py-2">
                            <select
                              value={editForm.producto_id}
                              onChange={(e) => setEditForm({ ...editForm, producto_id: e.target.value })}
                              className="w-full px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                            >
                              <option value="">— Producto —</option>
                              {productos.map((p) => (
                                <option key={p.id} value={p.id}>{p.nombre} ({p.unidad})</option>
                              ))}
                            </select>
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="number"
                              value={editForm.cantidad}
                              onChange={(e) => setEditForm({ ...editForm, cantidad: e.target.value })}
                              min="0"
                              step="0.001"
                              className="w-24 px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 text-right"
                            />
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="date"
                              value={editForm.fecha_entrada}
                              onChange={(e) => setEditForm({ ...editForm, fecha_entrada: e.target.value })}
                              className="px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                            />
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="date"
                              value={editForm.fecha_vencimiento}
                              onChange={(e) => setEditForm({ ...editForm, fecha_vencimiento: e.target.value })}
                              className="px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                            />
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="text"
                              value={editForm.notas}
                              onChange={(e) => setEditForm({ ...editForm, notas: e.target.value })}
                              placeholder="Notas"
                              className="w-full px-2 py-1.5 border border-cream-dark rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                            />
                          </td>
                          <td className="px-4 py-2">
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={handleSaveEdit}
                                disabled={saving}
                                className="px-3 py-1.5 bg-brot text-white rounded-lg text-xs hover:bg-brot-dark transition-colors disabled:opacity-50"
                              >
                                {saving ? "..." : "Guardar"}
                              </button>
                              <button
                                onClick={() => setEditId(null)}
                                className="px-3 py-1.5 border border-cream-dark rounded-lg text-xs hover:bg-cream-dark transition-colors"
                              >
                                Cancelar
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    }
                    if (deleteConfirm === entry.id) {
                      return (
                        <tr key={entry.id} className="border-b border-cream-dark bg-red-50">
                          <td colSpan={5} className="px-4 py-3 text-sm">
                            ¿Eliminar entrada de <strong>{entry.producto_nombre}</strong>?
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={() => handleDelete(entry.id)}
                                disabled={saving}
                                className="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 transition-colors disabled:opacity-50"
                              >
                                {saving ? "..." : "Eliminar"}
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="px-3 py-1.5 border border-cream-dark rounded-lg text-xs hover:bg-cream-dark transition-colors"
                              >
                                Cancelar
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    }
                    const badge = expiryBadge(entry.fecha_vencimiento);
                    return (
                      <tr
                        key={entry.id}
                        className={`${idx < stock.length - 1 ? "border-b border-cream-dark" : ""}`}
                      >
                        <td className="px-4 py-3 font-medium text-text">{entry.producto_nombre}</td>
                        <td className="px-4 py-3 text-right text-text">{entry.cantidad}</td>
                        <td className="px-4 py-3 text-warm-gray">{formatDate(entry.fecha_entrada)}</td>
                        <td className="px-4 py-3">
                          <span className={expiryClass(entry.fecha_vencimiento)}>
                            {formatDate(entry.fecha_vencimiento)}
                          </span>
                          {badge && (
                            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full ${
                              badge === "Vencido" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                            }`}>
                              {badge}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-warm-gray text-sm">{entry.notas ?? "—"}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => startEdit(entry)}
                              className="px-3 py-1.5 text-xs text-brot hover:text-brot-dark transition-colors min-h-[36px]"
                            >
                              Editar
                            </button>
                            <button
                              onClick={() => { setDeleteConfirm(entry.id); setEditId(null); }}
                              className="px-3 py-1.5 text-xs text-red-600 hover:text-red-700 transition-colors min-h-[36px]"
                            >
                              Eliminar
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-cream-dark">
              {stock.map((entry) => {
                const badge = expiryBadge(entry.fecha_vencimiento);
                if (deleteConfirm === entry.id) {
                  return (
                    <div key={entry.id} className="px-4 py-3 bg-red-50 flex items-center gap-3 flex-wrap">
                      <span className="text-sm flex-1">
                        ¿Eliminar <strong>{entry.producto_nombre}</strong>?
                      </span>
                      <button
                        onClick={() => handleDelete(entry.id)}
                        disabled={saving}
                        className="px-3 py-2 bg-red-600 text-white rounded-lg text-sm min-h-[44px] disabled:opacity-50"
                      >
                        {saving ? "..." : "Eliminar"}
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-3 py-2 border border-cream-dark rounded-lg text-sm min-h-[44px]"
                      >
                        Cancelar
                      </button>
                    </div>
                  );
                }
                return (
                  <div key={entry.id} className="px-4 py-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-medium text-text">{entry.producto_nombre}</p>
                        <p className="text-xs text-warm-gray mt-0.5">
                          Entrada: {formatDate(entry.fecha_entrada)}
                        </p>
                        <div className="flex items-center gap-1 mt-1">
                          <span className={`text-xs ${expiryClass(entry.fecha_vencimiento)}`}>
                            Vence: {formatDate(entry.fecha_vencimiento)}
                          </span>
                          {badge && (
                            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                              badge === "Vencido" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                            }`}>
                              {badge}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="font-medium text-text">{entry.cantidad}</p>
                        <div className="flex gap-2 mt-2">
                          <button
                            onClick={() => startEdit(entry)}
                            className="text-xs text-brot min-h-[36px]"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() => { setDeleteConfirm(entry.id); setEditId(null); }}
                            className="text-xs text-red-600 min-h-[36px]"
                          >
                            Eliminar
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Create form */}
      <div className="bg-white rounded-xl border border-cream-dark p-5">
        <h3 className="font-medium mb-4">Nueva entrada de stock</h3>
        <form onSubmit={handleCreate}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Producto <span className="text-red-500">*</span>
              </label>
              <select
                value={form.producto_id}
                onChange={(e) => setForm({ ...form, producto_id: e.target.value })}
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[42px]"
              >
                <option value="">— Seleccionar —</option>
                {productos.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre} ({p.unidad})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Cantidad <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                value={form.cantidad}
                onChange={(e) => setForm({ ...form, cantidad: e.target.value })}
                placeholder="0"
                required
                min="0"
                step="0.001"
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Fecha de entrada
              </label>
              <input
                type="date"
                value={form.fecha_entrada}
                onChange={(e) => setForm({ ...form, fecha_entrada: e.target.value })}
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Fecha de vencimiento <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                value={form.fecha_vencimiento}
                onChange={(e) => setForm({ ...form, fecha_vencimiento: e.target.value })}
                required
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>

            <div className="sm:col-span-2 lg:col-span-2">
              <label className="block text-xs font-medium text-warm-gray mb-1">
                Notas
              </label>
              <input
                type="text"
                value={form.notas}
                onChange={(e) => setForm({ ...form, notas: e.target.value })}
                placeholder="Notas opcionales"
                className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
          </div>

          <div className="mt-4">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-brot text-white rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Añadir entrada"}
            </button>
          </div>
        </form>
      </div>

      {!loading && (
        <p className="text-xs text-warm-gray mt-3 text-right">
          {stock.length} entrada{stock.length !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
