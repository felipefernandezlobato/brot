"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

interface Producto {
  id: number;
  nombre: string;
  categoria: string;
  unidad: string;
  nivel: string;
  producto_padre_id: number | null;
  cantidad_por_padre: number | null;
  receta_id: number | null;
  is_active: boolean;
}

interface StockCongelado {
  id: number;
  producto_congelado_id: number;
  producto_nombre: string;
  cantidad: number;
  fecha_entrada: string;
}

const NIVEL_ORDER = ["masa", "semi", "crudo", "terminado"];
const NIVEL_LABELS: Record<string, string> = {
  masa: "Masas",
  semi: "Semi-elaborados",
  crudo: "Crudos",
  terminado: "Terminados",
};
const NIVEL_COLORS: Record<string, string> = {
  masa: "text-purple-700",
  semi: "text-blue-700",
  crudo: "text-amber-700",
  terminado: "text-green-700",
};

export default function ProducirPage() {
  const { toast } = useToast();
  const [productos, setProductos] = useState<Producto[]>([]);
  const [stock, setStock] = useState<StockCongelado[]>([]);
  const [loading, setLoading] = useState(true);
  const [producing, setProducing] = useState(false);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [cantidad, setCantidad] = useState("");
  const [bastones, setBastones] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiFetch<Producto[]>("/api/congelados/productos"),
      apiFetch<StockCongelado[]>("/api/congelados"),
    ])
      .then(([p, s]) => { setProductos(p); setStock(s); })
      .catch(() => toast("Error al cargar", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const stockMap = useMemo(() => {
    const map = new Map<number, number>();
    for (const s of stock) {
      map.set(s.producto_congelado_id, (map.get(s.producto_congelado_id) ?? 0) + s.cantidad);
    }
    return map;
  }, [stock]);

  const prodMap = useMemo(
    () => new Map(productos.map((p) => [p.id, p])),
    [productos]
  );

  const grouped = useMemo(() => {
    const map = new Map<string, Producto[]>();
    for (const p of productos) {
      if (!p.is_active) continue;
      const nivel = p.nivel || "terminado";
      if (!map.has(nivel)) map.set(nivel, []);
      map.get(nivel)!.push(p);
    }
    return NIVEL_ORDER
      .filter((n) => map.has(n))
      .map((n) => ({ nivel: n, productos: map.get(n)! }));
  }, [productos]);

  const selected = selectedId ? prodMap.get(selectedId) : null;
  const padre = selected?.producto_padre_id ? prodMap.get(selected.producto_padre_id) : null;
  const needsBastones = padre && padre.nivel === "semi" && padre.nombre.toLowerCase().includes("baston");
  const padreStock = padre ? (stockMap.get(padre.id) ?? 0) : 0;

  const handleProducir = async () => {
    if (!selectedId || !cantidad || parseFloat(cantidad) <= 0) return;
    setProducing(true);
    try {
      const body: Record<string, unknown> = {
        producto_id: selectedId,
        cantidad_producida: parseFloat(cantidad),
      };
      if (needsBastones && bastones) {
        body.bastones_consumidos = parseFloat(bastones);
      }
      await apiFetch("/api/produccion/producir", {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast(`${cantidad} ${selected?.nombre} producido`);
      setCantidad("");
      setBastones("");
      setSelectedId(null);
      load();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Error al producir", "error");
    } finally {
      setProducing(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link
          href="/produccion"
          className="text-warm-gray hover:text-brot transition-colors text-sm min-h-[44px] flex items-center"
        >
          ← Calendario
        </Link>
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Producir
        </h1>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">Cargando...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Product selection */}
          <div>
            <p className="text-xs font-medium text-warm-gray mb-3">Selecciona que vas a producir</p>
            <div className="space-y-4">
              {grouped.map(({ nivel, productos: prods }) => (
                <div key={nivel}>
                  <h3 className={`text-sm font-bold uppercase tracking-wide mb-2 ${NIVEL_COLORS[nivel]}`}>
                    {NIVEL_LABELS[nivel]}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {prods.map((p) => {
                      const isSelected = selectedId === p.id;
                      const stk = stockMap.get(p.id) ?? 0;
                      const padreProd = p.producto_padre_id ? prodMap.get(p.producto_padre_id) : null;
                      return (
                        <button
                          key={p.id}
                          onClick={() => {
                            setSelectedId(isSelected ? null : p.id);
                            setCantidad("");
                            setBastones("");
                          }}
                          className={`text-left px-3 py-2.5 rounded-xl border transition-colors min-h-[44px] ${
                            isSelected
                              ? "border-brot bg-brot/5"
                              : "border-cream-dark bg-white hover:border-brot/50"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                              <p className={`font-medium text-sm truncate ${isSelected ? "text-brot" : "text-text"}`}>
                                {p.nombre}
                              </p>
                              {padreProd && (
                                <p className="text-xs text-warm-gray truncate">
                                  ← {padreProd.nombre}
                                  {p.cantidad_por_padre ? ` (${p.cantidad_por_padre}/${padreProd.unidad})` : ""}
                                </p>
                              )}
                            </div>
                            <div className="text-right shrink-0">
                              <p className="text-xs font-medium text-text tabular-nums">{stk}</p>
                              <p className="text-xs text-warm-gray">stock</p>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Production form */}
          <div>
            {!selected ? (
              <div className="bg-white rounded-xl border border-cream-dark p-8 text-center text-warm-gray">
                Selecciona un producto de la izquierda para producir.
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-cream-dark p-5 sticky top-6">
                <h2 className="font-medium text-text text-lg mb-1">{selected.nombre}</h2>
                <p className="text-xs text-warm-gray mb-4">
                  Nivel: {NIVEL_LABELS[selected.nivel]}
                  {padre && ` · Consume: ${padre.nombre}`}
                </p>

                {/* Parent stock info */}
                {padre && (
                  <div className={`rounded-lg px-4 py-3 mb-4 ${
                    padreStock > 0 ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"
                  }`}>
                    <p className="text-sm font-medium">
                      Stock de {padre.nombre}: <span className="tabular-nums">{padreStock} {padre.unidad}</span>
                    </p>
                    {selected.cantidad_por_padre && (
                      <p className="text-xs text-warm-gray mt-0.5">
                        1 {padre.unidad} → {selected.cantidad_por_padre} {selected.nombre}
                      </p>
                    )}
                  </div>
                )}

                {/* Bastones input (only for products that consume bastones) */}
                {needsBastones && (
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-text mb-1">
                      Bastones consumidos
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        inputMode="decimal"
                        min="0"
                        step="1"
                        value={bastones}
                        onChange={(e) => setBastones(e.target.value)}
                        placeholder="0"
                        className="flex-1 px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
                      />
                      <span className="text-sm text-warm-gray">bastones de {padre?.nombre}</span>
                    </div>
                    {bastones && selected.cantidad_por_padre && (
                      <p className="text-xs text-warm-gray mt-1">
                        {bastones} bastones × {selected.cantidad_por_padre} = {Math.round(parseFloat(bastones) * selected.cantidad_por_padre)} {selected.nombre} (teorico)
                      </p>
                    )}
                  </div>
                )}

                {/* Quantity produced */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-text mb-1">
                    Cantidad producida
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="any"
                      value={cantidad}
                      onChange={(e) => setCantidad(e.target.value)}
                      placeholder="0"
                      className="flex-1 px-3 py-2.5 rounded-lg border border-cream-dark bg-white text-text focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px] text-lg font-medium"
                    />
                    <span className="text-sm text-warm-gray">{selected.unidad}</span>
                  </div>
                </div>

                {/* What will happen */}
                {cantidad && parseFloat(cantidad) > 0 && (
                  <div className="bg-cream rounded-lg px-4 py-3 mb-4 text-sm space-y-1">
                    <p className="font-medium text-text">Al producir:</p>
                    {selected.receta_id && !padre && (
                      <p className="text-warm-gray">- Descuenta ingredientes de Stock MP (auto)</p>
                    )}
                    {padre && !needsBastones && (
                      <p className="text-warm-gray">
                        - Descuenta {(parseFloat(cantidad) / (selected.cantidad_por_padre || 1)).toFixed(1)} {padre.nombre} (auto)
                      </p>
                    )}
                    {needsBastones && bastones && (
                      <p className="text-warm-gray">
                        - Descuenta {bastones} bastones de {padre.nombre}
                      </p>
                    )}
                    <p className="text-brot font-medium">
                      + Suma {cantidad} {selected.nombre} al stock
                    </p>
                  </div>
                )}

                {/* Submit */}
                <button
                  onClick={handleProducir}
                  disabled={producing || !cantidad || parseFloat(cantidad) <= 0}
                  className="w-full bg-brot text-white py-3 rounded-lg text-sm font-medium hover:bg-brot-dark transition-colors min-h-[44px] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {producing ? "Registrando..." : "Registrar Produccion"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
