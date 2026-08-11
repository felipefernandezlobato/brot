"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatARS, formatDate } from "@/lib/format";

interface Resumen {
  comprado_total_ars: number;
  stock_mp_valor_ars: number;
  stock_mp_items: number;
  producido_total_unidades: number;
  stock_congelado_total: number;
  entregado_b2b_total: number;
  merma_total_ars: number;
}

interface StockMP {
  ingrediente: string;
  cantidad: number;
  unidad: string;
  valor: number;
}

interface StockCong {
  nombre: string;
  cantidad: number;
}

interface PorProducto {
  nombre: string;
  stock_congelado: number;
  entregado: number;
}

interface Movimiento {
  id: number;
  tipo_stock: string;
  tipo_movimiento: string;
  cantidad: number;
  referencia_origen: string | null;
  fecha: string;
  saldo_despues: number | null;
}

interface FlujoData {
  periodo: { desde: string; hasta: string };
  resumen: Resumen;
  stock_materia_prima: StockMP[];
  stock_congelado: StockCong[];
  por_producto: PorProducto[];
  movimientos_recientes: Movimiento[];
}

interface ReconciliacionItem {
  ingrediente_id: number;
  ingrediente: string;
  unidad: string;
  conteo_fisico: number;
  fecha_conteo: string | null;
  conteo_anterior?: number;
  fecha_anterior?: string;
  recibido?: number;
  consumido?: number;
  mermado?: number;
  calculado: number | null;
  discrepancia: number | null;
  status?: string;
  detalle?: string;
}

interface ReconciliacionData {
  fecha: string;
  total_ingredientes: number;
  con_discrepancia: number;
  items: ReconciliacionItem[];
}

type Tab = "flujo" | "reconciliacion";

const TABS: { key: Tab; label: string }[] = [
  { key: "flujo", label: "Flujo General" },
  { key: "reconciliacion", label: "Reconciliacion" },
];

export default function DashboardPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<Tab>("flujo");

  const switchTab = (t: Tab) => {
    setTab(t);
    window.history.replaceState(null, "", `/?tab=${t}`);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("tab") as Tab | null;
    if (t && TABS.some((x) => x.key === t)) setTab(t);
  }, []);

  return (
    <div>
      <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot mb-6">
        Panel de Control
      </h1>

      <div className="flex gap-1 bg-white rounded-xl border border-cream-dark p-1 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => switchTab(t.key)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${
              tab === t.key
                ? "bg-brot text-white"
                : "text-warm-gray hover:text-text hover:bg-cream/50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "flujo" && <TabFlujo />}
      {tab === "reconciliacion" && <TabReconciliacion />}
    </div>
  );
}

