"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface ProductoCongelado {
  id: number;
  receta_id: number | null;
}

export default function CongeladoRedirectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params?.id) return;
    apiFetch<ProductoCongelado>(`/api/congelados/productos/${params.id}/detalle`)
      .then((data) => {
        if (data.receta_id) {
          router.replace(`/escandallos/${data.receta_id}`);
        } else {
          setLoading(false);
        }
      })
      .catch(() => setLoading(false));
  }, [params?.id, router]);

  if (loading) return <div className="p-8 text-center text-warm-gray">Cargando...</div>;

  return (
    <div className="p-8 text-center text-warm-gray">
      Este producto no tiene receta vinculada.
    </div>
  );
}
