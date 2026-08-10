"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/components/Toast";

// ── Types ──────────────────────────────────────────────────────────────────

interface ProtocoloTemplate {
  id: number;
  nombre: string;
  tipo: string;
  seccion: string;
  orden: number;
}

interface ProtocoloCompletion {
  id: number;
  template_id: number;
  target_date: string;
  target_period?: string;
  completado_por: string;
  completado_en: string;
  revisado: boolean;
  revisado_por?: string;
}

interface ProtocoloItem {
  template: ProtocoloTemplate;
  completion: ProtocoloCompletion | null;
}

interface ProtocoloHoy {
  apertura: ProtocoloItem[];
  cierre: ProtocoloItem[];
}

type TabKey = "apertura" | "cierre" | "semanal" | "mensual";

const TABS: { key: TabKey; label: string }[] = [
  { key: "apertura", label: "Apertura" },
  { key: "cierre", label: "Cierre" },
  { key: "semanal", label: "Semanal" },
  { key: "mensual", label: "Mensual" },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function groupBySection(items: ProtocoloItem[]): Map<string, ProtocoloItem[]> {
  const groups = new Map<string, ProtocoloItem[]>();
  for (const item of items) {
    const key = item.template.seccion || "General";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return groups;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── ChecklistSection ───────────────────────────────────────────────────────

function ChecklistSection({
  title,
  items,
  onToggle,
  onReview,
  isAdmin,
}: {
  title: string;
  items: ProtocoloItem[];
  onToggle: (item: ProtocoloItem) => void;
  onReview: (completionId: number) => void;
  isAdmin: boolean;
}) {
  return (
    <div className="mb-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-warm-gray mb-2 px-1">
        {title}
      </h3>
      <div className="bg-white rounded-xl overflow-hidden border border-cream-dark">
        {items.map((item, idx) => {
          const done = !!item.completion;
          const isLast = idx === items.length - 1;
          return (
            <div
              key={item.template.id}
              className={`flex items-start gap-3 p-4 ${
                !isLast ? "border-b border-cream" : ""
              } ${done ? "bg-green-50/40" : ""}`}
            >
              {/* Checkbox */}
              <button
                onClick={() => onToggle(item)}
                className={`flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors mt-0.5 ${
                  done
                    ? "bg-brot border-brot text-white"
                    : "border-cream-dark hover:border-brot"
                }`}
                aria-label={done ? "Marcar como pendiente" : "Marcar como hecho"}
              >
                {done && (
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={3}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
              </button>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <p
                  className={`text-sm leading-snug ${
                    done ? "line-through text-warm-gray" : "text-text"
                  }`}
                >
                  {item.template.nombre}
                </p>
                {done && item.completion && (
                  <p className="text-xs text-warm-gray mt-0.5">
                    {item.completion.completado_por} ·{" "}
                    {formatTime(item.completion.completado_en)}
                    {item.completion.revisado && (
                      <span className="ml-1.5 text-green-600">· ✓ Revisado</span>
                    )}
                  </p>
                )}
              </div>

              {/* Admin review button */}
              {isAdmin && done && item.completion && !item.completion.revisado && (
                <button
                  onClick={() => onReview(item.completion!.id)}
                  className="flex-shrink-0 px-2 py-1 rounded text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors min-h-[30px]"
                >
                  Revisar
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function ProtocolosPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<TabKey>("apertura");
  const [hoy, setHoy] = useState<ProtocoloHoy | null>(null);
  const [semanal, setSemanal] = useState<ProtocoloItem[]>([]);
  const [mensual, setMensual] = useState<ProtocoloItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);

  const today = new Date().toISOString().split("T")[0];

  useEffect(() => {
    apiFetch<{ role: string }>("/api/auth/me")
      .then((u) => setIsAdmin(u.role === "admin"))
      .catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [hoyData, semanalData, mensualData] = await Promise.all([
        apiFetch<ProtocoloHoy>("/api/protocolos/hoy"),
        apiFetch<ProtocoloItem[]>("/api/protocolos/semanal"),
        apiFetch<ProtocoloItem[]>("/api/protocolos/mensual"),
      ]);
      setHoy(hoyData);
      setSemanal(semanalData);
      setMensual(mensualData);
    } catch {
      toast("Error al cargar protocolos", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getItems = (): ProtocoloItem[] => {
    if (activeTab === "apertura") return hoy?.apertura ?? [];
    if (activeTab === "cierre") return hoy?.cierre ?? [];
    if (activeTab === "semanal") return semanal;
    return mensual;
  };

  // Optimistic toggle
  const applyUpdate = (
    tab: TabKey,
    templateId: number,
    newCompletion: ProtocoloCompletion | null
  ) => {
    const updater = (list: ProtocoloItem[]) =>
      list.map((i) =>
        i.template.id === templateId ? { ...i, completion: newCompletion } : i
      );
    if (tab === "apertura")
      setHoy((h) => h && { ...h, apertura: updater(h.apertura) });
    else if (tab === "cierre")
      setHoy((h) => h && { ...h, cierre: updater(h.cierre) });
    else if (tab === "semanal") setSemanal(updater);
    else setMensual(updater);
  };

  const handleToggle = async (item: ProtocoloItem) => {
    const tid = item.template.id;

    if (item.completion) {
      // Undo — optimistic remove
      applyUpdate(activeTab, tid, null);
      try {
        await apiFetch(`/api/protocolos/completar/${item.completion.id}`, {
          method: "DELETE",
        });
        toast("Tarea desmarcada");
      } catch {
        toast("Error al desmarcar", "error");
        loadData();
      }
    } else {
      // Complete — optimistic add
      const fakeCompletion: ProtocoloCompletion = {
        id: -tid,
        template_id: tid,
        target_date: today,
        completado_por: "…",
        completado_en: new Date().toISOString(),
        revisado: false,
      };
      applyUpdate(activeTab, tid, fakeCompletion);
      const body: Record<string, unknown> = {
        template_id: tid,
        target_date: today,
      };
      if (activeTab === "semanal" || activeTab === "mensual") {
        body.target_period = today;
      }
      try {
        await apiFetch("/api/protocolos/completar", {
          method: "POST",
          body: JSON.stringify(body),
        });
        toast("Tarea completada ✓");
        loadData(); // refresh to get real IDs & username
      } catch {
        toast("Error al completar", "error");
        loadData();
      }
    }
  };

  const handleReview = async (completionId: number) => {
    try {
      await apiFetch(`/api/protocolos/completar/${completionId}/revision`, {
        method: "PUT",
      });
      toast("Revisión guardada ✓");
      loadData();
    } catch {
      toast("Error al revisar", "error");
    }
  };

  const items = getItems();
  const groups = groupBySection(items);
  const completados = items.filter((i) => i.completion).length;
  const total = items.length;
  const pct = total === 0 ? 100 : Math.round((completados / total) * 100);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-[family-name:var(--font-garamond)] text-3xl text-brot">
          Protocolos
        </h1>
        <Link
          href="/protocolos/historial"
          className="text-sm text-warm-gray hover:text-brot transition-colors"
        >
          Historial →
        </Link>
      </div>

      {/* Tabs */}
      <div className="sticky top-0 bg-cream z-20 -mx-4 px-4 border-b border-cream-dark mb-6">
        <div className="flex overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-shrink-0 flex items-center gap-1.5 px-5 py-3 text-sm font-medium border-b-2 transition-colors min-h-[44px] ${
                activeTab === tab.key
                  ? "border-brot text-brot"
                  : "border-transparent text-warm-gray hover:text-text"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-12 text-center text-warm-gray text-sm">
          Cargando protocolos…
        </div>
      ) : (
        <>
          {/* Progress */}
          {total > 0 && (
            <div className="mb-6">
              <div className="flex justify-between text-xs text-warm-gray mb-1.5">
                <span>
                  {completados} de {total} completados
                </span>
                <span className="font-medium">{pct}%</span>
              </div>
              <div className="h-2 bg-cream-dark rounded-full overflow-hidden">
                <div
                  className="h-full bg-brot rounded-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )}

          {/* Temperatures shortcut for apertura/cierre */}
          {(activeTab === "apertura" || activeTab === "cierre") && (
            <Link
              href="/protocolos/temperaturas"
              className="flex items-center justify-between bg-white border border-cream-dark rounded-xl px-4 py-3 mb-4 hover:bg-cream transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div>
                  <p className="text-sm font-medium text-text">
                    Registro de temperaturas
                  </p>
                  <p className="text-xs text-warm-gray">
                    Frigoríficos y cámaras
                  </p>
                </div>
              </div>
              <span className="text-warm-gray group-hover:text-brot transition-colors">
                →
              </span>
            </Link>
          )}

          {/* Checklist */}
          {total === 0 ? (
            <div className="py-12 text-center text-warm-gray text-sm">
              No hay tareas para este período.
            </div>
          ) : (
            Array.from(groups.entries()).map(([section, sectionItems]) => (
              <ChecklistSection
                key={section}
                title={section}
                items={sectionItems}
                onToggle={handleToggle}
                onReview={handleReview}
                isAdmin={isAdmin}
              />
            ))
          )}
        </>
      )}
    </div>
  );
}
