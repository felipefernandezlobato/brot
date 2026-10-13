# Identidad BROT — archivos oficiales del estudio

Subconjunto de `IDENTIDAD BROT - PANADERÍA/` (la entrega completa pesa 491 MB
y vive en el Drive del estudio). Aca esta solo lo que usa la app.

## Que hay

| carpeta / archivo          | que es                                           |
|----------------------------|--------------------------------------------------|
| `logos-svg/`               | los 9 logos en vector, nombre original           |
| `logos-png/`               | los mismos en PNG @4x, fondo transparente        |
| `Paleta de color BROT.pdf` | **fuente de verdad del color**                   |
| `Guía de uso.pdf`          | resumen de uso del estudio                       |

## Que NO se copio

`Mockups - Aplicaciones de marca/` (bolsas, remeras, vidriera, carteleria) y
`Recursos de marca/` (personaje e ilustraciones de producto, seccion 5 del
manual). Son utiles para piezas graficas pero la app no los usa; estan en el
Drive. Las ilustraciones de producto podrian servir para el catalogo del
portal de clientes si algun dia se quieren fotos de verdad.

El `Manual de Identidad BROT.pdf` tampoco: pesa 76 MB y esta en `.gitignore`.

## Color: cuidado al muestrear

Hay dos valores dando vueltas para el Verde Brot y conviene saber por que:

- **`#2c412c`** — el que escribe `Paleta de color BROT.pdf` y el que viene
  relleno dentro de los SVG de los logos. **Este es el correcto.**
- `#25422a` — lo que sale si uno le saca el color por pixel al recuadro del
  manual de 76 MB. Ese PDF renderiza sus propios recuadros un poco corridos
  respecto al hex que escribe al lado. Es un artefacto de la presentacion.

Si la app y el PDF se ven distintos lado a lado, es por esto. Los logos y la
paleta son consistentes entre si; el deck no. Ir siempre a la paleta.

## Nombres de archivo

El estudio los llamo "Recurso NN", que no dice nada, y encima el export PNG
numera distinto que el SVG. El mapeo esta en:

- `frontend/public/logos/README.md` — para los SVG
- `scripts/generar_iconos.py` — para los PNG (identificados por proporcion)

## Ilustraciones (seccion 5)

`ilustraciones-svg/` y `ilustraciones-png/` son los 21 recursos de
`Recursos de marca/`. Los que usa la app estan copiados y renombrados en
`frontend/public/ilustraciones/` (ver `src/lib/ilustraciones.ts`):

| Recurso | nombre en la app      | que es                          |
|---------|-----------------------|---------------------------------|
| 1       | personaje-cafe        | cafe y croissant, caminando     |
| 2       | personaje-reparto     | corriendo con bolsa y baguette  |
| 3       | personaje-caja        | cargando caja BROT              |
| 4       | personaje-bandeja     | cargando una pila de panes      |
| 5       | personaje-amasando    | amasando                        |
| 6       | personaje-pan         | caminando con un pan grande     |
| 7       | personaje-saludando   | saluda con una bandeja          |
| 8       | bolsa                 | la bolsa BROT, sin personaje    |
| 9       | personaje-obrador     | escena del obrador con estante  |
| 16-21   | producto-*            | pan, croissant, baguette, roll, espiga, palote |

Los 10-15 son los mismos seis productos pero con relleno crema detras del
trazo. No se usan: sobre las tarjetas (Blanco harina) el relleno coincide con
el fondo y no aporta nada. Sirven si alguna vez hace falta ponerlos sobre
Verde Brot o Chocolate.

**Son dibujos de linea negra.** No tienen version en color de marca, asi que
solo funcionan sobre fondos claros de la paleta.
