"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

const APP_VERSION = "0.1.0";

interface DbInfo {
  tables?: { name: string; rows: number }[];
  size_mb?: number;
  engine?: string;
}

export default function ConfiguracionPage() {
  const [dbInfo, setDbInfo] = useState<DbInfo | null>(null);
  const [dbLoading, setDbLoading] = useState(true);
  const [backupLoading, setBackupLoading] = useState(false);

  useEffect(() => {
    apiFetch<DbInfo>("/api/backup/info")
      .then(setDbInfo)
      .catch(() => {
        // Endpoint may not exist yet — fail silently, show placeholder
        setDbInfo(null);
      })
      .finally(() => setDbLoading(false));
  }, []);

  const handleDownloadBackup = async () => {
    setBackupLoading(true);
    try {
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8003";
      const token = localStorage.getItem("brot_token");
      const res = await fetch(`${apiUrl}/api/backup/descargar`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Error al descargar");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `brot-backup-${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert(
        "El endpoint de backup aún no está disponible. Estará listo en una próxima versión."
      );
    } finally {
      setBackupLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Configuración
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Información de la aplicación y herramientas de backup.
        </p>
      </div>

      <div className="space-y-5 max-w-xl">
        {/* App info */}
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
          <div className="px-4 py-2.5 bg-cream-dark">
            <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
              Aplicación
            </h3>
          </div>
          <div className="divide-y divide-cream-dark">
            <InfoRow label="Nombre" value="BROT — La Panadería" />
            <InfoRow label="Versión" value={APP_VERSION} />
            <InfoRow label="Entorno" value="Producción" />
          </div>
        </div>

        {/* Database info */}
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
          <div className="px-4 py-2.5 bg-cream-dark">
            <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
              Base de Datos
            </h3>
          </div>
          <div className="divide-y divide-cream-dark">
            {dbLoading ? (
              <p className="px-4 py-4 text-sm text-warm-gray">Cargando...</p>
            ) : dbInfo ? (
              <>
                {dbInfo.engine && (
                  <InfoRow label="Motor" value={dbInfo.engine} />
                )}
                {dbInfo.size_mb !== undefined && (
                  <InfoRow
                    label="Tamaño"
                    value={`${dbInfo.size_mb.toFixed(2)} MB`}
                  />
                )}
                {dbInfo.tables && dbInfo.tables.length > 0 && (
                  <div className="px-4 py-3">
                    <p className="text-xs font-medium text-warm-gray mb-2">
                      Tablas
                    </p>
                    <div className="space-y-1">
                      {dbInfo.tables.map((t) => (
                        <div
                          key={t.name}
                          className="flex justify-between text-sm"
                        >
                          <span className="font-mono text-text">{t.name}</span>
                          <span className="text-warm-gray">
                            {t.rows} filas
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="px-4 py-4 text-sm text-warm-gray">
                Información de base de datos no disponible.
              </p>
            )}
          </div>
        </div>

        {/* Backup */}
        <div className="bg-white rounded-xl border border-cream-dark overflow-hidden">
          <div className="px-4 py-2.5 bg-cream-dark">
            <h3 className="text-xs font-semibold text-warm-gray uppercase tracking-widest">
              Backup
            </h3>
          </div>
          <div className="p-4 space-y-3">
            <p className="text-sm text-warm-gray">
              Descarga un backup completo de los datos de la aplicación en
              formato comprimido.
            </p>
            <button
              onClick={handleDownloadBackup}
              disabled={backupLoading}
              className="flex items-center gap-2 bg-brot text-white px-5 py-2.5 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              <span>{backupLoading ? "Descargando..." : "Descargar Backup"}</span>
            </button>
            <p className="text-xs text-warm-gray">
              El endpoint de backup estará disponible próximamente.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center px-4 py-3">
      <span className="text-sm text-warm-gray">{label}</span>
      <span className="text-sm font-medium text-text">{value}</span>
    </div>
  );
}
