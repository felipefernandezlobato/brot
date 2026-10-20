/* El estado de un pedido o una entrega, con el mismo aspecto en todas partes.
 *
 * Estaba copiado en tres pantallas (/cliente/pedidos, /admin/pedidos-clientes y
 * la ficha de cliente) con tres paletas distintas para los mismos estados. Peor
 * que la inconsistencia: **dos de esas copias tenían la lista mal**.
 *
 * Ofrecían `en_proceso` y `cancelado`, que NO EXISTEN en el backend
 * (`VALID_ESTADOS` es pendiente → confirmado → en_preparacion → listo →
 * entregado, en routers/entregas_b2b.py y pedidos_clientes.py), y les faltaban
 * `en_preparacion` y `listo`, que sí son reales. Consecuencias que estaban
 * vivas: en el panel de admin, elegir "En proceso" o "Cancelado" mandaba un
 * estado inválido y el backend lo rechazaba, y no había forma de pasar un
 * pedido a "Listo"; en la pantalla del cliente, un pedido en preparación se
 * veía como una etiqueta gris con el texto crudo "en_preparacion".
 *
 * `cancelado` no existe a propósito: un pedido que no va se borra, no se marca
 * cancelado (ver el DELETE de pedido-portal). Si algún día hace falta
 * cancelar sin borrar, se agrega acá y en VALID_ESTADOS del backend.
 */

export const ESTADOS_PEDIDO = [
  { value: "pendiente", label: "Pendiente" },
  { value: "confirmado", label: "Confirmado" },
  { value: "en_preparacion", label: "En preparación" },
  { value: "listo", label: "Listo" },
  { value: "entregado", label: "Entregado" },
] as const;

const CLASES: Record<string, string> = {
  pendiente: "bg-amber-50 text-amber-700",
  confirmado: "bg-blue-50 text-blue-700",
  en_preparacion: "bg-blue-50 text-blue-700",
  listo: "bg-blue-50 text-blue-700",
  entregado: "bg-green-50 text-green-700",
};

const ETIQUETAS: Record<string, string> = Object.fromEntries(
  ESTADOS_PEDIDO.map((e) => [e.value, e.label]),
);

/** Las clases del estado, para quien necesita pintar algo que no es el badge
 *  (los chips de filtro del panel de admin usan este mismo color). */
export function claseEstado(estado: string): string {
  return CLASES[estado] ?? "bg-cream text-warm-gray";
}

export function etiquetaEstado(estado: string): string {
  // Sin traducción cae el valor crudo con el guion bajo cambiado por espacio:
  // feo pero legible, y mejor que una celda vacía si mañana se agrega un estado
  // en el backend y se olvida acá.
  return ETIQUETAS[estado] ?? estado.replace(/_/g, " ");
}

export function EstadoPedidoBadge({ estado }: { estado: string }) {
  const clase = CLASES[estado] ?? "bg-cream text-warm-gray";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${clase}`}
    >
      {etiquetaEstado(estado)}
    </span>
  );
}
