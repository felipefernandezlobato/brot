"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { PermissionGate } from "@/components/PermissionGate";

interface Ingrediente {
  id: number;
  nombre: string;
  unidad_uso: string;
  categoria_nombre: string;
  activo: boolean;
}

interface IngredienteRow {
  ingrediente_id: number;
  nombre: string;
  unidad: string;
  cantidad: string;
  notas: string;
  ubicacion: string;
  enabled: boolean;
}

export default function RegistroStockPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [ingredientes, setIngredientes] = useState<Ingrediente[]>([]);
  const [rows, setRows] = useState<IngredienteRow[]>([]);
  const [fecha, setFecha] = useState(() => new Date().toISOString().split("T")[0]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [buscar, setBuscar] = useState("");

  useEffect(() => {
    apiFetch<Ingrediente[]>("/api/ingredientes")
      .then((data) => {
        const activos = data.filter((i) => i.activo);
        setIngredientes(activos);
        setRows(
          activos.map((ing) => ({
            ingrediente_id: ing.id,
            nombre: ing.nombre,
            unidad: ing.unidad_uso,
            cantidad: "",
            notas: "",
            ubicacion: "",
            enabled: false,
          }))
        );
      })
      .catch(() => toast("Error al cargar ingredientes", "error"))
      .finally(() => setLoading(false));
  }, []);

  const filteredRows = rows.filter(
    (r) =>
      buscar === "" ||
      r.nombre.toLowerCase().includes(buscar.toLowerCase())
  );

  const updateRow = (
    ingredienteId: number,
    field: keyof IngredienteRow,
    value: string | boolean
  ) => {
    setRows((prev) =>
      prev.map((r) =>
        r.ingrediente_id === ingredienteId ? { ...r, [field]: value } : r
      )
    );
  };

  const enabledRows = rows.filter((r) => r.enabled && r.cantidad !== "");

  const handleSubmit = async () => {
    if (enabledRows.length === 0) {
      toast("Ingresá al menos un ingrediente con cantidad", "error");
      return;
    }

    const payload = enabledRows.map((r) => ({
      ingrediente_id: r.ingrediente_id,
      cantidad: parseFloat(r.cantidad),
      unidad: r.unidad,
      notas: r.notas || undefined,
      ubicacion: r.ubicacion || undefined,
      fecha: fecha,
    }));

    setSubmitting(true);
    try {
      await apiFetch("/api/inventario", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      toast(`${enabledRows.length} registros guardados correctamente`);
      router.push("/stock");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error desconocido";
      toast(`Error al guardar: ${msg}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleAll = (checked: boolean) => {
    setRows((prev) => prev.map((r) => ({ ...r, enabled: checked })));
  };

  return (
    <PermissionGate
      module="inventario"
      action="write"
      fallback={
        <div className="p-8 text-center text-warm-gray">
          No tenés permisos para registrar stock.
        </div>
      }
    >
      <div>
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => router.back()}
            className="text-warm-gray hover:text-text transition-colors p-1 min-h-[44px] min-w-[44px] flex items-center justify-center"
          >
            ←
          </button>
          <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
            Registrar Stock
          </h1>
        </div>

        {/* Date picker */}
        <div className="bg-white rounded-xl border border-cream-dark p-4 mb-4">
          <label className="block text-sm font-medium text-warm-gray mb-1">
            Fecha del conteo
          </label>
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="w-full md:w-56 px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
          />
        </div>

        {/* Instructions */}
        <p className="text-sm text-warm-gray mb-4">
          Activá la casilla de cada ingrediente que contaste e ingresá la
          cantidad actual. Solo los activados serán guardados.
        </p>

        {/* Search */}
        <div className="mb-3">
          <input
            type="search"
            placeholder="Buscar ingrediente..."
            value={buscar}
            onChange={(e) => setBuscar(e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg border border-cream-dark bg-white text-text placeholder:text-warm-gray focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
          />
        </div>

        {/* Select all */}
        {!loading && (
          <div className="flex items-center gap-3 mb-3 px-1">
            <label className="flex items-center gap-2 text-sm text-warm-gray cursor-pointer select-none">
              <input
                type="checkbox"
                className="w-4 h-4 accent-brot"
                onChange={(e) => toggleAll(e.target.checked)}
              />
              Seleccionar todos
            </label>
            {enabledRows.length > 0 && (
              <span className="text-xs text-brot font-medium">
                {enabledRows.length} seleccionado
                {enabledRows.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        )}

        {/* Ingredient rows */}
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden mb-6">
          {loading ? (
            <div className="p-8 text-center text-warm-gray">Cargando...</div>
          ) : filteredRows.length === 0 ? (
            <div className="p-8 text-center text-warm-gray">
              No se encontraron ingredientes.
            </div>
          ) : (
            <div className="divide-y divide-cream-dark">
              {filteredRows.map((row) => (
                <div
                  key={row.ingrediente_id}
                  className={`px-4 py-3 transition-colors ${
                    row.enabled ? "bg-brot/5" : ""
                  }`}
                >
                  {/* Top: checkbox + name */}
                  <div className="flex items-center gap-3 mb-2">
                    <input
                      type="checkbox"
                      checked={row.enabled}
                      onChange={(e) =>
                        updateRow(
                          row.ingrediente_id,
                          "enabled",
                          e.target.checked
                        )
                      }
                      className="w-4 h-4 accent-brot shrink-0"
                    />
                    <p className="font-medium text-text text-sm">{row.nombre}</p>
                  </div>

                  {/* Inputs (always visible but muted when disabled) */}
                  <div
                    className={`grid grid-cols-1 md:grid-cols-3 gap-2 pl-7 transition-opacity ${
                      row.enabled ? "opacity-100" : "opacity-40"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="0"
                        step="any"
                        placeholder="Cantidad"
                        value={row.cantidad}
                        disabled={!row.enabled}
                        onChange={(e) =>
                          updateRow(
                            row.ingrediente_id,
                            "cantidad",
                            e.target.value
                          )
                        }
                        className="flex-1 px-3 py-2 rounded-lg border border-cream-dark text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 disabled:bg-cream disabled:cursor-not-allowed min-h-[40px]"
                      />
                      <span className="text-xs text-warm-gray whitespace-nowrap">
                        {row.unidad}
                      </span>
                    </div>
                    <input
                      type="text"
                      placeholder="Ubicación (opcional)"
                      value={row.ubicacion}
                      disabled={!row.enabled}
                      onChange={(e) =>
                        updateRow(
                          row.ingrediente_id,
                          "ubicacion",
                          e.target.value
                        )
                      }
                      className="px-3 py-2 rounded-lg border border-cream-dark text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 disabled:bg-cream disabled:cursor-not-allowed min-h-[40px]"
                    />
                    <input
                      type="text"
                      placeholder="Notas (opcional)"
                      value={row.notas}
                      disabled={!row.enabled}
                      onChange={(e) =>
                        updateRow(row.ingrediente_id, "notas", e.target.value)
                      }
                      className="px-3 py-2 rounded-lg border border-cream-dark text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 disabled:bg-cream disabled:cursor-not-allowed min-h-[40px]"
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex gap-3 justify-end">
          <button
            onClick={() => router.back()}
            className="px-6 py-2.5 rounded-lg border border-cream-dark text-warm-gray hover:text-text hover:border-text transition-colors text-sm min-h-[44px]"
          >
            Cancelar
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || enabledRows.length === 0}
            className="bg-brot text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting
              ? "Guardando..."
              : `Guardar ${enabledRows.length > 0 ? `(${enabledRows.length})` : ""}`}
          </button>
        </div>
      </div>
    </PermissionGate>
  );
}
