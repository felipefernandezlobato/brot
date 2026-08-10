"use client";

import { useRef, useState } from "react";

// ---- Types ----

type SectionKey = "ingredientes" | "recetas" | "stock" | "mermas" | "produccion";

interface Section {
  key: SectionKey;
  label: string;
  description: string;
  expectedColumns: string[];
}

const SECTIONS: Section[] = [
  {
    key: "ingredientes",
    label: "Ingredientes",
    description: "Nombre, unidad, precio por unidad, categoría.",
    expectedColumns: ["nombre", "unidad", "precio_unidad", "categoria"],
  },
  {
    key: "recetas",
    label: "Recetas",
    description: "Nombre, categoría, porciones por lote, precio de venta.",
    expectedColumns: ["nombre", "categoria", "porciones_por_lote", "precio_venta"],
  },
  {
    key: "stock",
    label: "Stock",
    description: "Ingrediente, cantidad, fecha de actualización.",
    expectedColumns: ["ingrediente", "cantidad", "fecha"],
  },
  {
    key: "mermas",
    label: "Mermas",
    description: "Ingrediente, cantidad perdida, motivo, fecha.",
    expectedColumns: ["ingrediente", "cantidad", "motivo", "fecha"],
  },
  {
    key: "produccion",
    label: "Producción",
    description: "Receta, cantidad producida, fecha, turno.",
    expectedColumns: ["receta", "cantidad", "fecha", "turno"],
  },
];

// ---- CSV parser (client-side preview only) ----

function parseCsvPreview(
  text: string
): { headers: string[]; rows: string[][] } {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length === 0) return { headers: [], rows: [] };

  const split = (line: string) =>
    line.split(",").map((cell) => cell.replace(/^"|"$/g, "").trim());

  const headers = split(lines[0]);
  const rows = lines.slice(1, 11).map(split); // show up to 10 rows
  return { headers, rows };
}

// ---- Section card ----

interface SectionCardProps {
  section: Section;
  active: boolean;
  onClick: () => void;
}

function SectionCard({ section, active, onClick }: SectionCardProps) {
  return (
    <button
      onClick={onClick}
      className={`text-left w-full p-4 rounded-xl border transition-colors ${
        active
          ? "border-brot bg-brot/5"
          : "border-cream-dark bg-white hover:bg-cream"
      }`}
    >
      <p
        className={`text-sm font-medium ${
          active ? "text-brot" : "text-text"
        }`}
      >
        {section.label}
      </p>
      <p className="text-xs text-warm-gray mt-0.5">{section.description}</p>
      <div className="flex flex-wrap gap-1 mt-2">
        {section.expectedColumns.map((col) => (
          <span
            key={col}
            className="px-1.5 py-0.5 bg-cream-dark rounded text-xs text-warm-gray font-mono"
          >
            {col}
          </span>
        ))}
      </div>
    </button>
  );
}

// ---- Preview table ----

interface PreviewTableProps {
  headers: string[];
  rows: string[][];
}

function PreviewTable({ headers, rows }: PreviewTableProps) {
  if (headers.length === 0) return null;

  return (
    <div className="overflow-x-auto bg-white rounded-xl border border-cream-dark">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-cream-dark bg-cream">
            {headers.map((h) => (
              <th
                key={h}
                className="text-left px-3 py-2 text-xs font-semibold text-warm-gray uppercase tracking-wide whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-cream-dark last:border-0">
              {headers.map((_, j) => (
                <td key={j} className="px-3 py-2 text-text whitespace-nowrap">
                  {row[j] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---- Main page ----

export default function ImportarPage() {
  const [activeSection, setActiveSection] = useState<SectionKey>("ingredientes");
  const [preview, setPreview] = useState<{
    headers: string[];
    rows: string[][];
    fileName: string;
    totalRows: number;
  } | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    if (!file.name.endsWith(".csv")) {
      alert("Por favor selecciona un archivo CSV.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const lineCount = text.split(/\r?\n/).filter(Boolean).length;
      const { headers, rows } = parseCsvPreview(text);
      setPreview({
        headers,
        rows,
        fileName: file.name,
        totalRows: Math.max(0, lineCount - 1),
      });
    };
    reader.readAsText(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleConfirm = () => {
    // Import endpoints will be added in a future phase.
    // This button is intentionally a no-op UI shell.
    alert(
      "La importación real estará disponible en una próxima versión. Por ahora puedes verificar la vista previa."
    );
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-[family-name:var(--font-garamond)] text-2xl text-brot">
          Importar Datos
        </h2>
        <p className="text-sm text-warm-gray mt-1">
          Carga archivos CSV para importar datos en lote. Selecciona la sección
          y sube el archivo correspondiente.
        </p>
      </div>

      {/* Section selector */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        {SECTIONS.map((section) => (
          <SectionCard
            key={section.key}
            section={section}
            active={activeSection === section.key}
            onClick={() => {
              setActiveSection(section.key);
              setPreview(null);
              if (fileInputRef.current) fileInputRef.current.value = "";
            }}
          />
        ))}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 p-10 rounded-2xl border-2 border-dashed cursor-pointer transition-colors mb-6 ${
          dragging
            ? "border-brot bg-brot/5"
            : "border-cream-dark bg-white hover:bg-cream"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleInputChange}
        />
        <div className="text-center">
          <p className="text-sm font-medium text-text">
            Arrastra un CSV aquí o haz clic para seleccionar
          </p>
          <p className="text-xs text-warm-gray mt-1">
            Solo archivos .csv — se mostrará una vista previa antes de importar
          </p>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm font-medium text-text">{preview.fileName}</p>
              <p className="text-xs text-warm-gray">
                {preview.totalRows} filas de datos
                {preview.totalRows > 10 && " (mostrando primeras 10)"}
              </p>
            </div>
            <button
              onClick={() => {
                setPreview(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
              className="text-xs text-warm-gray hover:text-text transition-colors"
            >
              Limpiar
            </button>
          </div>

          <PreviewTable headers={preview.headers} rows={preview.rows} />

          {/* Confirm button */}
          <div className="mt-4 flex items-center gap-4">
            <button
              onClick={handleConfirm}
              className="bg-brot text-white px-6 py-2.5 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors"
            >
              Confirmar Importación
            </button>
            <p className="text-xs text-warm-gray">
              La importación de{" "}
              <strong>
                {SECTIONS.find((s) => s.key === activeSection)?.label}
              </strong>{" "}
              estará disponible próximamente.
            </p>
          </div>
        </div>
      )}

      {/* Info box */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        <p className="font-medium mb-1">Formato esperado</p>
        <p className="text-xs text-amber-700">
          La primera fila del CSV debe contener los encabezados de columna. Los
          campos de texto con comas deben ir entre comillas. Las fechas deben
          estar en formato YYYY-MM-DD.
        </p>
      </div>
    </div>
  );
}
