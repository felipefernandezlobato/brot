"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { Categoria } from "@/lib/types";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

interface LineaRecetaOut {
  id: number;
  ingrediente_id: number | null;
  subreceta_id: number | null;
  cantidad: number;
  unidad: string;
  nombre: string;
  costo_linea: number;
}

interface RecetaOut {
  id: number;
  nombre: string;
  categoria_id: number;
  categoria_nombre: string;
  porciones_por_lote: number;
  precio_venta: number | null;
  es_subreceta: boolean;
  unidad_rendimiento: string | null;
  notas: string | null;
  costo_total: number;
  costo_por_porcion: number;
  margen: number | null;
  multi: number | null;
  lineas: LineaRecetaOut[];
}

interface IngredienteOpt {
  id: number;
  nombre: string;
  unidad_uso: string;
  costo_por_unidad_uso: number;
}

interface LineaLocal {
  key: number;
  ingrediente_id: number | null;
  subreceta_id: number | null;
  nombre: string;
  cantidad: string;
  unidad: string;
  costo_por_unidad_uso: number;
}

const UNIDADES = [
  "g",
  "kg",
  "ml",
  "l",
  "unidad",
  "taza",
  "cdta",
  "cda",
  "sobre",
];

let lineaKey = 1000;

function MargenBadge({ margen }: { margen: number | null }) {
  if (margen === null) return <span className="text-warm-gray">—</span>;
  const color =
    margen >= 40
      ? "text-green-700"
      : margen >= 25
      ? "text-yellow-700"
      : "text-red-700";
  return <span className={`font-medium ${color}`}>{margen.toFixed(1)}%</span>;
}

