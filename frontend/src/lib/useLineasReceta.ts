import { useState } from "react";
import { PickerItem } from "@/components/IngredientOrSubrecetaPicker";

export interface LineaLocal {
  key: number;
  ingrediente_id: number | null;
  subreceta_id: number | null;
  tipo: "ingrediente" | "subreceta";
  nombre: string;
  cantidad: string;
  unidad: string;
  costoPorUnidad: number;
}

let lineaKey = 0;

export function useLineasReceta(initial: LineaLocal[] = []) {
  const [lineas, setLineas] = useState<LineaLocal[]>(initial);

  const addItem = (item: PickerItem) => {
    setLineas((prev) => [
      ...prev,
      {
        key: lineaKey++,
        ingrediente_id: item.tipo === "ingrediente" ? item.id : null,
        subreceta_id: item.tipo === "subreceta" ? item.id : null,
        tipo: item.tipo,
        nombre: item.nombre,
        cantidad: item.tipo === "subreceta" ? "1" : "100",
        unidad: item.unidad,
        costoPorUnidad: item.costoPorUnidad,
      },
    ]);
  };

  const removeLinea = (key: number) => {
    setLineas((prev) => prev.filter((l) => l.key !== key));
  };

  const updateLinea = (key: number, field: "cantidad" | "unidad", value: string) => {
    setLineas((prev) => prev.map((l) => (l.key === key ? { ...l, [field]: value } : l)));
  };

  const costoTotal = lineas.reduce((sum, l) => sum + (parseFloat(l.cantidad) || 0) * l.costoPorUnidad, 0);

  const toApiPayload = () =>
    lineas.map((l) => ({
      ingrediente_id: l.ingrediente_id,
      subreceta_id: l.subreceta_id,
      cantidad: parseFloat(l.cantidad) || 0,
      unidad: l.unidad,
    }));

  return { lineas, setLineas, addItem, removeLinea, updateLinea, costoTotal, toApiPayload };
}
