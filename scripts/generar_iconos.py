#!/usr/bin/env python3
"""Genera los iconos PWA y el favicon desde el logo oficial de BROT.

El manifest.json pedia /icons/icon-192.png y /icons/icon-512.png, pero la
carpeta solo tenia un .gitkeep — o sea que la app instalada en un telefono no
tenia icono y la consola tiraba 404. Esto los genera.

Entrada:  los PNG oficiales del estudio, en design/identidad/logos-png/.
Salida:   frontend/public/icons/{icon-192,icon-512,apple-touch-icon}.png
          frontend/public/favicon.ico

El icono es el logo crema centrado sobre un cuadrado Verde Brot: en el
launcher de un telefono un logo crema sobre fondo crema desaparece.

OJO con los nombres: el export PNG numera distinto que el SVG y no trae las
mismas variantes. Identificados por proporcion (ancho/alto del contenido):

    1.26 = principal    22 verde · 29 negro · 35 crema
    1.78 = secundario   23 y 25 verde (iguales) · 30 negro · 36 crema
    2.44 = reducido     31 negro · 37 crema     <- NO hay reducido en verde

Por eso el favicon se arma con el reducido crema (37) y no con uno verde.

Uso:  python scripts/generar_iconos.py
"""
from pathlib import Path
from PIL import Image

VERDE = (0x2c, 0x41, 0x2c)
ORIGEN = Path("design/identidad/logos-png/Recurso 35@4x.png")    # principal crema
REDUCIDO = Path("design/identidad/logos-png/Recurso 37@4x.png")  # reducido crema
ICONOS = Path("frontend/public/icons")
TAMANOS = {192: "icon-192.png", 512: "icon-512.png", 180: "apple-touch-icon.png"}
AIRE = 0.14  # fraccion del lado que queda libre a cada costado


def encuadrar(logo: Image.Image, lado: int, fondo) -> Image.Image:
    """Logo centrado sobre un cuadrado, respetando su proporcion."""
    lienzo = Image.new("RGBA", (lado, lado), fondo)
    libre = int(lado * (1 - 2 * AIRE))
    esc = min(libre / logo.width, libre / logo.height)
    w, h = max(1, int(logo.width * esc)), max(1, int(logo.height * esc))
    chico = logo.resize((w, h), Image.LANCZOS)
    lienzo.paste(chico, ((lado - w) // 2, (lado - h) // 2), chico)
    return lienzo


def main():
    if not ORIGEN.exists():
        raise SystemExit(f"no encuentro {ORIGEN}")
    logo = Image.open(ORIGEN).convert("RGBA")
    # recortar al contenido real: el PNG del estudio trae aire alrededor
    caja = logo.getbbox()
    logo = logo.crop(caja)
    print(f"logo {ORIGEN.name}: recortado a {logo.width}x{logo.height}")

    ICONOS.mkdir(parents=True, exist_ok=True)
    for lado, nombre in TAMANOS.items():
        encuadrar(logo, lado, VERDE + (255,)).convert("RGB").save(ICONOS / nombre)
        print(f"  icons/{nombre:22} {lado}x{lado}")

    # favicon: a 16px el logo principal es una manchita ilegible, asi que va
    # el reducido (solo BROT). Tambien sobre cuadrado verde y no transparente:
    # en una pestana el fondo puede ser claro u oscuro segun el tema del
    # navegador, y un logo crema suelto se pierde contra el claro.
    red = Image.open(REDUCIDO).convert("RGBA")
    red = red.crop(red.getbbox())
    encuadrar(red, 64, VERDE + (255,)).convert("RGB").save(
        "frontend/public/favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"  favicon.ico            16/32/48 (reducido crema sobre verde)")


if __name__ == "__main__":
    main()
