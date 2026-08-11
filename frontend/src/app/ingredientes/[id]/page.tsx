"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";
import { formatARS, formatDate } from "@/lib/format";
import { Categoria } from "@/lib/types";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

const UNIDADES = ["kg", "g", "litro", "ml", "unidad"];

interface Ingrediente {
  id: number;
  nombre: string;
  categoria_id: number;
  categoria_nombre: string;
  unidad_compra: string;
  cantidad_compra: number;
  precio_compra: number;
  unidad_uso: string;
  merma_porcentaje: number;
  proveedor: string | null;
  notas: string | null;
  activo: boolean;
  costo_por_unidad_uso: number;
  fecha_actualizacion: string;
}

interface HistorialPrecio {
  id: number;
  ingrediente_id: number;
  precio_anterior: number;
  precio_nuevo: number;
  fecha_cambio: string;
}

interface RecetaUsando {
  id: number;
  nombre: string;
  categoria: string;
  precio_venta: number | null;
  costo_porcion: number;
  multi: number | null;
}

interface PrecioProveedor {
  id: number;
  proveedor_id: number;
  proveedor_nombre: string;
  precio: number;
  unidad: string;
  fecha: string;
}

interface StockInfo {
  stock_actual: number;
  unidad: string;
  fecha_ultimo_conteo: string | null;
}

interface StockRecord {
  id: number;
  ingrediente_id: number;
  cantidad: number;
  unidad: string;
  fecha_registro: string;
  notas: string | null;
  ubicacion: string | null;
}

interface EditForm {
  nombre: string;
  categoria_id: string;
  unidad_compra: string;
  cantidad_compra: string;
  precio_compra: string;
  unidad_uso: string;
  merma_porcentaje: string;
  proveedor: string;
  notas: string;
  activo: boolean;
}

