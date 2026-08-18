"use client";

import { Categoria } from "@/lib/types";

interface Props {
  nombre: string;
  onNombreChange: (v: string) => void;
  categoriaId: string;
  onCategoriaIdChange: (v: string) => void;
  categorias: Categoria[];
  porciones: string;
  onPorcionesChange: (v: string) => void;
  precioVenta: string;
  onPrecioVentaChange: (v: string) => void;
  esSubreceta: boolean;
  onEsSubrecetaChange: (v: boolean) => void;
  unidadRendimiento: string;
  onUnidadRendimientoChange: (v: string) => void;
  notas: string;
  onNotasChange: (v: string) => void;
}

export function RecetaInfoFields({
  nombre,
  onNombreChange,
  categoriaId,
  onCategoriaIdChange,
  categorias,
  porciones,
  onPorcionesChange,
  precioVenta,
  onPrecioVentaChange,
  esSubreceta,
  onEsSubrecetaChange,
  unidadRendimiento,
  onUnidadRendimientoChange,
  notas,
  onNotasChange,
}: Props) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm space-y-4">
      <h2 className="font-medium text-sm uppercase tracking-wide text-warm-gray">
        Información básica
      </h2>

      <div>
        <label className="block text-sm font-medium text-text mb-1">Nombre *</label>
        <input
          type="text"
          value={nombre}
          onChange={(e) => onNombreChange(e.target.value)}
          placeholder="Ej: Pan de masa madre 400g"
          className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
          required
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-text mb-1">Categoría *</label>
          <select
            value={categoriaId}
            onChange={(e) => onCategoriaIdChange(e.target.value)}
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
          <label className="block text-sm font-medium text-text mb-1">Porciones por lote</label>
          <input
            type="number"
            value={porciones}
            onChange={(e) => onPorcionesChange(e.target.value)}
            min="0.01"
            step="0.01"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-text mb-1">Precio de venta (ARS)</label>
          <input
            type="number"
            value={precioVenta}
            onChange={(e) => onPrecioVentaChange(e.target.value)}
            min="0"
            step="0.01"
            placeholder="Opcional"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div className="flex items-center gap-3 pt-7">
          <input
            type="checkbox"
            id="esSubreceta"
            checked={esSubreceta}
            onChange={(e) => onEsSubrecetaChange(e.target.checked)}
            className="w-5 h-5 accent-brot"
          />
          <label htmlFor="esSubreceta" className="text-sm font-medium text-text">
            Es subreceta
          </label>
        </div>
      </div>

      {esSubreceta && (
        <div>
          <label className="block text-sm font-medium text-text mb-1">Unidad de rendimiento</label>
          <input
            type="text"
            value={unidadRendimiento}
            onChange={(e) => onUnidadRendimientoChange(e.target.value)}
            placeholder="Ej: g, ml, unidad..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-text mb-1">Notas</label>
        <textarea
          value={notas}
          onChange={(e) => onNotasChange(e.target.value)}
          rows={3}
          placeholder="Observaciones, instrucciones especiales..."
          className="w-full border border-gray-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brot/30 resize-none"
        />
      </div>
    </div>
  );
}
