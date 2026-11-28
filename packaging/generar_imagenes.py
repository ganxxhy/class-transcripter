"""Genera el icono y las imágenes del instalador (sin archivos binarios en el repo).

Diseño "Jornada" de Estudio: el arco del día con el sol sobre azul noche, y un cielo de atardecer
en el panel lateral. Mismo dibujo que docs/assets/icon.svg.
Salida en packaging/build/: icono.ico, asistente-*.bmp (panel izquierdo) y logo-*.bmp (esquina).
Uso: python packaging/generar_imagenes.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "build")
TINTA = (13, 35, 64)          # #0D2340
SOL = (255, 122, 47)          # #FF7A2F
ARCO = (207, 230, 255)        # #CFE6FF
BLANCO = (255, 255, 255)


def marca(d, x, y, lado, fondo=True):
    """El logo en un cuadrado de `lado` px con esquina superior izquierda en (x, y)."""
    u = lado / 64
    if fondo:
        d.rounded_rectangle((x, y, x + lado - 1, y + lado - 1), radius=15 * u, fill=TINTA)
    cx, cy, r = x + 32 * u, y + 46 * u, 20 * u
    d.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=ARCO, width=max(1, round(5 * u)))
    sx, sy, sr = x + 46.1 * u, y + 31.9 * u, 6.25 * u
    d.ellipse((sx - sr - 1.75 * u, sy - sr - 1.75 * u, sx + sr + 1.75 * u, sy + sr + 1.75 * u), fill=BLANCO)
    d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=SOL)


def icono(lado):
    s = lado * 4  # dibujamos grande y reducimos para suavizar bordes
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    marca(ImageDraw.Draw(img), 0, 0, s)
    return img.resize((lado, lado), Image.LANCZOS)


def fuente(tam, negrita=True):
    for nombre in (["BricolageGrotesque-Bold.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"] if negrita else ["segoeui.ttf", "DejaVuSans.ttf"]):
        for carpeta in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", ""):
            try:
                return ImageFont.truetype(os.path.join(carpeta, nombre) if carpeta else nombre, tam)
            except OSError:
                continue
    return ImageFont.load_default()


def _mezcla(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def panel(ancho, alto):
    """Panel izquierdo del asistente de instalación: cielo de la tarde con el arco del día y el sol."""
    k = 3
    W, H = ancho * k, alto * k
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img, "RGBA")
    paradas = [(0, (14, 31, 74)), (.45, (79, 111, 168)), (.8, (233, 148, 106)), (1, (255, 208, 166))]
    for yy in range(H):
        t = yy / (H - 1)
        for (t0, c0), (t1, c1) in zip(paradas, paradas[1:]):
            if t0 <= t <= t1:
                d.line((0, yy, W, yy), fill=_mezcla(c0, c1, (t - t0) / (t1 - t0)))
                break
    f = W / 164
    # arco del día y el sol a media tarde
    cx, cy, r = W / 2, H * 1.02, W * .62
    d.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=(255, 255, 255, 150), width=int(5 * f))
    import math
    a = math.radians(180 + 128)
    sx, sy = cx + r * math.cos(a), cy + r * math.sin(a)
    for rr, al in ((26, 40), (18, 80)):
        d.ellipse((sx - rr * f, sy - rr * f, sx + rr * f, sy + rr * f), fill=SOL + (al,))
    d.ellipse((sx - 9 * f, sy - 9 * f, sx + 9 * f, sy + 9 * f), fill=SOL, outline=BLANCO, width=int(2.5 * f))
    # estrellas
    for px, py in ((.18, .1), (.7, .07), (.42, .2), (.86, .26), (.1, .33)):
        d.ellipse((W * px - 1.4 * f, H * py - 1.4 * f, W * px + 1.4 * f, H * py + 1.4 * f), fill=(255, 255, 255, 200))
    # logo y nombre
    m = 20 * f
    marca(d, m, m, 44 * f)
    d.text((m, H * .34), "estudio", font=fuente(int(27 * f)), fill=BLANCO)
    d.text((m, H * .34 + 34 * f), "Tus clases grabadas,\nresumidas y en orden", font=fuente(int(10.5 * f), False), fill=(228, 236, 247), spacing=int(3 * f))
    return img.resize((ancho, alto), Image.LANCZOS)


def main():
    os.makedirs(SALIDA, exist_ok=True)
    base = icono(256)
    base.save(os.path.join(SALIDA, "icono.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(os.path.join(SALIDA, "icono.png"))
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "agente"))
    from tema import hub_icon
    hub_icon().save(os.path.join(SALIDA, "hub.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # Inno Setup elige la imagen según la escala de pantalla (100 % … 250 %)
    for escala in (100, 125, 150, 175, 200, 225, 250):
        k = escala / 100
        panel(int(164 * k), int(314 * k)).save(os.path.join(SALIDA, f"asistente-{escala}.bmp"))
        peq = Image.new("RGB", (int(55 * k), int(58 * k)), BLANCO)
        ic = icono(int(52 * k))
        peq.paste(ic, ((peq.width - ic.width) // 2, (peq.height - ic.height) // 2), ic)
        peq.save(os.path.join(SALIDA, f"logo-{escala}.bmp"))
    print("Imágenes en", SALIDA)


if __name__ == "__main__":
    main()
