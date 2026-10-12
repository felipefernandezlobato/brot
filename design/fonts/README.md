# Fuentes de marca BROT

Archivos originales que mando el estudio (Manual de Identidad, seccion 4).

- `gelica/`     — titulos y textos especiales
- `new-reason/` — subtitulos (Medium) y cuerpo de texto (Regular)

Los `.woff2` que usa la app estan en `frontend/public/fonts/` y se generan
desde estos `.otf`.

## Ojo: los Gelica estan mal nombrados

`Gelica-Medium.otf`, `Gelica-Semi-Bold.otf` y `Gelica-Extra-Light.otf` son
**italicas**, no pesos rectos: tienen el bit ITALIC en `OS/2.fsSelection` y
`head.macStyle`, y una inclinacion real de ~190 unidades contra ~10 de las
rectas (medido sobre el trazo de la "I").

Por eso los unicos pesos RECTOS de Gelica son **300 / 400 / 700 / 900**
(Light, Regular, Bold, Black). No existe un Gelica 500 ni 600 recto — si
hace falta, hay que pedirselo al estudio, no derivarlo de esos archivos.

New Reason no tiene este problema: sus cinco pesos son rectos.

## Regenerar los woff2

    python -m venv /tmp/fontenv && /tmp/fontenv/bin/pip install "fonttools[woff]"
    # luego, por cada cara:
    #   f = TTFont(origen.otf); f.flavor = "woff2"; f.save(destino.woff2)

El manual de identidad en PDF pesa 76 MB y queda fuera de git (ver
.gitignore); esta en el Drive del estudio.
