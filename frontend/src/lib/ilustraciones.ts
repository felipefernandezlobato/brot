/* Ilustraciones de marca — Manual de Identidad, seccion 5.
 *
 * 5.2 Ilustraciones personaje: el personaje de BROT en distintas situaciones.
 *     El manual dice que "puede interactuar con productos, objetos o elementos
 *     propios de BROT, adaptandose a cada contexto". Se usan para los estados
 *     vacios, donde antes solo habia una frase gris.
 * 5.3 Ilustraciones productos: seis iconos de linea (pan, croissant, baguette,
 *     roll de canela, espiga, palote).
 *
 * Los archivos son los SVG oficiales del estudio, renombrados desde
 * "Recurso N.svg" — el mapeo esta en design/identidad/README.md.
 *
 * Son dibujos de linea negra sin color de marca adentro, asi que funcionan
 * sobre cualquier fondo claro de la paleta. No hay version crema: sobre Verde
 * Brot o Chocolate no se ven.
 */

export const PERSONAJE = {
  cafe: "/ilustraciones/personaje-cafe.svg",
  reparto: "/ilustraciones/personaje-reparto.svg",
  caja: "/ilustraciones/personaje-caja.svg",
  bandeja: "/ilustraciones/personaje-bandeja.svg",
  amasando: "/ilustraciones/personaje-amasando.svg",
  pan: "/ilustraciones/personaje-pan.svg",
  saludando: "/ilustraciones/personaje-saludando.svg",
  obrador: "/ilustraciones/personaje-obrador.svg",
  bolsa: "/ilustraciones/bolsa.svg",
} as const;

const PRODUCTO = {
  pan: "/ilustraciones/producto-pan.svg",
  croissant: "/ilustraciones/producto-croissant.svg",
  baguette: "/ilustraciones/producto-baguette.svg",
  roll: "/ilustraciones/producto-roll.svg",
  espiga: "/ilustraciones/producto-espiga.svg",
  palote: "/ilustraciones/producto-palote.svg",
} as const;

/* Solo hay seis dibujos para 22 productos de catalogo, asi que varios
 * comparten. Se busca por nombre primero (mas especifico) y se cae a la
 * categoria. El orden importa: "pan de choco" y "pan suizo" son bolleria
 * aunque empiecen con "pan", por eso van antes que la regla de "pan". */
const POR_NOMBRE: [RegExp, string][] = [
  [/cinnamon|roll|caracol/i, PRODUCTO.roll],
  [/pan de choco|pan suizo/i, PRODUCTO.croissant],
  [/barra|baguet/i, PRODUCTO.baguette],
  // el palote es para masa cruda, no para cualquier cosa hecha con masa
  // estirada: Focaccia y Pan Lomo son panes y les va la hogaza
  [/pizza|^masa/i, PRODUCTO.palote],
  [/pan\b|hogaza|focaccia|\bny\b/i, PRODUCTO.pan],
];

const POR_CATEGORIA: Record<string, string> = {
  bolleria: PRODUCTO.croissant,
  bollería: PRODUCTO.croissant,
  panes: PRODUCTO.pan,
  pasteleria: PRODUCTO.roll,
  pastelería: PRODUCTO.roll,
  masas: PRODUCTO.palote,
};

/** Ilustracion de marca para un producto de catalogo.
 *  Si el producto tiene una foto propia cargada, esa manda. */
export function ilustracionProducto(
  nombre: string,
  categoria?: string | null,
  imagenUrl?: string | null,
): string {
  if (imagenUrl) return imagenUrl;
  for (const [re, src] of POR_NOMBRE) {
    if (re.test(nombre)) return src;
  }
  const porCat = categoria && POR_CATEGORIA[categoria.toLowerCase()];
  return porCat || PRODUCTO.espiga;
}