export default function RecetaDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const id = params.id as string;

  const [receta, setReceta] = useState<RecetaOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Edit form state
  const [nombre, setNombre] = useState("");
  const [categoriaId, setCategoriaId] = useState("");
  const [porciones, setPorciones] = useState("1");
  const [precioVenta, setPrecioVenta] = useState("");
  const [esSubreceta, setEsSubreceta] = useState(false);
  const [unidadRendimiento, setUnidadRendimiento] = useState("");
  const [notas, setNotas] = useState("");
  const [lineas, setLineas] = useState<LineaLocal[]>([]);

  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [ingredientes, setIngredientes] = useState<IngredienteOpt[]>([]);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorBuscar, setSelectorBuscar] = useState("");

  useEffect(() => {
    apiFetch<RecetaOut>(`/api/recetas/${id}`)
      .then(setReceta)
      .catch(() => toast("Error al cargar la receta", "error"))
      .finally(() => setLoading(false));

    apiFetch<Categoria[]>("/api/categorias?tipo=receta").then(setCategorias);
    apiFetch<IngredienteOpt[]>("/api/ingredientes").then(setIngredientes);
  }, [id, toast]);

  const enterEditMode = () => {
    if (!receta) return;
    setNombre(receta.nombre);
    setCategoriaId(String(receta.categoria_id));
    setPorciones(String(receta.porciones_por_lote));
    setPrecioVenta(
      receta.precio_venta !== null ? String(receta.precio_venta) : ""
    );
    setEsSubreceta(receta.es_subreceta);
    setUnidadRendimiento(receta.unidad_rendimiento || "");
    setNotas(receta.notas || "");
    setLineas(
      receta.lineas.map((l) => ({
        key: lineaKey++,
        ingrediente_id: l.ingrediente_id,
        subreceta_id: l.subreceta_id,
        nombre: l.nombre,
        cantidad: String(l.cantidad),
        unidad: l.unidad,
        costo_por_unidad_uso: l.cantidad > 0 ? l.costo_linea / l.cantidad : 0,
      }))
    );
    setEditMode(true);
  };

  const cancelEdit = () => {
    setEditMode(false);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nombre.trim() || !categoriaId) {
      toast("Nombre y categoría son obligatorios", "error");
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        nombre: nombre.trim(),
        categoria_id: parseInt(categoriaId),
        porciones_por_lote: parseFloat(porciones) || 1,
        precio_venta: precioVenta ? parseFloat(precioVenta) : null,
        es_subreceta: esSubreceta,
        unidad_rendimiento: esSubreceta ? unidadRendimiento || null : null,
        notas: notas || null,
        lineas: lineas.map((l) => ({
          ingrediente_id: l.ingrediente_id,
          subreceta_id: l.subreceta_id,
          cantidad: parseFloat(l.cantidad) || 0,
          unidad: l.unidad,
        })),
      };
      const updated = await apiFetch<RecetaOut>(`/api/recetas/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setReceta(updated);
      setEditMode(false);
      toast("Receta actualizada");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al guardar";
      toast(msg, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await apiFetch(`/api/recetas/${id}`, { method: "DELETE" });
      toast("Receta eliminada");
      router.push("/escandallos");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al eliminar";
      toast(msg, "error");
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const ingFiltered = ingredientes.filter((i) =>
    i.nombre.toLowerCase().includes(selectorBuscar.toLowerCase())
  );

  const addIngrediente = (ing: IngredienteOpt) => {
    setLineas((prev) => [
      ...prev,
      {
        key: lineaKey++,
        ingrediente_id: ing.id,
        subreceta_id: null,
        nombre: ing.nombre,
        cantidad: "100",
        unidad: ing.unidad_uso,
        costo_por_unidad_uso: ing.costo_por_unidad_uso,
      },
    ]);
    setSelectorOpen(false);
    setSelectorBuscar("");
  };

  const removeLinea = (key: number) => {
    setLineas((prev) => prev.filter((l) => l.key !== key));
  };

  const updateLinea = (
    key: number,
    field: "cantidad" | "unidad",
    value: string
  ) => {
    setLineas((prev) =>
      prev.map((l) => (l.key === key ? { ...l, [field]: value } : l))
    );
  };

  const costoEstimado = lineas.reduce((sum, l) => {
    const cant = parseFloat(l.cantidad) || 0;
    return sum + cant * l.costo_por_unidad_uso;
  }, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-16">
        <p className="text-warm-gray">Cargando...</p>
      </div>
    );
  }

  if (!receta) {
    return (
      <div className="text-center p-16">
        <p className="text-warm-gray mb-4">Receta no encontrada.</p>
        <Link href="/escandallos" className="text-brot hover:underline">
          ← Volver a escandallos
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
            href="/escandallos"
            className="text-warm-gray hover:text-brot text-sm transition-colors"
          >
            ← Escandallos
          </Link>
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mt-1">
            {receta.nombre}
          </h1>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="text-sm text-warm-gray">
              {receta.categoria_nombre}
            </span>
            {receta.es_subreceta && (
              <span className="px-2 py-0.5 bg-brot/10 text-brot text-xs rounded-full">
                subreceta
              </span>
            )}
            {receta.unidad_rendimiento && (
              <span className="text-xs text-warm-gray">
                · {receta.unidad_rendimiento}
              </span>
            )}
          </div>
        </div>

        {!editMode && (
          <div className="flex gap-2 shrink-0">
            <PermissionGate module="recetas" action="update">
              <button
                onClick={enterEditMode}
                className="border border-brot text-brot px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot hover:text-white transition-colors"
              >
                Editar
              </button>
            </PermissionGate>
            <PermissionGate module="recetas" action="delete">
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="border border-red-300 text-red-500 px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-red-50 transition-colors"
              >
                Eliminar
              </button>
            </PermissionGate>
          </div>
        )}
      </div>

      {!editMode ? (
        /* VIEW MODE */
        <div className="space-y-6">
          {/* Cost card summary */}
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray mb-4">
              Resumen de costos
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-cream rounded-lg p-4">
                <p className="text-xs text-warm-gray mb-1">Costo total lote</p>
                <p className="font-medium text-text">
                  {formatARS(receta.costo_total)}
                </p>
              </div>
              <div className="bg-cream rounded-lg p-4">
                <p className="text-xs text-warm-gray mb-1">Costo / porción</p>
                <p className="font-medium text-text">
                  {formatARS(receta.costo_por_porcion)}
                </p>
                <p className="text-xs text-warm-gray mt-1">
                  {receta.porciones_por_lote}{" "}
                  {receta.porciones_por_lote === 1 ? "porción" : "porciones"}/lote
                </p>
              </div>
              <div className="bg-cream rounded-lg p-4">
                <p className="text-xs text-warm-gray mb-1">PVP</p>
                <p className="font-medium text-text">
                  {receta.precio_venta !== null
                    ? formatARS(receta.precio_venta)
                    : "—"}
                </p>
              </div>
              <div className="bg-cream rounded-lg p-4">
                <p className="text-xs text-warm-gray mb-1">Margen / Multi</p>
                <p className="font-medium">
                  <MargenBadge margen={receta.margen} />
                </p>
                <p className="text-xs text-warm-gray mt-1">
                  {receta.multi !== null
                    ? `${receta.multi.toFixed(2)}×`
                    : "—"}
                </p>
              </div>
            </div>
          </div>

          {/* Line items table */}
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100">
              <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
                Ingredientes
              </h2>
            </div>
            {receta.lineas.length === 0 ? (
              <p className="p-6 text-center text-warm-gray text-sm">
                Sin ingredientes registrados.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-warm-gray text-xs uppercase tracking-wide">
                      <th className="text-left px-6 py-3">Ingrediente</th>
                      <th className="text-right px-6 py-3">Cantidad</th>
                      <th className="text-right px-6 py-3">Unidad</th>
                      <th className="text-right px-6 py-3">Costo línea</th>
                    </tr>
                  </thead>
                  <tbody>
                    {receta.lineas.map((l) => (
                      <tr
                        key={l.id}
                        className="border-b border-gray-50 last:border-0"
                      >
                        <td className="px-6 py-3 font-medium text-text">
                          <span>{l.nombre}</span>
                          {l.subreceta_id !== null && (
                            <Link
                              href={`/escandallos/${l.subreceta_id}`}
                              className="ml-2 text-xs text-brot hover:underline"
                            >
                              (subreceta)
                            </Link>
                          )}
                        </td>
                        <td className="px-6 py-3 text-right font-mono">
                          {l.cantidad}
                        </td>
                        <td className="px-6 py-3 text-right text-warm-gray">
                          {l.unidad}
                        </td>
                        <td className="px-6 py-3 text-right font-mono">
                          {formatARS(l.costo_linea)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t border-gray-200 bg-cream/50">
                      <td
                        colSpan={3}
                        className="px-6 py-3 text-right font-medium text-text text-sm"
                      >
                        Total lote
                      </td>
                      <td className="px-6 py-3 text-right font-medium text-brot font-mono">
                        {formatARS(receta.costo_total)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>

          {/* Notas */}
          {receta.notas && (
            <div className="bg-white rounded-xl p-6 shadow-sm">
              <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray mb-2">
                Notas
              </h2>
              <p className="text-sm text-text whitespace-pre-line">
                {receta.notas}
              </p>
            </div>
          )}
        </div>
      ) : (
        /* EDIT MODE */
        <form onSubmit={handleSave} className="space-y-6">
          <div className="bg-white rounded-xl p-6 shadow-sm space-y-4">
            <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
              Información básica
            </h2>

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Nombre *
              </label>
              <input
                type="text"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Categoría *
                </label>
                <select
                  value={categoriaId}
                  onChange={(e) => setCategoriaId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                  required
                >
                  <option value="">Seleccionar...</option>
                  {categorias.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Porciones por lote
                </label>
                <input
                  type="number"
                  value={porciones}
                  onChange={(e) => setPorciones(e.target.value)}
                  min="0.01"
                  step="0.01"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Precio de venta (ARS)
                </label>
                <input
                  type="number"
                  value={precioVenta}
                  onChange={(e) => setPrecioVenta(e.target.value)}
                  min="0"
                  step="0.01"
                  placeholder="Opcional"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>

              <div className="flex items-center gap-3 pt-7">
                <input
                  type="checkbox"
                  id="esSubrecetaEdit"
                  checked={esSubreceta}
                  onChange={(e) => setEsSubreceta(e.target.checked)}
                  className="w-5 h-5 accent-brot"
                />
                <label
                  htmlFor="esSubrecetaEdit"
                  className="text-sm font-medium text-text"
                >
                  Es subreceta
                </label>
              </div>
            </div>

            {esSubreceta && (
              <div>
                <label className="block text-sm font-medium text-text mb-1">
                  Unidad de rendimiento
                </label>
                <input
                  type="text"
                  value={unidadRendimiento}
                  onChange={(e) => setUnidadRendimiento(e.target.value)}
                  placeholder="Ej: g, ml, unidad..."
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-text mb-1">
                Notas
              </label>
              <textarea
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
              />
            </div>
          </div>

          {/* Edit line items */}
          <div className="bg-white rounded-xl p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
                Ingredientes
              </h2>
              <button
                type="button"
                onClick={() => setSelectorOpen(true)}
                className="bg-brot text-white px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] flex items-center hover:bg-brot-dark transition-colors"
              >
                + Agregar
              </button>
            </div>

            {lineas.length === 0 ? (
              <p className="text-warm-gray text-sm py-4 text-center">
                Sin ingredientes.
              </p>
            ) : (
              <div className="space-y-3">
                {lineas.map((l) => (
                  <div
                    key={l.key}
                    className="flex items-center gap-3 p-3 bg-cream rounded-lg"
                  >
                    <div className="flex-1 text-sm font-medium text-text min-w-0">
                      <span className="truncate block">{l.nombre}</span>
                    </div>
                    <input
                      type="number"
                      value={l.cantidad}
                      onChange={(e) =>
                        updateLinea(l.key, "cantidad", e.target.value)
                      }
                      min="0"
                      step="0.01"
                      className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                    />
                    <select
                      value={l.unidad}
                      onChange={(e) =>
                        updateLinea(l.key, "unidad", e.target.value)
                      }
                      className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
                    >
                      {UNIDADES.map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => removeLinea(l.key)}
                      className="text-red-400 hover:text-red-600 p-1 min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
                      aria-label="Eliminar ingrediente"
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}

            {lineas.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
                <span className="text-sm text-warm-gray">Costo estimado</span>
                <span className="font-medium text-brot">
                  {formatARS(costoEstimado)}
                </span>
              </div>
            )}
          </div>

          <div className="flex gap-3 justify-end pb-4">
            <button
              type="button"
              onClick={cancelEdit}
              className="px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-warm-gray hover:bg-cream transition-colors min-h-[44px]"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="bg-brot text-white px-6 py-2 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {submitting ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </form>
      )}

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-xl">
            <h3 className="font-medium text-text text-lg mb-2">
              Eliminar receta
            </h3>
            <p className="text-warm-gray text-sm mb-6">
              Esta acción no se puede deshacer. La receta{" "}
              <strong className="text-text">{receta.nombre}</strong> y todas
              sus líneas se eliminarán permanentemente.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
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

      {/* Ingredient selector modal */}
      {selectorOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col shadow-xl">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-medium text-text">
                Seleccionar ingrediente
              </h3>
              <button
                onClick={() => {
                  setSelectorOpen(false);
                  setSelectorBuscar("");
                }}
                className="text-warm-gray hover:text-text min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
                aria-label="Cerrar"
              >
                &times;
              </button>
            </div>
            <div className="p-3 border-b border-gray-100">
              <input
                type="search"
                placeholder="Buscar ingrediente..."
                value={selectorBuscar}
                onChange={(e) => setSelectorBuscar(e.target.value)}
                autoFocus
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
            </div>
            <div className="flex-1 overflow-y-auto">
              {ingFiltered.length === 0 ? (
                <p className="p-4 text-center text-warm-gray text-sm">
                  No se encontraron ingredientes.
                </p>
              ) : (
                ingFiltered.map((i) => (
                  <button
                    key={i.id}
                    onClick={() => addIngrediente(i)}
                    className="w-full text-left px-4 py-3 hover:bg-cream transition-colors flex items-center justify-between border-b border-gray-50 min-h-[44px]"
                  >
                    <span className="text-sm font-medium text-text">
                      {i.nombre}
                    </span>
                    <span className="text-xs text-warm-gray">
                      {formatARS(i.costo_por_unidad_uso)}/{i.unidad_uso}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
