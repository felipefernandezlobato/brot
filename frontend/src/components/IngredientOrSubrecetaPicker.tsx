"use client";

import { useState } from "react";
import { formatARS } from "@/lib/format";

export interface PickerOption {
  id: number;
  nombre: string;
  unidad: string;
  costoPorUnidad: number;
}

export interface PickerItem extends PickerOption {
  tipo: "ingrediente" | "subreceta";
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (item: PickerItem) => void;
  ingredientes: PickerOption[];
  subrecetas?: PickerOption[];
  excludeRecetaId?: number;
  title?: string;
  searchPlaceholder?: string;
}

export function IngredientOrSubrecetaPicker({
  open,
  onClose,
  onSelect,
  ingredientes,
  subrecetas = [],
  excludeRecetaId,
  title = "Seleccionar",
  searchPlaceholder,
}: Props) {
  const [tab, setTab] = useState<"ingrediente" | "subreceta">("ingrediente");
  const [buscar, setBuscar] = useState("");

  if (!open) return null;

  const showTabs = subrecetas.length > 0;
  const subrecetasDisponibles = subrecetas.filter((s) => s.id !== excludeRecetaId);
  const activeList = tab === "ingrediente" ? ingredientes : subrecetasDisponibles;
  const filtered = activeList.filter((i) =>
    i.nombre.toLowerCase().includes(buscar.toLowerCase())
  );
  const placeholder =
    searchPlaceholder ?? (tab === "ingrediente" ? "Buscar ingrediente..." : "Buscar subreceta...");

  const close = () => {
    onClose();
    setBuscar("");
  };

  const handleSelect = (opt: PickerOption) => {
    onSelect({ ...opt, tipo: tab });
    close();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-white rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col shadow-xl">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-medium text-text">{title}</h3>
          <button
            onClick={close}
            className="text-warm-gray hover:text-text min-h-[44px] min-w-[44px] flex items-center justify-center text-xl leading-none"
            aria-label="Cerrar"
          >
            &times;
          </button>
        </div>

        {showTabs && (
          <div className="flex border-b border-gray-100">
            <button
              type="button"
              onClick={() => setTab("ingrediente")}
              className={`flex-1 py-2.5 text-sm font-medium min-h-[44px] ${
                tab === "ingrediente" ? "text-brot border-b-2 border-brot" : "text-warm-gray"
              }`}
            >
              Ingredientes
            </button>
            <button
              type="button"
              onClick={() => setTab("subreceta")}
              className={`flex-1 py-2.5 text-sm font-medium min-h-[44px] ${
                tab === "subreceta" ? "text-brot border-b-2 border-brot" : "text-warm-gray"
              }`}
            >
              Subrecetas
            </button>
          </div>
        )}

        <div className="p-3 border-b border-gray-100">
          <input
            type="search"
            placeholder={placeholder}
            value={buscar}
            onChange={(e) => setBuscar(e.target.value)}
            autoFocus
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="p-4 text-center text-warm-gray text-sm">No se encontraron resultados.</p>
          ) : (
            filtered.map((item) => (
              <button
                key={item.id}
                onClick={() => handleSelect(item)}
                className="w-full text-left px-4 py-3 hover:bg-cream transition-colors flex items-center justify-between border-b border-gray-50 min-h-[44px]"
              >
                <span className="text-sm font-medium text-text">
                  {item.nombre}
                  {tab === "subreceta" && <span className="ml-1 text-xs text-brot">(subreceta)</span>}
                </span>
                <span className="text-xs text-warm-gray">
                  {formatARS(item.costoPorUnidad)}/{item.unidad}
                </span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
