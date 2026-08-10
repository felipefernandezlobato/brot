"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface Alerta {
  ingrediente_id: number;
  ingrediente_nombre: string;
  cantidad: number | null;
  unidad: string;
  alerta: "sin_stock" | "sin_registro";
  fecha_registro: string | null;
}

export default function AlertasStockPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [loading, setLoading] = useState(true);

  const cargar = () => {
    setLoading(true);
    apiFetch<Alerta[]>("/api/inventario/alertas")
      .then(setAlertas)
      .catch(() => toast("Error al cargar alertas", "error"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    cargar();
  }, []);

  const sinStock = alertas.filter((a) => a.alerta === "sin_stock");
  const sinRegistro = alertas.filter((a) => a.alerta === "sin_registro");

  const alertaBadge = (alerta: Alerta["alerta"]) =>
    alerta === "sin_stock" ? (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
        Sin stock
      </span>
    ) : (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
        Sin registro
      </span>
    );

  const AlertaCard = ({ alerta }: { alerta: Alerta }) => (
    <div
      className={`px-4 py-4 ${
        alerta.alerta === "sin_stock" ? "bg-red-50" : "bg-amber-50"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-text">{alerta.ingrediente_nombre}</p>
          {alerta.fecha_registro && (
            <p className="text-xs text-warm-gray mt-0.5">
              Ultimo registro:{" "}
              {new Date(alerta.fecha_registro).toLocaleDateString("es-AR", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
              })}
            </p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-sm font-bold text-text">
            {alerta.cantidad ?? 0}{" "}
            <span className="font-normal text-warm-gray">{alerta.unidad}</span>
          </p>
          <div className="mt-1">{alertaBadge(alerta.alerta)}</div>
        </div>
      </div>
    </div>
  );

  return (
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
          Alertas de Stock
        </h1>
        <button
          onClick={cargar}
          className="ml-auto text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] px-3"
        >
          Actualizar
        </button>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
          Cargando...
        </div>
      ) : alertas.length === 0 ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center">
          <p className="text-text font-medium">Todo en orden</p>
          <p className="text-warm-gray text-sm mt-1">
            No hay ingredientes con stock bajo o sin stock.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-3xl font-bold text-red-700">{sinStock.length}</p>
              <p className="text-sm text-red-600 mt-0.5">Sin stock</p>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-3xl font-bold text-amber-700">{sinRegistro.length}</p>
              <p className="text-sm text-amber-600 mt-0.5">Sin registro</p>
            </div>
          </div>

          {/* Sin stock section */}
          {sinStock.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-red-700 mb-2 uppercase tracking-wide">
                Sin stock ({sinStock.length})
              </h2>
              <div className="bg-white rounded-xl border border-red-200 overflow-hidden divide-y divide-red-100">
                {sinStock.map((a) => (
                  <AlertaCard key={a.ingrediente_id} alerta={a} />
                ))}
              </div>
            </div>
          )}

          {/* Sin registro section */}
          {sinRegistro.length > 0 && (
            <div>
              <h2 className="text-sm font-semibold text-amber-700 mb-2 uppercase tracking-wide">
                Sin registro ({sinRegistro.length})
              </h2>
              <div className="bg-white rounded-xl border border-amber-200 overflow-hidden divide-y divide-amber-100">
                {sinRegistro.map((a) => (
                  <AlertaCard key={a.ingrediente_id} alerta={a} />
                ))}
              </div>
            </div>
          )}

          {/* Action */}
          <button
            onClick={() => router.push("/stock/registro")}
            className="w-full bg-brot text-white py-3 rounded-xl text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px]"
          >
            + Registrar Stock
          </button>
        </div>
      )}
    </div>
  );
}
