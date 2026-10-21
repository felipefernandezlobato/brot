"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatARS } from "@/lib/format";
import { useToast } from "@/components/Toast";

// ---- Types ----

interface CompetenciaEntry {
  id: number;
  receta_id: number;
  competidor_nombre: string;
  precio: number;
  notas?: string;
}

interface CompararRow {
  receta_id: number;
  receta_nombre: string;
  pvp: number | null;
  competidores: CompetenciaEntry[];
}

// All unique competitor names across all rows
function allCompetidores(rows: CompararRow[]): string[] {
  const names = new Set<string>();
  rows.forEach((r) => r.competidores.forEach((c) => names.add(c.competidor_nombre)));
  return Array.from(names).sort();
}

// ---- Modal: add a competitor price ----

interface AgregarModalProps {
  recetas: { id: number; nombre: string }[];
  onClose: () => void;
  onSaved: () => void;
}

function AgregarModal({ recetas, onClose, onSaved }: AgregarModalProps) {
  const { toast } = useToast();
  const [recetaId, setRecetaId] = useState<number | "">(recetas[0]?.id ?? "");
  const [competidor, setCompetidor] = useState("");
  const [precio, setPrecio] = useState("");
  const [notas, setNotas] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recetaId || !competidor.trim() || !precio) return;
    setSaving(true);
    try {
      await apiFetch("/api/competencia", {
        method: "POST",
        body: JSON.stringify({
          receta_id: recetaId,
          competidor_nombre: competidor.trim(),
          precio: parseFloat(precio),
          notas: notas.trim() || undefined,
        }),
      });
      toast("Precio agregado");
      onSaved();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error al guardar";
      toast(msg, "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-end md:items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-card rounded-2xl w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between px-5 pt-5 pb-3 border-b border-cream-dark">
          <h2 className="titulo text-xl text-brot">
            Agregar Precio Competencia
          </h2>
          <button
            onClick={onClose}
            className="text-warm-gray hover:text-text transition-colors text-xl leading-none"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Receta
            </label>
            <select
              value={recetaId}
              onChange={(e) => setRecetaId(Number(e.target.value))}
              required
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30 min-h-[44px]"
            >
              {recetas.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nombre}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Nombre del competidor
            </label>
            <input
              type="text"
              value={competidor}
              onChange={(e) => setCompetidor(e.target.value)}
              placeholder="Ej: Panadería Central"
              required
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Precio
            </label>
            <input
              type="number"
              value={precio}
              onChange={(e) => setPrecio(e.target.value)}
              placeholder="0.00"
              step="0.01"
              min="0"
              required
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-warm-gray mb-1">
              Notas (opcional)
            </label>
            <input
              type="text"
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Observaciones..."
              className="w-full px-3 py-2 border border-cream-dark rounded-lg bg-cream text-sm focus:outline-none focus:ring-2 focus:ring-brot/30"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-brot text-white py-2.5 rounded-lg text-sm font-medium min-h-[44px] hover:bg-brot-dark transition-colors disabled:opacity-50"
            >
              {saving ? "Guardando..." : "Guardar"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-5 border border-cream-dark rounded-lg text-sm min-h-[44px] hover:bg-cream transition-colors"
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---- Price cell: color-coded vs our PVP ----

/** Numera las notas distintas, para citarlas al pie como en un libro.
 *
 * Deduplica por TEXTO y no por fila: un mismo aviso se repite en varias celdas
 * (los cinco precios mayoristas de BRUTO comparten la misma nota), así que
 * numerar por celda daría trece llamadas para cuatro avisos distintos y la
 * leyenda sería ilegible.
 *
 * El orden es el de aparición recorriendo la tabla, así que la numeración sigue
 * la lectura: la primera llamada que ves es la 1.
 */
function numerarNotas(rows: CompararRow[]): Map<string, number> {
  const m = new Map<string, number>();
  rows.forEach((r) =>
    r.competidores.forEach((c) => {
      if (c.notas && !m.has(c.notas)) m.set(c.notas, m.size + 1);
    })
  );
  return m;
}

function PriceCell({
  precio,
  pvp,
  nota,
}: {
  precio: number | undefined;
  pvp: number | null;
  nota?: number;
}) {
  if (precio === undefined) {
    return <td className="px-3 py-3 text-center text-warm-gray text-sm">—</td>;
  }

  let colorClass = "text-text";
  if (pvp !== null) {
    colorClass =
      pvp <= precio
        ? "text-green-700 font-medium"  // our price is lower or equal → good
        : "text-red-600 font-medium";    // competitor is cheaper → attention
  }

  /* La llamada al pie es la mitad del valor de esta tabla.
   *
   * Las notas se podian escribir al cargar un precio y NO SE MOSTRABAN EN
   * NINGUN SITIO, asi que todas las advertencias de comparabilidad vivian en
   * un campo invisible: que el Pan Bollito se vende por kilo de masa y no por
   * unidad, que el medio kilo de BRUTO es precio de mostrador y el resto
   * mayorista, que su integral es multisemilla y el nuestro no. Sin eso, dos
   * numeros en la misma fila parecen comparables cuando no lo son, y la
   * conclusion que saca uno es "puedo triplicar el precio".
   *
   * Primero fue un asterisco con `title`, que obligaba a pasar el raton por
   * trece celdas para saber que decia cada una. Un numero que se explica al
   * pie se lee de un pantallazo.
   */
  return (
    <td className={`px-3 py-3 text-right tabular-nums text-sm ${colorClass}`}>
      {formatARS(precio)}
      {nota && (
        <sup className="ml-0.5 text-[10px] font-normal text-brot">{nota}</sup>
      )}
    </td>
  );
}

/** Las notas al pie de la tabla. */
function LeyendaNotas({ notas }: { notas: Map<string, number> }) {
  if (notas.size === 0) return null;
  const orden = [...notas.entries()].sort((a, b) => a[1] - b[1]);
  return (
    <div className="mt-3 space-y-1">
      {orden.map(([texto, n]) => (
        <p key={n} className="text-xs text-warm-gray leading-relaxed">
          <sup className="text-brot mr-1">{n}</sup>
          {texto}
        </p>
      ))}
    </div>
  );
}

// ---- Main page ----

export default function CompetenciaPage() {
  const { toast } = useToast();
  const [rows, setRows] = useState<CompararRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  const loadData = useCallback(() => {
    setLoading(true);
    apiFetch<CompararRow[]>("/api/competencia/comparar")
      .then((comparar) => {
        setRows(comparar);
      })
      .catch(() => toast("Error al cargar datos", "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const competidores = allCompetidores(rows);
  const notasNumeradas = numerarNotas(rows);

  // Build unique list of recetas for the modal
  const recetasParaModal = rows.map((r) => ({
    id: r.receta_id,
    nombre: r.receta_nombre,
  }));

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="titulo text-3xl text-brot">
          Precios Competencia
        </h1>
        <button
          onClick={() => setShowModal(true)}
          className="bg-brot text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px] flex items-center hover:bg-brot-dark transition-colors"
        >
          + Agregar Precio
        </button>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mb-4 text-xs text-warm-gray">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-green-100 border border-green-300" />
          Nuestro precio es competitivo
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-red-100 border border-red-300" />
          Competidor más barato
        </span>
      </div>

      {/* Table */}
      <div className="bg-card rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-warm-gray text-sm">
            Cargando...
          </div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-warm-gray text-sm">
            No hay datos de competencia registrados.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-warm-gray text-xs uppercase tracking-wide">
                  {/* Sticky: la tabla mide ~710px y en un movil el contenedor
                      da 358, asi que hay que desplazarla si o si. Sin fijar
                      esta columna, mirar el precio de un competidor dejaba
                      fuera de pantalla el nombre del producto. Fondo opaco
                      obligatorio -- una celda sticky no hereda el fondo de su
                      fila y se veria el texto de debajo al pasar. */}
                  <th className="sticky left-0 z-20 bg-card text-left px-3 py-3 min-w-[150px]">
                    Receta
                  </th>
                  <th className="text-right px-3 py-3 min-w-[110px]">
                    PVP B2B
                  </th>
                  {competidores.map((name) => (
                    <th
                      key={name}
                      className="text-right px-3 py-3 min-w-[110px]"
                    >
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  // La entrada entera y no solo el precio: la celda necesita
                  // tambien la nota para poder citarla al pie.
                  const competidorMap = new Map(
                    row.competidores.map((c) => [c.competidor_nombre, c])
                  );
                  return (
                    <tr
                      key={row.receta_id}
                      className="border-b border-gray-50 hover:bg-cream transition-colors"
                    >
                      <td className="sticky left-0 z-10 bg-card px-3 py-3">
                        <div className="font-medium text-text">
                          {row.receta_nombre}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-sm font-semibold text-text">
                        {row.pvp !== null ? formatARS(row.pvp) : "—"}
                      </td>
                      {competidores.map((name) => (
                        <PriceCell
                          key={name}
                          precio={competidorMap.get(name)?.precio}
                          nota={
                            notasNumeradas.get(
                              competidorMap.get(name)?.notas ?? ""
                            )
                          }
                          pvp={row.pvp}
                        />
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {/* La leyenda va FUERA del contenedor con scroll horizontal: dentro
            heredaba el ancho de la tabla y en un movil habia que desplazarse
            a la derecha para leerla, que es justo lo contrario de lo que
            tiene que hacer una nota al pie. */}
        {!loading && rows.length > 0 && <LeyendaNotas notas={notasNumeradas} />}
      </div>

      {showModal && (
        <AgregarModal
          recetas={recetasParaModal}
          onClose={() => setShowModal(false)}
          onSaved={() => {
            setShowModal(false);
            loadData();
          }}
        />
      )}
    </div>
  );
}
