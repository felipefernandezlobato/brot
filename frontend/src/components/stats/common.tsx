"use client";

/* Piezas compartidas de los bloques de estadisticas.
 *
 * Viven aparte porque las usan dos pantallas con permisos distintos:
 * EstadisticasMensuales (inicio, solo admin: ventas, margen y compras) y
 * EstadisticasCompras (/pedidos, cualquier empleado: solo compras).
 *
 * Son presentacionales puras: ninguna sabe de roles ni pide datos. Si alguna
 * necesita saber el rol, va en la pantalla que la usa, no aca.
 */

export interface ItemMonto {
  nombre: string;
  monto_ars: number;
}

export interface CambioPrecio {
  ingrediente_id: number;
  nombre: string;
  precio_anterior: number;
  precio_nuevo: number;
  fecha_cambio: string;
  variacion_pct: number | null;
}

const NOMBRE_MES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

export function etiquetaMes(clave: string): string {
  const [a, m] = clave.split("-").map(Number);
  return `${NOMBRE_MES[m - 1]} ${a}`;
}

export function Tarjeta({
  label,
  valor,
  detalle,
  aviso,
}: {
  label: string;
  valor: string;
  detalle?: string;
  aviso?: string;
}) {
  return (
    <div className="bg-card border border-cream-dark rounded-xl p-4">
      <p className="text-xs text-warm-gray">{label}</p>
      <p className="text-xl font-bold text-text tabular-nums">{valor}</p>
      {detalle && <p className="text-xs text-warm-gray mt-0.5">{detalle}</p>}
      {aviso && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-1.5 py-0.5 mt-1 inline-block">
          {aviso}
        </p>
      )}
    </div>
  );
}

export function Panel({
  titulo,
  nota,
  vacio,
  children,
}: {
  titulo: string;
  nota?: string;
  vacio: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-cream-dark rounded-xl p-4">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="font-medium text-text text-sm">{titulo}</h3>
        {nota && <span className="text-xs text-warm-gray">{nota}</span>}
      </div>
      {vacio ? (
        <p className="text-xs text-warm-gray">Sin datos este mes</p>
      ) : (
        <div className="space-y-1.5 max-h-[280px] overflow-y-auto">{children}</div>
      )}
    </div>
  );
}

export function Fila({ nombre, derecha, sub }: { nombre: string; derecha: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between text-sm gap-3">
      <span className="text-text truncate">{nombre}</span>
      <span className="text-warm-gray tabular-nums whitespace-nowrap">
        {sub && <span className="text-xs mr-2">{sub}</span>}
        {derecha}
      </span>
    </div>
  );
}

/* Selector de mes. Los dos bloques traen todos los meses en una sola respuesta,
 * asi que cambiar de mes es instantaneo y no vuelve a pedir nada. */
export function SelectorMes({
  meses,
  idx,
  onSelect,
}: {
  meses: string[];
  idx: number;
  onSelect: (i: number) => void;
}) {
  return (
    <div className="flex gap-1 flex-wrap">
      {meses.map((clave, i) => (
        <button
          key={clave}
          onClick={() => onSelect(i)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors min-h-[36px] ${
            i === idx ? "bg-brot text-white" : "bg-cream text-warm-gray hover:text-brot"
          }`}
        >
          {etiquetaMes(clave)}
        </button>
      ))}
    </div>
  );
}
