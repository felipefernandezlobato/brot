export function formatARS(amount: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function formatDateTime(isoStr: string): string {
  const d = new Date(isoStr);
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuracion(totalMin: number): string {
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

/** Parsea una cantidad tipeada por una persona.
 *
 * Devuelve null si no es un numero usable, para que quien llama pueda avisar
 * QUE fila esta mal en vez de mandar `NaN` al backend: `JSON.stringify` lo
 * convierte en `null` y la respuesta es un error de Pydantic crudo
 * ("Input should be a valid number") que no dice de que item se trata.
 * Acepta la coma como separador decimal, que es como se escribe aca.
 */
export function parseCantidad(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = parseFloat(String(v).replace(",", "."));
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/** Una cantidad para mostrar: entera sin decimales, y si no, a dos.
 *
 * Existe porque la aritmetica de coma flotante asoma en la pantalla. El panel
 * de inicio mostraba "Harina 0000 105.89999999999999 kg" y movimientos de
 * "-0.7000000000000001", que son 105,9 y -0,7 con el ruido binario a la vista.
 *
 * Estaba duplicada identica en /stock y /congelados; vive aca para que una
 * tercera pantalla no haga una tercera copia. Los umbrales de discrepancia del
 * historial estan calibrados contra estos dos decimales (ver `discrepanciaPct`
 * en esas dos paginas), asi que cambiar el redondeo de aqui los afecta.
 */
export function formatCantidad(n: number): string {
  return Number.isInteger(n) ? String(n) : (Math.round(n * 100) / 100).toString();
}

/** Deja solo digitos y un punto decimal, aceptando la coma de entrada.
 *  Permite estados intermedios como "0." mientras se escribe "0.5". */
export function limpiarCantidad(v: string): string {
  const limpio = v.replace(",", ".").replace(/[^0-9.]/g, "");
  const partes = limpio.split(".");
  return partes.length > 2 ? `${partes[0]}.${partes.slice(1).join("")}` : limpio;
}
