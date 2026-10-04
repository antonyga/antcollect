"""Genera el icono de AntCollect: moneda dorada con una "A" geométrica.

Uso (Pillow viene con el entorno del backend), desde backend/:
  uv run python ../mobile/assets/icono/generar.py ../mobile/assets/icono
Después, desde mobile/:
  dart run flutter_launcher_icons && dart run flutter_native_splash:create

Salidas (en mobile/assets/icono/):
  icono.png        1024², fondo oscuro a sangre (iOS, Play Store, web)
  primer_plano.png 1024², moneda sobre transparente dentro de la zona segura
                   del icono adaptativo de Android (66 %)
  splash.png       1024², moneda sobre transparente (pantalla de arranque)
  moneda.png       256², solo la moneda, para la pantalla de acceso
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SALIDA = Path(sys.argv[1])
N = 1024
SS = 4  # supersampling para bordes suaves

FONDO = (35, 27, 18)
ORO_CLARO = (247, 214, 120)
ORO = (214, 164, 46)
ORO_OSCURO = (138, 96, 14)
GRABADO = (120, 82, 10)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def moneda(diametro: int) -> Image.Image:
    """Moneda de `diametro` px (en resolución final) sobre transparente."""
    d = diametro * SS
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    r = d / 2

    # Cuerpo: degradado radial con la luz arriba a la izquierda.
    cuerpo = Image.new("RGBA", (d, d))
    px = cuerpo.load()
    lx, ly = r * 0.62, r * 0.55
    for y in range(0, d, 2):
        for x in range(0, d, 2):
            t = min(1.0, math.hypot(x - lx, y - ly) / (d * 0.95))
            c = (
                lerp(ORO_CLARO, ORO, t / 0.55)
                if t < 0.55
                else lerp(ORO, ORO_OSCURO, (t - 0.55) / 0.45)
            )
            for dx in (0, 1):
                for dy in (0, 1):
                    if x + dx < d and y + dy < d:
                        px[x + dx, y + dy] = (*c, 255)
    mascara = Image.new("L", (d, d), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, d - 1, d - 1), fill=255)
    img.paste(cuerpo, (0, 0), mascara)

    dib = ImageDraw.Draw(img)
    # Canto estriado: muescas radiales en el borde.
    estrias = 120
    for i in range(estrias):
        a = 2 * math.pi * i / estrias
        r1, r2 = r * 0.93, r * 0.995
        dib.line(
            (
                r + r1 * math.cos(a),
                r + r1 * math.sin(a),
                r + r2 * math.cos(a),
                r + r2 * math.sin(a),
            ),
            fill=(*ORO_OSCURO, 150),
            width=max(1, round(d * 0.006)),
        )
    # Gráfila: anillo interior.
    g = r * 0.80
    dib.ellipse((r - g, r - g, r + g, r + g), outline=(*GRABADO, 255), width=round(d * 0.018))

    # "A" geométrica (sin tipografías: solo polígonos).
    alto, ancho, grosor = r * 0.92, r * 0.84, r * 0.20
    cima = (r, r - alto * 0.52)
    izq = (r - ancho / 2 * 1.12, r + alto * 0.60)
    der = (r + ancho / 2 * 1.12, r + alto * 0.60)

    def trazo(p, q):
        ang = math.atan2(q[1] - p[1], q[0] - p[0]) + math.pi / 2
        ox, oy = math.cos(ang) * grosor / 2, math.sin(ang) * grosor / 2
        return [
            (p[0] + ox, p[1] + oy),
            (q[0] + ox, q[1] + oy),
            (q[0] - ox, q[1] - oy),
            (p[0] - ox, p[1] - oy),
        ]

    capa = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    cd = ImageDraw.Draw(capa)
    for p, q in ((cima, izq), (cima, der)):
        cd.polygon(trazo(p, q), fill=(*GRABADO, 255))
    cd.ellipse(
        (cima[0] - grosor / 2, cima[1] - grosor / 2, cima[0] + grosor / 2, cima[1] + grosor / 2),
        fill=(*GRABADO, 255),
    )
    # Pies cortados en horizontal: las patas se prolongan y se recortan.
    base = r + alto * 0.48
    cd.rectangle((0, base, d, d), fill=(0, 0, 0, 0))
    yb = r + alto * 0.12
    t = (yb - cima[1]) / (izq[1] - cima[1])
    xb = ancho / 2 * 1.12 * t
    cd.rectangle((r - xb, yb - grosor * 0.38, r + xb, yb + grosor * 0.38), fill=(*GRABADO, 255))
    # Recorta lo que sobresale del anillo interior y da un relieve suave.
    recorte = Image.new("L", (d, d), 0)
    ImageDraw.Draw(recorte).ellipse(
        (r - g * 0.97, r - g * 0.97, r + g * 0.97, r + g * 0.97), fill=255
    )
    capa.putalpha(Image.composite(capa.getchannel("A"), Image.new("L", (d, d), 0), recorte))
    luz = Image.new("RGBA", (d, d), (*ORO_CLARO, 0))
    luz.putalpha(capa.getchannel("A").filter(ImageFilter.GaussianBlur(d * 0.004)))
    img.alpha_composite(luz, (round(-d * 0.006), round(-d * 0.006)))
    img.alpha_composite(capa)

    return img.resize((diametro, diametro), Image.LANCZOS)


def sobre(lienzo: Image.Image, m: Image.Image, sombra: bool) -> Image.Image:
    x = (N - m.width) // 2
    if sombra:
        s = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        ImageDraw.Draw(s).ellipse(
            (x, x + N * 0.02, x + m.width, x + m.width + N * 0.02), fill=(0, 0, 0, 120)
        )
        lienzo.alpha_composite(s.filter(ImageFilter.GaussianBlur(N * 0.02)))
    lienzo.alpha_composite(m, (x, x))
    return lienzo


SALIDA.mkdir(parents=True, exist_ok=True)
icono = sobre(Image.new("RGBA", (N, N), (*FONDO, 255)), moneda(round(N * 0.78)), sombra=True)
icono.convert("RGB").save(SALIDA / "icono.png")  # iOS no admite transparencia
sobre(Image.new("RGBA", (N, N), (0, 0, 0, 0)), moneda(round(N * 0.60)), sombra=False).save(
    SALIDA / "primer_plano.png"
)
sobre(Image.new("RGBA", (N, N), (0, 0, 0, 0)), moneda(round(N * 0.62)), sombra=False).save(
    SALIDA / "splash.png"
)
moneda(256).save(SALIDA / "moneda.png")
print("ok")
