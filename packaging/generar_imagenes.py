"""Genera el icono y las imágenes del instalador (sin archivos binarios en el repo).

Salida en packaging/build/: icono.ico, asistente-*.bmp (panel izquierdo) y logo-*.bmp (esquina).
Uso: python packaging/generar_imagenes.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "build")
ACENTO = (67, 56, 202)        # #4338CA
BLANCO = (255, 255, 255)


def ondas(draw, cx, cy, alto, grosor, color):
    """El logo: cinco barras de onda de sonido."""
    alturas = [0.33, 0.6, 1.0, 0.6, 0.33]
    paso = grosor * 2.2
    x0 = cx - paso * 2
    for i, h in enumerate(alturas):
        x = x0 + i * paso
        mitad = alto * h / 2
        draw.rounded_rectangle((x - grosor / 2, cy - mitad, x + grosor / 2, cy + mitad), radius=grosor / 2, fill=color)


def icono(lado):
    s = lado * 4  # dibujamos grande y reducimos para suavizar bordes
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.24), fill=ACENTO)
    ondas(d, s / 2, s / 2, s * 0.58, s * 0.085, BLANCO)
    return img.resize((lado, lado), Image.LANCZOS)


def fuente(tam, negrita=True):
    for nombre in (["segoeuib.ttf", "DejaVuSans-Bold.ttf"] if negrita else ["segoeui.ttf", "DejaVuSans.ttf"]):
        for carpeta in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", ""):
            try:
                return ImageFont.truetype(os.path.join(carpeta, nombre) if carpeta else nombre, tam)
            except OSError:
                continue
    return ImageFont.load_default()


def panel(ancho, alto):
    """Panel izquierdo del asistente de instalación (bienvenida y final)."""
    f = ancho / 164
    img = Image.new("RGB", (ancho, alto), ACENTO)
    d = ImageDraw.Draw(img, "RGBA")
    # círculos decorativos abajo a la izquierda
    cx, cy = ancho * 0.25, alto * 0.95
    for r in (50, 75, 100):
        rr = r * f
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 46), width=max(1, int(2 * f)))
    # logo
    m = 22 * f
    lado = 46 * f
    d.rounded_rectangle((m, m, m + lado, m + lado), radius=13 * f, fill=(255, 255, 255, 40))
    ondas(d, m + lado / 2, m + lado / 2, lado * 0.55, lado * 0.085, BLANCO)
    # nombre
    t = fuente(int(22 * f))
    d.text((m, alto * 0.62), "Agente", font=t, fill=BLANCO)
    d.text((m, alto * 0.62 + 25 * f), "de clases", font=t, fill=BLANCO)
    return img


def main():
    os.makedirs(SALIDA, exist_ok=True)
    base = icono(256)
    base.save(os.path.join(SALIDA, "icono.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(os.path.join(SALIDA, "icono.png"))
    # Inno Setup elige la imagen según la escala de pantalla (100 % … 250 %)
    for escala in (100, 125, 150, 175, 200, 225, 250):
        k = escala / 100
        panel(int(164 * k), int(314 * k)).save(os.path.join(SALIDA, f"asistente-{escala}.bmp"))
        icono(int(55 * k)).convert("RGBA")
        peq = Image.new("RGB", (int(55 * k), int(58 * k)), BLANCO)
        ic = icono(int(52 * k))
        peq.paste(ic, ((peq.width - ic.width) // 2, (peq.height - ic.height) // 2), ic)
        peq.save(os.path.join(SALIDA, f"logo-{escala}.bmp"))
    print("Imágenes en", SALIDA)


if __name__ == "__main__":
    main()