export default function IngredienteDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const { toast } = useToast();

  const [ingrediente, setIngrediente] = useState<Ingrediente | null>(null);
  const [historial, setHistorial] = useState<HistorialPrecio[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [recetas, setRecetas] = useState<RecetaUsando[]>([]);
  const [preciosProveedores, setPreciosProveedores] = useState<PrecioProveedor[]>([]);
  const [stockInfo, setStockInfo] = useState<StockInfo | null>(null);
  const [stockHistory, setStockHistory] = useState<StockRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editForm, setEditForm] = useState<EditForm | null>(null);

  const id = params?.id;

  useEffect(() => {
    if (!id) return;
    Promise.all([
      apiFetch<Ingrediente>(`/api/ingredientes/${id}`),
      apiFetch<HistorialPrecio[]>(`/api/ingredientes/${id}/historial`),
      apiFetch<Categoria[]>("/api/categorias?tipo=ingrediente"),
      apiFetch<RecetaUsando[]>(`/api/ingredientes/${id}/recetas`),
      apiFetch<PrecioProveedor[]>(`/api/ingredientes/${id}/precios-proveedores`),
      apiFetch<StockInfo>(`/api/ingredientes/${id}/stock`),
      apiFetch<StockRecord[]>(`/api/inventario?ingrediente_id=${id}`),
    ])
      .then(([ing, hist, cats, recs, precios, stock, stockHist]) => {
        setIngrediente(ing);
        setHistorial(hist);
        setCategorias(cats);
        setRecetas(recs);
        setPreciosProveedores(precios);
        setStockInfo(stock);
        setStockHistory(stockHist);
        initEditForm(ing);
      })
      .catch(() => toast("Error al cargar el ingrediente", "error"))
      .finally(() => setLoading(false));
  }, [id]);

  function initEditForm(ing: Ingrediente) {
    setEditForm({
      nombre: ing.nombre,
      categoria_id: String(ing.categoria_id),
      unidad_compra: ing.unidad_compra,
      cantidad_compra: String(ing.cantidad_compra),
      precio_compra: String(ing.precio_compra),
      unidad_uso: ing.unidad_uso,
      merma_porcentaje: String(ing.merma_porcentaje),
      proveedor: ing.proveedor ?? "",
      notas: ing.notas ?? "",
      activo: ing.activo,
    });
  }

  function setField(field: keyof EditForm, value: string | boolean) {
    setEditForm((prev) => (prev ? { ...prev, [field]: value } : prev));
  }

  function cancelEdit() {
    if (ingrediente) initEditForm(ingrediente);
    setEditing(false);
  }

  async function handleSave() {
    if (!editForm || !id) return;
    setSaving(true);
    try {
      const updated = await apiFetch<Ingrediente>(`/api/ingredientes/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          nombre: editForm.nombre.trim(),
          categoria_id: Number(editForm.categoria_id),
          unidad_compra: editForm.unidad_compra,
          cantidad_compra: Number(editForm.cantidad_compra),
          precio_compra: Number(editForm.precio_compra),
          unidad_uso: editForm.unidad_uso,
          merma_porcentaje: Number(editForm.merma_porcentaje) || 0,
          proveedor: editForm.proveedor.trim() || null,
          notas: editForm.notas.trim() || null,
          activo: editForm.activo,
        }),
      });
      setIngrediente(updated);
      // Refresh historial in case price changed
      const newHist = await apiFetch<HistorialPrecio[]>(
        `/api/ingredientes/${id}/historial`
      );
      setHistorial(newHist);
      setEditing(false);
      toast("Ingrediente actualizado correctamente");
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al actualizar",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!id) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/ingredientes/${id}`, { method: "DELETE" });
      toast("Ingrediente eliminado");
      router.push("/ingredientes");
    } catch (err: unknown) {
      toast(
        err instanceof Error ? err.message : "Error al eliminar",
        "error"
      );
      setDeleting(false);
      setShowDeleteModal(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8 text-center text-warm-gray">Cargando...</div>
    );
  }

  if (!ingrediente) {
    return (
      <div className="p-8 text-center text-warm-gray">
        Ingrediente no encontrado.
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/ingredientes")}
            className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
          >
            ← Volver
          </button>
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            {ingrediente.nombre}
          </h1>
          {!ingrediente.activo && (
            <span className="text-xs text-warm-gray bg-cream border border-cream-dark px-2 py-0.5 rounded-full">
              Inactivo
            </span>
          )}
        </div>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-warm-gray hover:border-brot hover:text-brot transition-colors min-h-[44px] text-sm font-medium"
            title="Editar"
          >
            Editar
          </button>
        )}
      </div>

      {/* View mode */}
      {!editing && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="bg-white border border-cream-dark rounded-xl p-4">
              <p className="text-xs text-warm-gray">Precio compra</p>
              <p className="text-lg font-bold text-text">{formatARS(ingrediente.precio_compra)}</p>
              <p className="text-xs text-warm-gray">/ {ingrediente.cantidad_compra} {ingrediente.unidad_compra}</p>
            </div>
            <div className="bg-white border border-brot/30 rounded-xl p-4">
              <p className="text-xs text-warm-gray">Costo / {ingrediente.unidad_uso}</p>
              <p className="text-lg font-bold text-brot">{formatARS(ingrediente.costo_por_unidad_uso)}</p>
            </div>
            <div className="bg-white border border-cream-dark rounded-xl p-4">
              <p className="text-xs text-warm-gray">Stock actual</p>
              <p className="text-lg font-bold text-text">
                {stockInfo ? `${stockInfo.stock_actual} ${stockInfo.unidad}` : "--"}
              </p>
              {stockInfo?.fecha_ultimo_conteo && (
                <p className="text-xs text-warm-gray">{formatDate(stockInfo.fecha_ultimo_conteo)}</p>
              )}
            </div>
            <div className="bg-white border border-cream-dark rounded-xl p-4">
              <p className="text-xs text-warm-gray">Recetas</p>
              <p className="text-lg font-bold text-text">{recetas.length}</p>
            </div>
          </div>

          {/* Info row */}
          <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
            <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <span><span className="text-warm-gray">Categoria:</span> <span className="font-medium text-text">{ingrediente.categoria_nombre}</span></span>
              <span><span className="text-warm-gray">Proveedor:</span> <span className="font-medium text-text">{ingrediente.proveedor ?? "--"}</span></span>
              <span><span className="text-warm-gray">Merma:</span> <span className="font-medium text-text">{ingrediente.merma_porcentaje}%</span></span>
              <span><span className="text-warm-gray">Unidades:</span> <span className="font-medium text-text">{ingrediente.unidad_compra} → {ingrediente.unidad_uso}</span></span>
              <span><span className="text-warm-gray">Actualizado:</span> <span className="font-medium text-text">{formatDate(ingrediente.fecha_actualizacion)}</span></span>
            </div>
            {ingrediente.notas && (
              <p className="text-xs text-warm-gray mt-2 pt-2 border-t border-cream-dark">{ingrediente.notas}</p>
            )}
          </div>

          {/* Recipes using this ingredient */}
          {recetas.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
              <div className="px-4 py-3 border-b border-cream-dark">
                <h2 className="font-medium text-text text-sm">Recetas que lo usan ({recetas.length})</h2>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-2 font-medium text-warm-gray">Receta</th>
                    <th className="text-left px-3 py-2 font-medium text-warm-gray">Categoria</th>
                    <th className="text-right px-3 py-2 font-medium text-warm-gray">Costo</th>
                    <th className="text-right px-3 py-2 font-medium text-warm-gray">PVP</th>
                    <th className="text-right px-4 py-2 font-medium text-warm-gray">Multi</th>
                  </tr>
                </thead>
                <tbody>
                  {recetas.map((r, idx) => (
                    <tr
                      key={r.id}
                      onClick={() => router.push(`/escandallos`)}
                      className={`cursor-pointer hover:bg-cream/40 ${idx < recetas.length - 1 ? "border-b border-cream-dark" : ""}`}
                    >
                      <td className="px-4 py-2 font-medium text-text">{r.nombre}</td>
                      <td className="px-3 py-2 text-warm-gray">{r.categoria}</td>
                      <td className="px-3 py-2 text-right text-text tabular-nums">{formatARS(r.costo_porcion)}</td>
                      <td className="px-3 py-2 text-right text-text tabular-nums">{r.precio_venta ? formatARS(r.precio_venta) : "--"}</td>
                      <td className="px-4 py-2 text-right">
                        {r.multi ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            r.multi >= 3 ? "bg-green-100 text-green-700" :
                            r.multi >= 2 ? "bg-amber-100 text-amber-700" :
                            "bg-red-100 text-red-700"
                          }`}>
                            x{r.multi}
                          </span>
                        ) : "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Supplier prices */}
          {preciosProveedores.length > 0 && (
            <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-4">
              <div className="px-4 py-3 border-b border-cream-dark">
                <h2 className="font-medium text-text text-sm">Precios por proveedor</h2>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark bg-cream/50">
                    <th className="text-left px-4 py-2 font-medium text-warm-gray">Proveedor</th>
                    <th className="text-right px-3 py-2 font-medium text-warm-gray">Precio</th>
                    <th className="text-left px-3 py-2 font-medium text-warm-gray">Unidad</th>
                    <th className="text-left px-4 py-2 font-medium text-warm-gray">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {preciosProveedores
                    .sort((a, b) => a.precio - b.precio)
                    .map((p, idx) => (
                      <tr
                        key={p.id}
                        className={`${idx < preciosProveedores.length - 1 ? "border-b border-cream-dark" : ""} ${
                          idx === 0 ? "bg-green-50/50" : ""
                        }`}
                      >
                        <td className="px-4 py-2 font-medium text-text">
                          {p.proveedor_nombre}
                          {idx === 0 && <span className="ml-2 text-xs text-green-600">Mejor precio</span>}
                        </td>
                        <td className="px-3 py-2 text-right font-medium text-text tabular-nums">{formatARS(p.precio)}</td>
                        <td className="px-3 py-2 text-warm-gray">{p.unidad}</td>
                        <td className="px-4 py-2 text-warm-gray">{formatDate(p.fecha)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Stock evolution + consumption chart */}
          {stockHistory.length > 1 && (() => {
            const sorted = stockHistory
              .slice()
              .sort((a, b) => a.fecha_registro.localeCompare(b.fecha_registro));
            const chartData = sorted.map((r, i) => {
              let consumo = 0;
              if (i > 0) {
                const prev = sorted[i - 1];
                const dias = (new Date(r.fecha_registro).getTime() - new Date(prev.fecha_registro).getTime()) / (1000 * 60 * 60 * 24);
                if (dias > 0) {
                  const diff = prev.cantidad - r.cantidad;
                  consumo = Math.max(0, Math.round((diff / dias) * 7 * 10) / 10);
                }
              }
              return { fecha: r.fecha_registro, stock: r.cantidad, consumo };
            });
            return (
            <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4">
              <h2 className="font-medium text-text mb-3">Evolucion de stock y consumo semanal</h2>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E8DFD3" />
                  <XAxis
                    dataKey="fecha"
                    tick={{ fontSize: 11, fill: "#6B5E52" }}
                    tickFormatter={(v: string) => {
                      const d = new Date(v + "T00:00:00");
                      return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" });
                    }}
                  />
                  <YAxis yAxisId="left" tick={{ fontSize: 11, fill: "#6B5E52" }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: "#dc2626" }} />
                  <Tooltip
                    labelFormatter={(v) => formatDate(String(v))}
                    contentStyle={{ borderRadius: "8px", border: "1px solid #E8DFD3", fontSize: "13px" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Bar yAxisId="right" dataKey="consumo" name="Consumo/sem" fill="#dc2626" opacity={0.3} barSize={20} />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="stock"
                    name="Stock"
                    stroke="#004225"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#004225" }}
                    connectNulls
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            );
          })()}

          {/* Price history */}
          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4">
            <h2 className="font-medium text-text mb-3">
              Historial de precios
            </h2>
            {historial.length === 0 ? (
              <p className="text-sm text-warm-gray">
                Sin cambios de precio registrados.
              </p>
            ) : (
              <div className="space-y-2">
                {historial.map((h) => {
                  const pctChange = h.precio_anterior > 0
                    ? ((h.precio_nuevo - h.precio_anterior) / h.precio_anterior * 100)
                    : 0;
                  return (
                    <div
                      key={h.id}
                      className="flex items-center justify-between text-sm py-2 border-b border-cream-dark last:border-0"
                    >
                      <span className="text-warm-gray">
                        {formatDate(h.fecha_cambio)}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-warm-gray line-through">
                          {formatARS(h.precio_anterior)}
                        </span>
                        <span className="text-warm-gray">→</span>
                        <span className="font-medium text-brot">
                          {formatARS(h.precio_nuevo)}
                        </span>
                        {pctChange !== 0 && (
                          <span className={`text-xs font-medium ${pctChange > 0 ? "text-red-600" : "text-green-600"}`}>
                            {pctChange > 0 ? "+" : ""}{pctChange.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Delete */}
          <PermissionGate module="ingredientes" action="delete">
            <div className="bg-white rounded-xl border border-cream-dark p-5">
              <h2 className="font-medium text-text mb-2">Zona de peligro</h2>
              <p className="text-sm text-warm-gray mb-3">
                Eliminar este ingrediente de forma permanente.
              </p>
              <button
                onClick={() => setShowDeleteModal(true)}
                className="px-4 py-2.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors text-sm font-medium min-h-[44px]"
              >
                Eliminar ingrediente
              </button>
            </div>
          </PermissionGate>
        </>
      )}

      {/* Edit mode */}
      {editing && editForm && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
        >
          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Información básica
            </h2>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Nombre
              </label>
              <input
                type="text"
                value={editForm.nombre}
                onChange={(e) => setField("nombre", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Categoría
              </label>
              <select
                value={editForm.categoria_id}
                onChange={(e) => setField("categoria_id", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              >
                {categorias.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.nombre}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Proveedor
              </label>
              <input
                type="text"
                value={editForm.proveedor}
                onChange={(e) => setField("proveedor", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Datos de compra
            </h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Cantidad
                </label>
                <input
                  type="text"
                  inputMode="decimal"
                  value={editForm.cantidad_compra}
                  onChange={(e) => setField("cantidad_compra", e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Unidad de compra
                </label>
                <select
                  value={editForm.unidad_compra}
                  onChange={(e) => setField("unidad_compra", e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
                >
                  {UNIDADES.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Precio de compra (ARS)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={editForm.precio_compra}
                onChange={(e) => setField("precio_compra", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Datos de uso
            </h2>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Unidad de uso
              </label>
              <select
                value={editForm.unidad_uso}
                onChange={(e) => setField("unidad_uso", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              >
                {UNIDADES.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Merma (%)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={editForm.merma_porcentaje}
                onChange={(e) => setField("merma_porcentaje", e.target.value)}
                className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
              />
            </div>
          </div>

          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-4 space-y-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Notas
            </h2>
            <textarea
              value={editForm.notas}
              onChange={(e) => setField("notas", e.target.value)}
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
            />
          </div>

          {/* Activo toggle */}
          <div className="bg-white rounded-xl border border-cream-dark p-5 mb-6">
            <label className="flex items-center gap-3 cursor-pointer min-h-[44px]">
              <input
                type="checkbox"
                checked={editForm.activo}
                onChange={(e) => setField("activo", e.target.checked)}
                className="w-5 h-5 accent-brot"
              />
              <div>
                <p className="font-medium text-text text-sm">Activo</p>
                <p className="text-xs text-warm-gray">
                  Los ingredientes inactivos no aparecen en nuevas recetas
                </p>
              </div>
            </label>
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={cancelEdit}
              className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-3 rounded-lg bg-brot text-white hover:bg-brot-dark transition-colors min-h-[44px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </form>
      )}

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-xl">
            <h2 className="font-[family-name:var(--font-garamond)] text-xl text-text mb-2">
              ¿Eliminar ingrediente?
            </h2>
            <p className="text-sm text-warm-gray mb-6">
              Esta acción no se puede deshacer. Se eliminará{" "}
              <strong>{ingrediente.nombre}</strong> de forma permanente.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
                className="flex-1 px-4 py-3 rounded-lg border border-cream-dark bg-white text-warm-gray hover:bg-cream transition-colors min-h-[44px] font-medium"
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 px-4 py-3 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors min-h-[44px] font-medium disabled:opacity-50"
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

function InfoRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-xs text-warm-gray mb-0.5">{label}</p>
      <p
        className={`text-sm font-medium ${
          highlight ? "text-brot" : "text-text"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
