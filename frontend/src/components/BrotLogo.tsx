/* Logo BROT — Manual de Identidad, seccion 3.1.
 *
 * El manual autoriza tres versiones y dice cuando usar cada una:
 *
 *   principal   icono de pan + BROT + PANADERIA. "Debe utilizarse por defecto
 *               en la mayoria de las aplicaciones, reservando las versiones
 *               alternativas solo para espacios reducidos o formatos especiales."
 *   secundario  BROT + PANADERIA, sin icono. "Cuando el espacio de aplicacion
 *               no se adapte al del logo principal."
 *   reducido    solo BROT. "En piezas pequenas o donde la marca ya esta
 *               contextualizada."
 *
 * Los SVG son los archivos oficiales del estudio, renombrados — ver
 * public/logos/README.md para el mapeo contra los "Recurso NN.svg" originales.
 *
 * El color viene aplicado en el archivo, no se controla por CSS: un SVG
 * cargado via <img> no hereda currentColor. Hay que elegir la variante segun
 * el fondo:
 *
 *   color="verde"  #25422a, para fondos claros (Blanco harina, tarjetas)
 *   color="crema"  #eee3d2, para fondos Verde Brot o Chocolate
 *   color="negro"  para B&W, impresion especial o restricciones tecnicas
 *                  (seccion 3.6 del manual)
 *
 * El logo ya dice PANADERIA, asi que no hace falta repetirlo como texto al
 * lado — solo subtitulos que agreguen algo ("Tienda en linea").
 */

type Variante = "principal" | "secundario" | "reducido";
type Color = "verde" | "crema" | "negro";

const SUFIJO: Record<Color, string> = {
  verde: "",
  crema: "-crema",
  negro: "-negro",
};

export function BrotLogo({
  variante = "principal",
  color = "verde",
  className,
}: {
  variante?: Variante;
  color?: Color;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/logos/brot-${variante}${SUFIJO[color]}.svg`}
      alt="BROT Panadería"
      className={className}
      draggable={false}
    />
  );
}
