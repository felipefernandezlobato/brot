"use client";

import { formatARS } from "@/lib/format";
import { LineaLocal } from "@/lib/useLineasReceta";

export const UNIDADES = ["g", "kg", "ml", "litro", "unidad", "taza", "cdta", "cda", "sobre"];

interface Props {
  lineas: LineaLocal[];
  onAdd: () => void;
  onRemove: (key: number) => void;
  onChange: (key: number, field: "cantidad" | "unidad", value: string) => void;
  costoTotal: number;
}

export function RecetaLineasEditor({ lineas, onAdd, onRemove, onChange, costoTotal }: Props) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
          Ingredientes
        </h2>
        <button
          type="button"
          onClick={onAdd}
          className="bg-brot text-white px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] flex items-center hover:bg-brot-dark transition-colors"
        >
          + Agregar línea
        </button>
      </div>

      {lineas.length === 0 ? (
        <p className="text-warm-gray text-sm py-4 text-center">
          Sin ingredientes. Agrega al menos uno.
        </p>
      ) : (
        <div className="space-y-3">
          {lineas.map((l) => (
            <div key={l.key} className="flex items-center gap-3 p-3 bg-cream rounded-lg">
              <div className="flex-1 text-sm font-medium text-text min-w-0">
                <span className="truncate block">
                  {l.nombre}
                  {l.tipo === "subreceta" && (
                    <span className="ml-1 text-xs text-brot">(subreceta)</span>
                  )}
                </span>
              </div>
              <input
                type="number"
                value={l.cantidad}
                onChange={(e) => onChange(l.key, "cantidad", e.target.value)}
                min="0"
                step="0.01"
                className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
              />
              <select
                value={l.unidad}
                onChange={(e) => onChange(l.key, "unidad", e.target.value)}
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
                onClick={() => onRemove(l.key)}
                className="text-red-400 hover:text-red-600 p-1 min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
                aria-label="Eliminar línea"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      {lineas.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
          <span className="text-sm text-warm-gray">Costo estimado total</span>
          <span className="font-medium text-brot">{formatARS(costoTotal)}</span>
        </div>
      )}
    </div>
  );
}