function TabFlujo() {
  const { toast } = useToast();
  const [data, setData] = useState<FlujoData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<FlujoData>("/api/dashboard/flujo?fecha_desde=2026-05-01")
      .then(setData)
      .catch(() => toast("Error al cargar dashboard", "error"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">Cargando...</div>;
  }
  if (!data) return null;

  const r = data.resumen;

  const movLabel: Record<string, string> = {
    recepcion: "Recepcion",
    produccion_consumo: "Consumo prod.",
    produccion_salida: "Producido",
    entrega_b2b: "Entrega B2B",
    entrega_b2c: "Entrega B2C",
    merma: "Merma",
    ajuste_manual: "Ajuste",
  };

  return (
    <>
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Comprado</p>
          <p className="text-xl font-bold text-text">{formatARS(r.comprado_total_ars)}</p>
        </div>
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Stock Materia Prima</p>
          <p className="text-xl font-bold text-text">{formatARS(r.stock_mp_valor_ars)}</p>
          <p className="text-xs text-warm-gray">{r.stock_mp_items} ingredientes</p>
        </div>
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Producido</p>
          <p className="text-xl font-bold text-text">{r.producido_total_unidades}</p>
          <p className="text-xs text-warm-gray">unidades</p>
        </div>
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-xs text-warm-gray">Entregado B2B</p>
          <p className="text-xl font-bold text-text">{r.entregado_b2b_total}</p>
          <p className="text-xs text-warm-gray">unidades</p>
        </div>
      </div>

      {/* Flow arrow */}
      <div className="bg-white border border-cream-dark rounded-xl p-4 mb-6">
        <p className="text-xs font-medium text-warm-gray mb-3">Flujo de productos</p>
        <div className="flex items-center justify-between gap-2 overflow-x-auto text-center">
          <div className="flex-1 min-w-[80px]">
            <p className="text-lg font-bold text-brot">{formatARS(r.comprado_total_ars)}</p>
            <p className="text-xs text-warm-gray">Compras</p>
          </div>
          <span className="text-warm-gray shrink-0">→</span>
          <div className="flex-1 min-w-[80px]">
            <p className="text-lg font-bold text-text">{r.stock_mp_items}</p>
            <p className="text-xs text-warm-gray">Stock MP</p>
          </div>
          <span className="text-warm-gray shrink-0">→</span>
          <div className="flex-1 min-w-[80px]">
            <p className="text-lg font-bold text-text">{r.producido_total_unidades}</p>
            <p className="text-xs text-warm-gray">Producido</p>
          </div>
          <span className="text-warm-gray shrink-0">→</span>
          <div className="flex-1 min-w-[80px]">
            <p className="text-lg font-bold text-text">{r.stock_congelado_total}</p>
            <p className="text-xs text-warm-gray">Congelado</p>
          </div>
          <span className="text-warm-gray shrink-0">→</span>
          <div className="flex-1 min-w-[80px]">
            <p className="text-lg font-bold text-text">{r.entregado_b2b_total}</p>
            <p className="text-xs text-warm-gray">Entregado</p>
          </div>
        </div>
      </div>

      {/* Stock congelado by product */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-sm font-medium text-text mb-3">Stock Congelado</p>
          <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
            {data.stock_congelado
              .sort((a, b) => b.cantidad - a.cantidad)
              .map((p) => (
                <div key={p.nombre} className="flex items-center justify-between text-sm">
                  <span className="text-text truncate">{p.nombre}</span>
                  <span className="font-medium text-text tabular-nums ml-2">{p.cantidad}</span>
                </div>
              ))}
          </div>
        </div>

        <div className="bg-white border border-cream-dark rounded-xl p-4">
          <p className="text-sm font-medium text-text mb-3">Materia Prima (top 10 por valor)</p>
          <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
            {data.stock_materia_prima
              .sort((a, b) => b.valor - a.valor)
              .slice(0, 10)
              .map((item) => (
                <div key={item.ingrediente} className="flex items-center justify-between text-sm">
                  <span className="text-text truncate">
                    {item.ingrediente}
                    <span className="text-warm-gray text-xs ml-1">{item.cantidad} {item.unidad}</span>
                  </span>
                  <span className="font-medium text-text tabular-nums ml-2">{formatARS(item.valor)}</span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Recent movements */}
      {data.movimientos_recientes.length > 0 && (
        <div className="bg-white border border-cream-dark rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-cream-dark">
            <p className="text-sm font-medium text-text">Movimientos recientes</p>
          </div>
          <div className="divide-y divide-cream-dark max-h-[300px] overflow-y-auto">
            {data.movimientos_recientes.map((m) => (
              <div key={m.id} className="px-4 py-2.5 flex items-center justify-between gap-2 text-sm">
                <div>
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium mr-2 ${
                    m.cantidad > 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                  }`}>
                    {m.cantidad > 0 ? "+" : ""}{m.cantidad}
                  </span>
                  <span className="text-warm-gray">{movLabel[m.tipo_movimiento] || m.tipo_movimiento}</span>
                </div>
                <span className="text-xs text-warm-gray">{formatDate(m.fecha)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.movimientos_recientes.length === 0 && (
        <div className="bg-white border border-cream-dark rounded-xl p-6 text-center text-warm-gray text-sm">
          No hay movimientos de stock registrados todavia.
          Los movimientos se crean automaticamente al producir, recibir pedidos, entregar o registrar mermas.
        </div>
      )}
    </>
  );
}

function TabReconciliacion() {
  const { toast } = useToast();
  const [data, setData] = useState<ReconciliacionData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<ReconciliacionData>("/api/dashboard/reconciliacion")
      .then(setData)
      .catch(() => toast("Error al cargar reconciliacion", "error"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">Cargando...</div>;
  }
  if (!data) return null;

  return (
    <>
      {/* Summary */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <div className={`border rounded-xl p-4 ${
          data.con_discrepancia > 0
            ? "bg-amber-50 border-amber-200"
            : "bg-green-50 border-green-200"
        }`}>
          <p className={`text-2xl font-bold ${data.con_discrepancia > 0 ? "text-amber-700" : "text-green-700"}`}>
            {data.con_discrepancia}
          </p>
          <p className={`text-sm ${data.con_discrepancia > 0 ? "text-amber-600" : "text-green-600"}`}>
            Con discrepancia
          </p>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <p className="text-2xl font-bold text-green-700">
            {data.total_ingredientes - data.con_discrepancia}
          </p>
          <p className="text-sm text-green-600">Cuadran</p>
        </div>
      </div>

      <p className="text-xs text-warm-gray mb-3">
        Compara el conteo fisico con lo que la app calcula (conteo anterior + recibido - consumido - merma).
        Si hay discrepancia, algo no cuadra.
      </p>

      {/* Table */}
      <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-cream-dark bg-cream/50">
                <th className="text-left px-4 py-3 font-medium text-warm-gray">Ingrediente</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">Conteo fisico</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">Anterior</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">+Recibido</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">-Consumido</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">-Merma</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">= Calculado</th>
                <th className="text-right px-3 py-3 font-medium text-warm-gray">Diferencia</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item, idx) => {
                const hasDisc = item.status === "discrepancia";
                return (
                  <tr
                    key={item.ingrediente_id}
                    className={`${idx < data.items.length - 1 ? "border-b border-cream-dark" : ""} ${
                      hasDisc ? "bg-amber-50/50" : ""
                    }`}
                  >
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-text">{item.ingrediente}</p>
                      <p className="text-xs text-warm-gray">
                        {item.unidad}
                        {item.fecha_conteo && ` · ${formatDate(item.fecha_conteo)}`}
                      </p>
                    </td>
                    <td className="text-right px-3 py-2.5 font-medium text-text tabular-nums">
                      {item.conteo_fisico}
                    </td>
                    <td className="text-right px-3 py-2.5 text-warm-gray tabular-nums">
                      {item.conteo_anterior ?? "--"}
                    </td>
                    <td className="text-right px-3 py-2.5 text-green-600 tabular-nums">
                      {item.recibido ? `+${item.recibido}` : "--"}
                    </td>
                    <td className="text-right px-3 py-2.5 text-red-600 tabular-nums">
                      {item.consumido ? `-${item.consumido}` : "--"}
                    </td>
                    <td className="text-right px-3 py-2.5 text-red-600 tabular-nums">
                      {item.mermado ? `-${item.mermado}` : "--"}
                    </td>
                    <td className="text-right px-3 py-2.5 font-medium text-text tabular-nums">
                      {item.calculado !== null ? item.calculado : "--"}
                    </td>
                    <td className={`text-right px-3 py-2.5 font-bold tabular-nums ${
                      item.discrepancia === null
                        ? "text-warm-gray"
                        : hasDisc
                        ? item.discrepancia > 0 ? "text-amber-600" : "text-red-600"
                        : "text-green-600"
                    }`}>
                      {item.discrepancia !== null
                        ? item.discrepancia > 0 ? `+${item.discrepancia}` : item.discrepancia
                        : item.detalle || "--"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-xs text-warm-gray mt-3 text-right">
        {data.total_ingredientes} ingredientes analizados
      </p>
    </>
  );
}
