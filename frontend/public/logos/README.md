# Logos BROT

Archivos oficiales del estudio, renombrados. Los originales se llaman
"Recurso NN.svg" (ver `design/identidad/logos-svg/`), que no dice nada:

| version                            | verde #2c412c | negro      | crema #ece3d4 |
|------------------------------------|---------------|------------|---------------|
| principal (pan + BROT + PANADERIA) | Recurso 22    | Recurso 32 | Recurso 35    |
| secundario (BROT + PANADERIA)      | Recurso 23    | Recurso 33 | Recurso 36    |
| reducido (solo BROT)               | Recurso 24    | Recurso 34 | Recurso 37    |

Cuando usar cada version, segun la seccion 3.1 del manual:

- **principal** — por defecto en la mayoria de las aplicaciones.
- **secundario** — cuando el espacio no se adapta al principal.
- **reducido** — piezas chicas o donde la marca ya esta contextualizada.

Reduccion minima (seccion 3.4), para digital: **150 px de ancho** tanto para
el principal como para el secundario. Por debajo de eso "PANADERIA" deja de
leerse. El reducido no tiene minimo declarado (son cuatro letras grandes).

El color va en el archivo, no en CSS: un SVG cargado via `<img>` no hereda
`currentColor`. Hay que elegir la variante segun el fondo — ver
`src/components/BrotLogo.tsx`.

Los iconos PWA (`../icons/`) y el favicon se generan desde los PNG oficiales
con `scripts/generar_iconos.py`.
