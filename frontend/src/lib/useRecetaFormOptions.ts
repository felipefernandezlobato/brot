import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Categoria, SubrecetaOpt } from "@/lib/types";
import { PickerOption } from "@/components/IngredientOrSubrecetaPicker";

interface IngredienteOpt {
  id: number;
  nombre: string;
  unidad_uso: string;
  costo_por_unidad_uso: number;
}

export function useRecetaFormOptions() {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [ingredientesOpts, setIngredientesOpts] = useState<PickerOption[]>([]);
  const [subrecetasOpts, setSubrecetasOpts] = useState<PickerOption[]>([]);

  useEffect(() => {
    apiFetch<Categoria[]>("/api/categorias?tipo=receta").then(setCategorias);
    apiFetch<IngredienteOpt[]>("/api/ingredientes").then((ings) =>
      setIngredientesOpts(
        ings.map((i) => ({
          id: i.id,
          nombre: i.nombre,
          unidad: i.unidad_uso,
          costoPorUnidad: i.costo_por_unidad_uso,
        }))
      )
    );
    apiFetch<SubrecetaOpt[]>("/api/recetas?es_subreceta=true").then((subs) =>
      setSubrecetasOpts(
        subs.map((s) => ({
          id: s.id,
          nombre: s.nombre,
          unidad: s.unidad_rendimiento || "unidad",
          costoPorUnidad: s.costo_por_porcion,
        }))
      )
    );
  }, []);

  return { categorias, ingredientesOpts, subrecetasOpts };
}
