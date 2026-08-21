"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import MermaForm, { MermaFormData } from "../../MermaForm";

interface MermaOut {
  id: number;
  ingrediente_id: number | null;
  receta_id: number | null;
  producto_congelado_id: number | null;
  nombre_libre: string | null;
  item_nombre: string;
  cantidad: number;
  unidad: string;
  motivo: MermaFormData["motivo"];
  notas: string | null;
  fecha: string;
}

function toFormData(m: MermaOut): MermaFormData {
  const modo: MermaFormData["modo"] = m.ingrediente_id
    ? "ingrediente"
    : m.producto_congelado_id
    ? "producto"
    : "libre";
  return {
    modo,
    ingrediente_id: m.ingrediente_id != null ? String(m.ingrediente_id) : "",
    producto_congelado_id: m.producto_congelado_id != null ? String(m.producto_congelado_id) : "",
    nombre_libre: m.nombre_libre ?? (modo === "libre" ? m.item_nombre : ""),
    cantidad: String(m.cantidad),
    unidad: m.unidad,
    motivo: m.motivo,
    notas: m.notas ?? "",
    fecha: m.fecha,
  };
}

export default function EditarMermaPage() {
  const router = useRouter();
  const { toast } = useToast();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [initialValues, setInitialValues] = useState<MermaFormData | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    apiFetch<MermaOut>(`/api/mermas/${id}`)
      .then((m) => setInitialValues(toFormData(m)))
      .catch(() => setNotFound(true));
  }, [id]);

  async function handleSubmit(body: Record<string, unknown>) {
    await apiFetch(`/api/mermas/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    toast("Merma actualizada correctamente");
    router.push("/mermas");
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => router.push("/mermas")}
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Volver
        </button>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Editar Merma
        </h1>
      </div>

      {notFound ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          No se encontró este registro de merma.
        </div>
      ) : !initialValues ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : (
        <MermaForm
          initialValues={initialValues}
          submitLabel="Guardar Cambios"
          onCancel={() => router.push("/mermas")}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}
